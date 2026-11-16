import sqlite3
import tempfile
import unittest
from pathlib import Path

import db
import ingest

FX = Path(__file__).parent / "tests" / "fixtures"
NEW, OLD = FX / "cde_2025-26.csv", FX / "cde_2024-25.csv"
SYNTH = "99999999999999"


def fresh():
    conn = db.connect(":memory:")
    db.init_db(conn)
    return conn


def dump(conn):
    return [[tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1, 2")] for t in ("schools", "school_years")]


class IngestTest(unittest.TestCase):
    def test_counts_and_reload_is_identical(self):
        conn = fresh()
        self.assertEqual(ingest.ingest(conn, NEW), {"academic_year": "2025-26", "schools": 20, "snapshots": 20})
        before = dump(conn)
        ingest.ingest(conn, NEW)
        self.assertEqual(dump(conn), before)
        self.assertEqual(len(before[0]), 20)
        self.assertEqual(len(before[1]), 20)

    def test_suppressed_cells_are_null(self):
        conn = fresh()
        ingest.ingest(conn, NEW)
        r = conn.execute("SELECT african_american, african_american_pct, filipino, filipino_pct "
                         "FROM school_years WHERE cds_code = ?", (SYNTH,)).fetchone()
        self.assertEqual(tuple(r), (None, None, None, None))

    def test_leading_zero_code_round_trips(self):
        conn = fresh()
        ingest.ingest(conn, NEW)
        row = conn.execute("SELECT cds_code FROM schools WHERE cds_code = '01100170112607'").fetchone()
        self.assertEqual(len(row[0]), 14)

    def test_old_after_new_keeps_new_identity(self):
        conn = fresh()
        ingest.ingest(conn, NEW)
        ingest.ingest(conn, OLD)
        r = conn.execute("SELECT school_name, first_year, last_year FROM schools WHERE cds_code = '34674390101907'").fetchone()
        self.assertEqual((r[0], r[1], r[2]), ("The MET", "2024-25", "2025-26"))
        self.assertEqual(conn.execute("SELECT school_name FROM schools WHERE cds_code = '01611190111765'").fetchone()[0],
                         conn.execute("SELECT school_name FROM schools s JOIN school_years y USING (cds_code) "
                                      "WHERE cds_code = '01611190111765' AND academic_year = '2025-26'").fetchone()[0])

    def test_order_does_not_matter(self):
        a, b = fresh(), fresh()
        ingest.ingest(a, NEW); ingest.ingest(a, OLD)
        ingest.ingest(b, OLD); ingest.ingest(b, NEW)
        self.assertEqual(dump(a), dump(b))

    def test_only_old_school_keeps_old_last_year(self):
        conn = fresh()
        ingest.ingest(conn, NEW); ingest.ingest(conn, OLD)
        r = conn.execute("SELECT first_year, last_year FROM schools WHERE cds_code = '01100170125567'").fetchone()
        self.assertEqual((r[0], r[1]), ("2024-25", "2024-25"))

    def test_override_survives_reingest(self):
        conn = fresh()
        ingest.ingest(conn, NEW)
        conn.execute("UPDATE schools SET lat_override = 1.5, lng_override = -2.5 WHERE cds_code = '34674390101907'")
        ingest.ingest(conn, NEW); ingest.ingest(conn, OLD)
        r = conn.execute("SELECT lat_override, lng_override, lat FROM schools WHERE cds_code = '34674390101907'").fetchone()
        self.assertEqual((r[0], r[1]), (1.5, -2.5))
        self.assertNotEqual(r[2], 1.5)  # CDE's own lat still refreshes

    def test_2024_rows_have_null_staff(self):
        conn = fresh()
        ingest.ingest(conn, OLD)
        n = conn.execute("SELECT COUNT(*) FROM school_years WHERE staff_total IS NOT NULL OR staff_teacher IS NOT NULL").fetchone()[0]
        self.assertEqual(n, 0)

    def test_blank_latitude_and_zip4(self):
        conn = fresh()
        ingest.ingest(conn, OLD)
        blanks = conn.execute("SELECT lat, lng FROM schools WHERE lat IS NULL").fetchall()
        self.assertEqual(len(blanks), 2)
        self.assertTrue(all(r[1] is None for r in blanks))
        self.assertEqual(conn.execute("SELECT zip FROM schools WHERE cds_code = '01100170112607'").fetchone()[0], "94612")

    def test_dates_and_flags(self):
        self.assertEqual(ingest.coerce("1/1/1938 12:00:00 AM", "TEXT", "open_date"), "1938-01-01")
        self.assertEqual(ingest.coerce("12/31/2020 12:00:00 AM", "TEXT", "closed_date"), "2020-12-31")
        self.assertIsNone(ingest.coerce("", "TEXT", "open_date"))
        self.assertIsNone(ingest.coerce("?", "TEXT", "charter"))
        self.assertEqual(ingest.coerce(" Y ", "TEXT", "charter"), "Y")
        self.assertEqual(ingest.coerce("12.0", "INTEGER"), 12)
        self.assertIsNone(ingest.coerce("*", "REAL"))

    def test_unknown_header_raises_and_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.csv"
            p.write_text("CDS Code,Mystery Column\r\n01100170112607,x\r\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Mystery Column"):
                ingest.ingest(fresh(), p)

    def test_progress_called(self):
        calls = []
        ingest.ingest(fresh(), NEW, on_progress=lambda *a: calls.append(a))
        self.assertEqual(calls[-1][:2], (20, 20))


if __name__ == "__main__":
    unittest.main()
