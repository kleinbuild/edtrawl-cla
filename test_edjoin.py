import json
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import db
import edjoin

FIX = Path(__file__).with_name("tests") / "fixtures"
LISTING = FIX / "edjoin_listing.json"
DETAIL = FIX / "edjoin_detail.html"


def memdb():
    conn = db.connect(":memory:")
    db.init_db(conn)
    return conn


def ms(y, m, d, h=0, mi=0):
    return f"/Date({int(datetime(y, m, d, h, mi, tzinfo=timezone.utc).timestamp() * 1000)})/"


def page(rows, pages=1, total=None):
    return json.dumps({"data": rows, "totalPages": pages, "totalRecords": total or len(rows)}).encode()


def row(i, **kw):
    r = {"postingID": i, "positionTitle": f"Teacher {i}", "displayFlag": "By Date",
         "postingDate": ms(2026, 11, 13), "displayUntil": ms(2026, 11, 20, 7, 55), "numberOpenings": 0}
    return {**r, **kw}


class Fake:
    """Replaces the HTTP function and the sleep; records calls."""
    def __init__(self, responses):
        self.responses, self.urls, self.sleeps = list(responses), [], []

    def http(self, url):
        self.urls.append(url)
        return self.responses.pop(0)

    def install(self, test):
        old = edjoin._http_get, edjoin._sleep, edjoin._last[0]
        edjoin._http_get, edjoin._sleep, edjoin._last[0] = self.http, self.sleeps.append, None
        test.addCleanup(lambda: (setattr(edjoin, "_http_get", old[0]), setattr(edjoin, "_sleep", old[1]),
                                 edjoin._last.__setitem__(0, old[2])))
        return self


class Save(unittest.TestCase):
    def test_fixture_parses_and_saves(self):
        conn = memdb()
        self.assertEqual(edjoin.load_file(conn, LISTING, today="2026-11-16"), (50, 0))
        r = conn.execute("SELECT * FROM jobs WHERE posting_id = 2270705").fetchone()
        self.assertEqual((r["title"][:3], r["district_raw"], r["city"], r["county"], r["category"]),
                         ("ECE", "San Juan Unified School District", "Carmichael", "Sacramento", "Teacher - Other"))
        self.assertEqual((r["posted_on"], r["openings"], r["location_raw"]), ("2026-11-16", 0, "Marvin Marshall"))
        self.assertEqual(r["url"], "https://www.edjoin.org/Home/JobPosting/2270705")
        self.assertIsNone(r["edjoin_district_id"])
        self.assertEqual(json.loads(r["raw_json"])["postingID"], 2270705)

    def test_dates(self):
        v = edjoin._row(row(1, displayUntil=ms(2026, 11, 20, 7, 55)), "t")  # 23:55 PST on the 19th
        self.assertEqual((v["posted_on"], v["deadline"]), ("2026-11-13", "2026-11-19"))
        self.assertEqual(edjoin._row(row(1, displayUntil=ms(2026, 7, 1, 6, 59)), "t")["deadline"], "2026-06-30")  # PDT
        self.assertIsNone(edjoin._row(row(1, postingDate="/Date(-62135568000000)/"), "t")["posted_on"])
        self.assertIsNone(edjoin._row(row(1, displayFlag="Until Filled"), "t")["deadline"])
        self.assertIsNone(edjoin._row(row(1, displayFlag="Continuous"), "t")["deadline"])
        self.assertIsNone(edjoin._row(row(1, displayUntil="/Date(-62135568000000)/"), "t")["deadline"])

    def test_second_save_keeps_first_seen_and_matcher_fields(self):
        conn = memdb()
        edjoin.save_listings(conn, [row(5, positionTitle="Teacher @ Elder Creek ELEM-1")], today="2026-11-01")
        conn.execute("UPDATE jobs SET cds_code = NULL, district_code = '1234567' WHERE posting_id = 5")
        conn.execute("UPDATE jobs SET location_raw = 'Detail Place' WHERE posting_id = 5")
        # a title that now names no site must not blank a stored location_raw
        self.assertEqual(edjoin.save_listings(conn, [row(5, positionTitle="Teacher v2")], today="2026-11-09"), (0, 1))
        r = conn.execute("SELECT * FROM jobs").fetchall()
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["first_seen"], r[0]["last_seen"], r[0]["title"]), ("2026-11-01", "2026-11-09", "Teacher v2"))
        self.assertEqual((r[0]["district_code"], r[0]["location_raw"]), ("1234567", "Detail Place"))

    def test_matcher_cds_code_survives(self):
        conn = memdb()
        conn.execute("INSERT INTO schools (cds_code, district_code, school_name, first_year, last_year) "
                     "VALUES ('12345671234567', '1234567', 'S', 'a', 'a')")
        edjoin.save_listings(conn, [row(5)], today="2026-11-01")
        conn.execute("UPDATE jobs SET cds_code = '12345671234567'")
        edjoin.save_listings(conn, [row(5)], today="2026-11-02")
        self.assertEqual(conn.execute("SELECT cds_code FROM jobs").fetchone()[0], "12345671234567")

    def test_sql_text_is_bound(self):
        conn = memdb()
        edjoin.save_listings(conn, [row(7, positionTitle="x'); DROP TABLE jobs;--")], today="t")
        self.assertEqual(conn.execute("SELECT title FROM jobs").fetchone()[0], "x'); DROP TABLE jobs;--")


