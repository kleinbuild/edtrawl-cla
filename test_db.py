import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import db

HOME = "38.577,-121.495"  # California State Capitol
TABLES = {"schools", "school_years", "homes", "known_drives", "commutes", "jobs", "name_matches", "job_marks"}


def school(conn, cds, district="3467439", name="Capitol Elementary"):
    conn.execute("INSERT INTO schools (cds_code, district_code, district_name, county_name, school_name,"
                 " first_year, last_year) VALUES (?, ?, 'Sacramento City Unified', 'Sacramento', ?,"
                 " '2025-26', '2025-26')", (cds, district, name))


class Schema(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init_db(self.conn)

    def test_tables_and_view_exist(self):
        rows = self.conn.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table','view')").fetchall()
        self.assertEqual({r["name"] for r in rows if r["type"] == "table"}, TABLES)
        self.assertEqual([r["name"] for r in rows if r["type"] == "view"], ["job_search"])

    def test_init_twice(self):
        school(self.conn, "34674390000001")
        before = self.conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
        db.init_db(self.conn)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0], before)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM schools").fetchone()[0], 1)

    def test_cde_columns_single_source(self):
        headers = [c.header for c in db.CDE_COLUMNS]
        self.assertEqual(len(headers), 98)
        self.assertEqual(len(set(headers)), 98)
        for table in ("schools", "school_years"):
            cols = [r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")]
            expected = [c.column for c in db.CDE_COLUMNS if table in c.tables]
            self.assertEqual(cols[:len(expected)], expected)

    def test_13_char_cds_fails(self):
        with self.assertRaises(sqlite3.IntegrityError):
            school(self.conn, "3467439000000")

    def test_leading_zero_cds_kept(self):
        school(self.conn, "01100170112607", district="0110017")
        self.assertEqual(self.conn.execute("SELECT cds_code FROM schools").fetchone()[0], "01100170112607")

    def test_snapshot_for_unknown_school_fails(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO school_years (cds_code, academic_year) VALUES ('34674390000001', '2025-26')")

    def test_bad_flag_fails(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO schools (cds_code, district_code, school_name, charter, first_year,"
                              " last_year) VALUES ('34674390000001', '3467439', 'x', 'Yes', '2025-26', '2025-26')")

    def test_factor_am_3_fails(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO homes (home_key, factor_am, created_on) VALUES (?, 3.0, '2026-11-16')",
                              (HOME,))

    def test_mark_maybe_fails(self):
        self.conn.execute("INSERT INTO jobs (posting_id, title, url, first_seen, last_seen)"
                          " VALUES (1, 'Teacher', 'https://www.edjoin.org/x', 'd', 'd')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO job_marks VALUES (1, 'maybe', NULL, '2026-11-16')")


class JobSearchView(unittest.TestCase):
    def setUp(self):
        c = self.conn = db.connect(":memory:")
        db.init_db(c)
        c.execute("INSERT INTO homes (home_key, factor_am, factor_pm, created_on) VALUES (?, 1.2, 1.5, 'd')", (HOME,))
        for cds, am, pm, prov in (("34674390000001", 10, 20, "osrm"), ("34674390000002", 30, 25, "estimate")):
            school(c, cds)
            c.execute("INSERT INTO commutes VALUES (?, ?, 5, ?, ?, ?, 'd')", (cds, HOME, am, pm, prov))
        for year, n in (("2024-25", 400), ("2025-26", 420)):
            c.execute("INSERT INTO school_years (cds_code, academic_year, enroll_total) VALUES (?, ?, ?)",
                      ("34674390000001", year, n))
        jobs = ((1, "34674390000001", "3467439"), (2, None, "3467439"), (3, None, None))
        for pid, cds, dist in jobs:
            c.execute("INSERT INTO jobs (posting_id, title, url, district_code, cds_code, first_seen, last_seen)"
                      " VALUES (?, 'Teacher', 'https://www.edjoin.org/x', ?, ?, 'd', 'd')", (pid, dist, cds))
        c.execute("INSERT INTO job_marks VALUES (1, 'kept', NULL, '2026-11-16')")
        self.rows = {r["posting_id"]: r for r in c.execute("SELECT * FROM job_search WHERE home_key = ?", (HOME,))}

    def test_school_job(self):
        r = self.rows[1]
        self.assertAlmostEqual(r["am_minutes"], 12.0)  # factor_am on the morning only
        self.assertAlmostEqual(r["pm_minutes"], 30.0)  # factor_pm on the afternoon only
        self.assertEqual((r["provider"], r["mark_status"], r["school_name"]), ("osrm", "kept", "Capitol Elementary"))
        self.assertEqual((r["academic_year"], r["enroll_total"]), ("2025-26", 420))
        self.assertEqual((r["prev_academic_year"], r["prev_enroll_total"]), ("2024-25", 400))
        self.assertIsNone(r["district_min_minutes"])

    def test_district_job(self):
        r = self.rows[2]
        # slower direction per school after factors: max(12, 30) = 30 and max(36, 37.5) = 37.5
        self.assertEqual((r["district_min_minutes"], r["district_max_minutes"]), (30.0, 37.5))
        self.assertEqual(r["district_schools_in_range"], 2)
        self.assertEqual(r["provider"], "estimate")
        self.assertEqual(r["district_name"], "Sacramento City Unified")
        self.assertIsNone(r["am_minutes"])
        self.assertIsNone(r["mark_status"])

    def test_unmatched_job_still_listed(self):
        self.assertEqual(set(self.rows), {1, 2, 3})
        self.assertIsNone(self.rows[3]["provider"])


class Main(unittest.TestCase):
    def test_python_db_py_twice(self):
        with tempfile.TemporaryDirectory() as d:
            for _ in range(2):
                out = subprocess.run([sys.executable, str(Path(db.__file__).resolve())], cwd=d,
                                     capture_output=True, text=True, check=True).stdout
            self.assertTrue((Path(d) / "edtrawl.db").exists())
            for name in TABLES | {"job_search"}:
                self.assertIn(name, out)


if __name__ == "__main__":
    unittest.main()
