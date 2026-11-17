import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import chart
import config
import db
import edtrawl

TODAY = date(2026, 11, 16)
HOME = "38.577,-121.495"


def make(jobs, websites=("https://www.lincoln.example/",)):
    """An in-memory database: home, three schools (two in district D1), a commute each, and the given jobs."""
    conn = db.connect(":memory:")
    db.init_db(conn)
    conn.execute("INSERT INTO homes (home_key, created_on) VALUES (?, '2026-11-01')", (HOME,))
    for i, (name, lat, lng, site) in enumerate([("Lincoln Elementary", 38.59, -121.47, websites[0]),
                                                 ("Roosevelt Middle", 38.62, -121.40, "http://plain.example/"),
                                                 ("Far High", 38.30, -121.90, "javascript:alert(1)")]):
        conn.execute("INSERT INTO schools (cds_code, district_code, district_name, school_name, lat, lng, website, "
                     "first_year, last_year) VALUES (?, ?, 'D1 Unified', ?, ?, ?, ?, '2025-26', '2025-26')",
                     (f"3467000000{i:04d}", "3467000", name, lat, lng, site))
        conn.execute("INSERT INTO commutes VALUES (?, ?, ?, ?, ?, 'osrm', '2026-11-01')",
                     (f"3467000000{i:04d}", HOME, 2 + 10 * i, 8 + 20 * i, 10 + 20 * i))
    for pid, title, cds in jobs:
        conn.execute("INSERT INTO jobs (posting_id, title, district_raw, district_code, cds_code, salary_info, deadline, "
                     "url, first_seen, last_seen) VALUES (?, ?, 'D1', '3467000', ?, '$50,000', '2026-11-25', 'x', "
                     "'2026-11-10', '2026-11-10')", (pid, title, cds))
    conn.commit()
    return conn, config.Config(home_key=HOME)


def page(jobs, **kw):
    conn, cfg = make(jobs, **kw)
    return chart.render(chart.gather(conn, cfg, TODAY), cfg)


class Chart(unittest.TestCase):
    def test_title_with_script_is_escaped(self):
        html = page([(1, "<script>alert(1)</script> & Math", "34670000000000")])
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; Math", html)
        self.assertEqual(html.count("<script>"), 1)  # only ours
        self.assertEqual(html.count("</script>"), 1)

    def test_only_allowed_urls(self):
        html = page([(7, "Math", "34670000000000"), (8, "Art", "34670000000001"), (9, "Gym", "34670000000002")])
        self.assertNotIn("http://", html)
        self.assertNotIn("javascript:", html.lower().replace("javascript:alert(1)", ""))  # not as a link
        self.assertNotRegex(html, r"(?i)href=\"(?:javascript|http:)")
        refs = re.findall(r'\b(?:src|href)="([^"]*)"', html)
        for r in refs:
            self.assertTrue(r.startswith("#") or r.startswith(chart.EDJOIN) or r == "https://www.lincoln.example/", r)
        self.assertIn(chart.EDJOIN + "7", html)
        self.assertEqual(set(re.findall(r"https?://[^\s\"'<>)]+", html)) - {"https://www.lincoln.example/"},
                         {chart.EDJOIN + str(i) for i in (7, 8, 9)})
        self.assertNotIn("<img", html)
        self.assertNotIn("url(", html)

    def test_csp_and_no_home_coordinates(self):
        html = page([(1, "Math", "34670000000000")])
        self.assertIn("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:", html)
        for needle in ("38.577", "-121.495", "121.495", "38.57"):
            self.assertNotIn(needle, html)
        self.assertIn("where home is relative to nearby schools", html)

    def test_district_jobs_listed_not_mapped(self):
        html = page([(1, "Math", "34670000000000"), (2, "District Wide Teacher", None)])
        cards = re.findall(r'<li class="card".*?</li>', html, re.S)
        self.assertEqual(len(cards), 2)
        wide = next(c for c in cards if "District Wide Teacher" in c)
        self.assertIn("Site not listed", wide)
        self.assertIn("no single dot", wide)
        self.assertIn('data-school=""', wide)
        self.assertNotIn('class="find"', wide)
        self.assertEqual(html.count('class="mk '), 1)  # one hiring school on the map
        self.assertIn("across the district", wide)

    def test_card_facts_and_bands(self):
        html = page([(1, "Math", "34670000000002")])
        self.assertIn("~", html)
        self.assertIn("Over 45 min", html)
        self.assertIn("estimates, assuming you arrive by 7:00 and leave at 3:30", html)
        self.assertIn("Made Nov 16, 2026", html)
        self.assertIn("OpenStreetMap contributors", html)
        self.assertIn("California Department of Education", html)

    def test_empty_state_still_shows_schools(self):
        html = page([])
        self.assertIn("the net is empty today", html)
        self.assertIn("python edtrawl.py", html)
        self.assertEqual(html.count("<circle cx="), 3 + len(chart._rings(20)) + 1)  # 3 schools, rings, home
        self.assertNotIn('class="card"', html)

    def test_tossed_and_closed_jobs_are_left_out(self):
        conn, cfg = make([(1, "Kept one", "34670000000000"), (2, "Tossed one", "34670000000000"),
                          (3, "Closed one", "34670000000000")])
        conn.execute("INSERT INTO job_marks VALUES (1, 'kept', NULL, '2026-11-12')")
        conn.execute("INSERT INTO job_marks VALUES (2, 'tossed', NULL, '2026-11-12')")
        conn.execute("UPDATE jobs SET deadline = '2026-11-01' WHERE posting_id = 3")
        html = chart.render(chart.gather(conn, cfg, TODAY), cfg)
        self.assertIn("Kept one", html)
        self.assertNotIn("Tossed one", html)
        self.assertNotIn("Closed one", html)
        self.assertIn('data-kept="1"', html)


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        conn = db.connect(str(self.tmp / "t.db"))
        db.init_db(conn)
        conn.close()
        (self.tmp / "c.toml").write_text(f'home_key = "{HOME}"\n')

    def run_chart(self, *extra):
        out = self.tmp / "out.html"
        with mock.patch("webbrowser.open", return_value=True) as opened:
            code = edtrawl.main(["--db", str(self.tmp / "t.db"), "--config", str(self.tmp / "c.toml"), "--plain",
                                 "chart", "--out", str(out), *extra])
        return code, out, opened

    def test_writes_and_opens(self):
        conn = db.connect(str(self.tmp / "t.db"))
        conn.execute("INSERT INTO homes (home_key, created_on) VALUES (?, '2026-11-01')", (HOME,))
        conn.commit()
        conn.close()
        code, out, opened = self.run_chart()
        self.assertEqual(code, 0)
        self.assertTrue(out.read_text().startswith("<!doctype html>"))
        opened.assert_called_once()

    def test_no_open_flag(self):
        code, out, opened = self.run_chart("--no-open")
        self.assertEqual(code, 0)
        self.assertTrue(out.exists())
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