class Site(unittest.TestCase):
    def test_examples(self):
        f = edjoin.site_from_title
        self.assertEqual(f("Teacher, Elementary, 3rd Grade @ Theodore Judah ELEM-114"), "Theodore Judah")
        self.assertEqual(f("ECE Content Specialist - Education at Marvin Marshall (PC #: 32158 / Job ID#: 8859)"),
                         "Marvin Marshall")
        self.assertEqual(f("RESOURCE TEACHER - SPECIAL EDUCATION - MILD/ MOD (Carroll Elementary School)"),
                         "Carroll Elementary School")
        for t in ("X (Special Education Department)", "X (PC #: 32158)", "X (2026-27 School Year)",
                  "Augmentative Specialist @ Special Education - DEPT-62.1", "3rd Grade Teacher", "", None):
            self.assertIsNone(f(t), t)

    def test_fixture_never_yields_a_non_site(self):
        for r in json.loads(LISTING.read_text())["data"]:
            s = edjoin.site_from_title(r["positionTitle"])
            self.assertTrue(s is None or s in r["positionTitle"])


class Detail(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(edjoin.parse_detail(DETAIL.read_text(encoding="utf-8")), "Theodore Judah Elementary")
        self.assertIsNone(edjoin.parse_detail("<html>no block</html>"))

    def test_fetch_detail_url_rules(self):
        fake = Fake([(200, DETAIL.read_bytes())]).install(self)
        self.assertEqual(edjoin.fetch_detail(2295141), "Theodore Judah Elementary")
        self.assertEqual(fake.urls, ["https://www.edjoin.org/Home/JobPosting/2295141"])
        for bad in ("2295141", -1, True, "../x"):
            with self.assertRaises(ValueError):
                edjoin.fetch_detail(bad)

    def test_non_edjoin_url_rejected(self):
        fake = Fake([]).install(self)
        for u in ("https://evil.example/Home/JobPosting/1", "http://www.edjoin.org/Home/JobPosting/1",
                  "https://www.edjoin.org/Home/JobPosting/1/../x", "https://www.edjoin.org.evil.example/Home/LoadJobs?a=1"):
            with self.assertRaises(ValueError):
                edjoin._get(u)
        self.assertEqual(fake.urls, [])


class Fetch(unittest.TestCase):
    def test_query_has_all_19_params(self):
        q = edjoin._query(34, 31, 2)
        self.assertEqual(len(q.split("?")[1].split("&")), 19)
        self.assertIn("regions=34&jobTypes=1,2,3,4,48,5,46,6,7,8,9,10,11,55,56,63,64&days=31", q)

    def test_stops_at_total_pages_and_delays(self):
        fake = Fake([(200, page([row(1)], pages=2)), (200, page([row(2)], pages=2)), (200, page([row(3)]))]).install(self)
        seen = []
        rows = edjoin.fetch_listings([34], on_progress=lambda *a: seen.append(a))
        self.assertEqual([r["postingID"] for r in rows], [1, 2])
        self.assertEqual(len(fake.urls), 2)
        self.assertEqual(len(fake.sleeps), 1)  # between the two requests, not before the first
        self.assertTrue(0 < fake.sleeps[0] <= edjoin.DELAY)
        self.assertEqual(seen[-1][0], 2)

    def test_delay_between_counties_too(self):
        fake = Fake([(200, page([row(1)])), (200, page([row(2)]))]).install(self)
        edjoin.fetch_listings([34, 58])
        self.assertEqual(len(fake.sleeps), 1)

    def test_page_cap(self):
        fake = Fake([(200, page([row(i)], pages=999)) for i in range(1, 50)]).install(self)
        rows = edjoin.fetch_listings([34])
        self.assertEqual(len(fake.urls), edjoin.MAX_PAGES)
        self.assertEqual(len(rows), edjoin.MAX_PAGES)

    def test_limit(self):
        fake = Fake([(200, page([row(i) for i in range(1, 6)], pages=9))]).install(self)
        self.assertEqual(len(edjoin.fetch_listings([34], limit=3)), 3)
        self.assertEqual(len(fake.urls), 1)

    def test_429_raises_without_second_request(self):
        fake = Fake([(200, page([row(1)], pages=3)), (429, b""), (200, page([row(3)]))]).install(self)
        with self.assertRaises(edjoin.EdjoinRefused):
            edjoin.fetch_listings([34])
        self.assertEqual(len(fake.urls), 2)

    def test_status_errors(self):
        for status, exc in ((403, edjoin.EdjoinRefused), (500, edjoin.EdjoinServerError),
                            (503, edjoin.EdjoinServerError), (302, edjoin.EdjoinServerError)):
            fake = Fake([(status, b"")]).install(self)
            with self.assertRaises(exc):
                edjoin.fetch_listings([34])
            self.assertEqual(len(fake.urls), 1)

    def test_malformed_raises(self):
        for body in (b"<html>captcha</html>", b"[]", b'{"data": 1, "totalPages": 1, "totalRecords": 1}',
                     b'{"data": [{"postingID": "x", "positionTitle": "t"}], "totalPages": 1, "totalRecords": 1}',
                     b'{"data": [{"postingID": 1}], "totalPages": 1, "totalRecords": 1}', b"\xff\xfe"):
            Fake([(200, body)]).install(self)
            with self.assertRaises(edjoin.EdjoinBadResponse, msg=body):
                edjoin.fetch_listings([34])

    def test_user_agent_only(self):
        self.assertEqual(edjoin.USER_AGENT, "EdTrawl/0.1 (personal job-search tool)")


class Counties(unittest.TestCase):
    def test_ids(self):
        conn = memdb()
        conn.execute("INSERT INTO homes VALUES ('h', 'home', 1, 1, 't')")
        for i, county in enumerate(("Sacramento", "Yolo", "Atlantis", "Sacramento")):
            conn.execute("INSERT INTO schools (cds_code, district_code, county_name, school_name, first_year, last_year) "
                         "VALUES (?, '1234567', ?, 's', 'a', 'a')", (f"{i:014}", county))
            conn.execute("INSERT INTO commutes VALUES (?, 'h', 5, 1, 1, 'estimate', 't')", (f"{i:014}",))
        conn.execute("INSERT INTO schools (cds_code, district_code, county_name, school_name, first_year, last_year) "
                     "VALUES ('9' || substr('0000000000000', 1), '1234567', 'Fresno', 's', 'a', 'a')")  # no commute row
        self.assertEqual(edjoin.county_ids_in_range(conn, SimpleNamespace(home_key="h")), [34, 58])

    def test_table(self):
        self.assertEqual((edjoin.COUNTY_IDS["Alameda"], edjoin.COUNTY_IDS["Sacramento"], edjoin.COUNTY_IDS["Yuba"]),
                         (1, 34, 59))
        self.assertEqual(len(edjoin.COUNTY_IDS), 59)


if __name__ == "__main__":
    unittest.main()
