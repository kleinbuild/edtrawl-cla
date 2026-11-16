import unittest
from datetime import date, timedelta
from types import SimpleNamespace

import db
import query

HOME = "38.577,-121.495"
A, B, C = "01234560000001", "07654320000002", "01234560000003"  # A and C share district 0123456
CFG = SimpleNamespace(home_key=HOME)
TODAY = date.today()


def build():
    conn = db.connect(":memory:")
    db.init_db(conn)
    for code, name, level, charter in ((A, "Alpha Elementary", "Elementary", "N"), (B, "Bravo High", "High", "Y"),
                                       (C, "Charlie Middle", "Middle", "N")):
        conn.execute("INSERT INTO schools (cds_code, district_code, school_name, school_level, charter, "
                     "first_year, last_year, district_name, county_name) VALUES (?,?,?,?,?,?,?,?,?)",
                     (code, code[:7], name, level, charter, "2024-25", "2025-26", "D" + code[:7], "Sacramento"))
    for code, year, enroll, t1 in ((A, "2024-25", 400, "Y"), (A, "2025-26", 440, "Y"), (B, "2024-25", 900, "N"),
                                   (B, "2025-26", 880, "N"), (C, "2025-26", 300, "N")):
        conn.execute("INSERT INTO school_years (cds_code, academic_year, enroll_total, title_i) VALUES (?,?,?,?)",
                     (code, year, enroll, t1))
    conn.execute("INSERT INTO homes (home_key, factor_am, factor_pm, created_on) VALUES (?,1.2,1.5,'2026-11-16')", (HOME,))
    conn.execute("INSERT INTO homes (home_key, created_on) VALUES ('36.0,-119.0','2026-11-16')")  # another home
    for code, am, pm in ((A, 10, 20), (B, 30, 12), (C, 5, 5)):
        conn.execute("INSERT INTO commutes VALUES (?,?,?,?,?,'estimate','2026-11-16')", (code, HOME, 5.0, am, pm))
    # (id, cds, district, posted days ago)
    for pid, cds, dist, ago in ((1, A, None, 1), (2, B, None, 10), (3, None, A[:7], 2), (4, None, None, 3), (5, A, None, 40)):
        conn.execute("INSERT INTO jobs (posting_id, title, url, cds_code, district_code, posted_on, first_seen, last_seen) "
                     "VALUES (?,?,?,?,?,?,'2026-11-16','2026-11-16')",
                     (pid, f"Job {pid}", f"https://x/{pid}", cds, dist, (TODAY - timedelta(days=ago)).isoformat()))
    conn.execute("INSERT INTO job_marks VALUES (2,'kept',NULL,'2026-11-16')")
    conn.execute("INSERT INTO job_marks VALUES (5,'tossed',NULL,'2026-11-16')")
    conn.commit()
    return conn


def ids(rows):
    return [r["posting_id"] for r in rows]


class QueryTest(unittest.TestCase):
    def setUp(self):
        self.conn = build()

    def s(self, **kw):
        return ids(query.search(self.conn, CFG, **kw))

    def test_order_nearest_first_no_drive_last(self):
        # job 3 district-wide: nearest school C = 7.5; job 1: max(12, 30) = 30; job 2: max(36, 18) = 36; job 4 none
        self.assertEqual(self.s(), [3, 1, 5, 2, 4])

    def test_each_factor_on_its_own_direction(self):
        r = {x["posting_id"]: x for x in query.search(self.conn, CFG)}
        self.assertAlmostEqual(r[1]["am_minutes"], 12)   # 10 * 1.2
        self.assertAlmostEqual(r[1]["pm_minutes"], 30)   # 20 * 1.5
        self.assertAlmostEqual(r[2]["drive_minutes"], 36)  # larger of 30*1.2 and 12*1.5

    def test_district_job_reports_min_and_max(self):
        r = {x["posting_id"]: x for x in query.search(self.conn, CFG)}[3]
        self.assertAlmostEqual(r["district_min_minutes"], 7.5)
        self.assertAlmostEqual(r["district_max_minutes"], 30)
        self.assertEqual(r["district_schools_in_range"], 2)

    def test_other_home_is_not_mixed_in(self):
        other = SimpleNamespace(home_key="36.0,-119.0")
        self.assertEqual(ids(query.search(self.conn, other)).count(1), 1)  # one row per job per home
        self.assertTrue(all(r["drive_minutes"] is None for r in query.search(self.conn, other)))

    def test_max_commute(self):
        self.assertEqual(self.s(max_commute=30), [3, 1, 5])      # inclusive; no-drive job 4 excluded
        self.assertEqual(self.s(max_commute=35), [3, 1, 5])
        self.assertEqual(self.s(max_commute=5), [])

    def test_posted_within(self):
        self.assertEqual(self.s(posted_within=5), [3, 1, 4])
        self.assertEqual(self.s(posted_within=60), [3, 1, 5, 2, 4])

    def test_level_and_district_jobs_excluded_from_school_filters(self):
        self.assertEqual(self.s(level="elem"), [1, 5])
        self.assertEqual(self.s(level="high"), [2])

    def test_charter(self):
        self.assertEqual(self.s(charter=True), [2])
        self.assertEqual(self.s(charter=False), [1, 5])

    def test_title_i_and_enrollment_use_latest_year(self):
        self.assertEqual(self.s(title_i=True), [1, 5])
        self.assertEqual(self.s(title_i=False), [2])
        self.assertEqual(self.s(min_enrollment=900), [])          # B is 880 now, 900 last year
        self.assertEqual(self.s(min_enrollment=440), [1, 5, 2])
        r = {x["posting_id"]: x for x in query.search(self.conn, CFG)}[1]
        self.assertEqual((r["enroll_total"], r["prev_enroll_total"], r["academic_year"]), (440, 400, "2025-26"))

    def test_status_and_new_only(self):
        self.assertEqual(self.s(status="kept"), [2])
        self.assertEqual(self.s(status="tossed"), [5])
        self.assertEqual(self.s(new_only=True), [3, 1, 4])

    def test_limit(self):
        self.assertEqual(self.s(limit=2), [3, 1])

    def test_nearly(self):
        # new_only leaves 3 (7.5), 1 (30), 4 (none). Above 10: job 1 at 30
        self.assertEqual(query.nearly(self.conn, CFG, max_commute=10, new_only=True), (30, 1))
        # all jobs: next above 10 is 30 (jobs 1 and 5), then 36
        self.assertEqual(query.nearly(self.conn, CFG, max_commute=10), (30, 2))
        # rounds up to the next 5
        self.assertEqual(query.nearly(self.conn, CFG, max_commute=30), (40, 1))
        self.assertIsNone(query.nearly(self.conn, CFG, max_commute=36))
        self.assertIsNone(query.nearly(self.conn, CFG))

    def test_nearly_respects_other_filters(self):
        self.assertEqual(query.nearly(self.conn, CFG, max_commute=10, charter=True), (40, 1))


if __name__ == "__main__":
    unittest.main()
