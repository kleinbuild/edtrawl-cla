import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import config
import db
import travel

FIX = Path(__file__).parent / "tests" / "fixtures"
HOME = (38.577, -121.495)  # California State Capitol
# (cds, county, locale, lat, lng): values copied from tests/fixtures/cde_2025-26.csv
SCHOOLS = [
    ("34674396034326", "Sacramento", "11 - City, Large", 38.56709008, -121.49661817),   # William Land
    ("34674390101907", "Sacramento", "11 - City, Large", 38.56731508, -121.50136317),   # The MET
    ("34674390133777", "Sacramento", "11 - City, Large", 38.58246408, -121.48108317),   # Washington
    ("34674396034037", "Sacramento", "11 - City, Large", 38.56222808, -121.51274117),   # Leataata Floyd
    ("34674134835302", "Sacramento", "31 - Town, Fringe", 38.15464903, -121.69666615),  # Rio Vista High, ~31 mi
]
WLAND = SCHOOLS[0][0]


def make(tmp):
    conn = db.connect(":memory:")
    db.init_db(conn)
    for cds, county, locale, lat, lng in SCHOOLS:
        conn.execute("INSERT INTO schools (cds_code, district_code, county_name, school_name, status, locale, lat, lng, "
                     "first_year, last_year) VALUES (?, ?, ?, 'S', 'Active', ?, ?, ?, '2025-26', '2025-26')",
                     (cds, cds[:7], county, locale, lat, lng))
    path = str(Path(tmp) / "config.toml")
    cfg = config.load(path)
    travel.set_home(conn, cfg, *HOME, path=path)
    return conn, cfg, path


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.conn, self.cfg, self.path = make(self._t.name)

    def rows(self):
        return {r["cds_code"]: r for r in self.conn.execute("SELECT * FROM commutes")}


class Geometry(unittest.TestCase):
    def test_haversine_known_pair(self):  # Sacramento to San Francisco city hall is about 74.6 miles (great circle)
        self.assertAlmostEqual(travel.haversine_miles(38.5767, -121.4934, 37.7793, -122.4193), 74.6, delta=0.5)

    def test_estimate_and_rush(self):
        self.assertGreater(travel.estimate(10, "11 - City"), travel.estimate(1, "11 - City"))
        self.assertGreater(travel.estimate(10, "11 - City"), travel.estimate(10, "43 - Rural"))
        cfg = config.Config()
        self.assertAlmostEqual(travel.rush("Los Angeles", "am", cfg), 1 + 0.75 * 0.59)
        self.assertAlmostEqual(travel.rush("Modoc", "pm", cfg), 1 + 1.2 * 0.10)

    def test_geocode_parses_saved_response(self):
        saved = json.loads((FIX / "census_capitol.json").read_text())
        with mock.patch.object(travel, "_http_json", return_value=saved):
            lat, lng = travel.geocode("1315 10th St, Sacramento, CA 95814")
        self.assertAlmostEqual(lat, 38.577, places=2)
        self.assertAlmostEqual(lng, -121.495, places=2)
        with mock.patch.object(travel, "_http_json", return_value={"result": {"addressMatches": []}}):
            self.assertIsNone(travel.geocode("nowhere"))

    def test_geocode_failure_hides_address(self):
        with mock.patch.object(travel, "_http_json", side_effect=OSError("boom 1315 10th St")):
            with self.assertRaises(travel.GeocoderUnavailable) as cm:
                travel.geocode("1315 10th St")
        self.assertNotIn("10th", str(cm.exception))


class Home(Base):
    def test_set_home_rounds_and_rejects(self):
        self.assertEqual(self.cfg.home_key, "38.577,-121.495")
        self.assertIn("38.577,-121.495", Path(self.path).read_text())
        with self.assertRaises(travel.OutsideCalifornia):
            travel.set_home(self.conn, self.cfg, 40.7, -74.0, path=self.path)

    def test_zip_centroid(self):
        self.conn.execute("UPDATE schools SET zip = '95818' WHERE cds_code IN (?, ?)", (SCHOOLS[0][0], SCHOOLS[1][0]))
        lat, lng = travel.zip_centroid(self.conn, "95818")
        self.assertAlmostEqual(lat, (SCHOOLS[0][3] + SCHOOLS[1][3]) / 2)
        with self.assertRaises(travel.UnknownZip):
            travel.zip_centroid(self.conn, "00000")


class Radius(Base):
    def test_radius_and_coordinates(self):
        self.cfg.radius_miles = 31.2
        self.assertEqual(len(travel.schools_in_radius(self.conn, self.cfg)), 5)
        self.cfg.radius_miles = 31.1  # Rio Vista (31.16 mi) is just outside
        self.assertEqual(len(travel.schools_in_radius(self.conn, self.cfg)), 4)
        self.conn.execute("UPDATE schools SET lat = NULL WHERE cds_code = ?", (WLAND,))
        self.assertEqual(len(travel.schools_in_radius(self.conn, self.cfg)), 3)
        self.conn.execute("UPDATE schools SET lat_override = 38.57, lng_override = -121.49 WHERE cds_code = ?", (WLAND,))
        self.assertEqual(len(travel.schools_in_radius(self.conn, self.cfg)), 4)
        self.conn.execute("UPDATE schools SET status = 'Closed' WHERE cds_code = ?", (WLAND,))
        self.assertEqual(len(travel.schools_in_radius(self.conn, self.cfg)), 3)


class Cache(Base):
    def test_fill_then_skip_then_stale(self):
        self.cfg.radius_miles = 5
        self.assertEqual(travel.update_commutes(self.conn, self.cfg)["computed"], 4)
        self.assertEqual(travel.update_commutes(self.conn, self.cfg)["computed"], 0)
        self.assertEqual({r["provider"] for r in self.rows().values()}, {"estimate"})
        later = date.today() + timedelta(days=91)
        self.assertEqual(travel.update_commutes(self.conn, self.cfg, today=later)["computed"], 4)

    def test_rush_applied_and_progress(self):
        self.cfg.radius_miles = 5
        calls = []
        travel.update_commutes(self.conn, self.cfg, on_progress=lambda *a: calls.append(a))
        r = self.rows()[WLAND]
        free = travel.estimate(r["straight_miles"], "11 - City")
        self.assertAlmostEqual(r["am_minutes"], free * travel.rush("Sacramento", "am", self.cfg))
        self.assertEqual(calls[-1], (4, 4, "commutes"))

    def test_provider_upgrade_and_keep(self):
        self.cfg.radius_miles = 5
        travel.update_commutes(self.conn, self.cfg)
        self.cfg.routing = "osrm"
        fake = lambda home, schools, cfg: [(10.0, 12.0)] * len(schools)
        with mock.patch.object(travel, "osrm", fake):
            self.assertEqual(travel.update_commutes(self.conn, self.cfg)["computed"], 4)  # estimate rows upgraded
            self.assertEqual({r["provider"] for r in self.rows().values()}, {"osrm"})
            self.cfg.routing = "estimate"
            self.assertEqual(travel.update_commutes(self.conn, self.cfg)["computed"], 0)  # osrm rows kept

    def test_osrm_failure_stops_and_writes_nothing(self):
        self.cfg.radius_miles, self.cfg.routing = 5, "osrm"
        with mock.patch.object(travel, "_osrm_table", side_effect=travel.RoutingUnavailable("x")):
            with self.assertRaises(travel.RoutingUnavailable):
                travel.update_commutes(self.conn, self.cfg)
        self.assertEqual(self.rows(), {})

    def test_new_home_recomputes_and_shrunk_radius_deletes(self):
        self.cfg.radius_miles = 5
        travel.update_commutes(self.conn, self.cfg)
        travel.set_home(self.conn, self.cfg, 38.57, -121.50, path=self.path)
        self.assertEqual(travel.update_commutes(self.conn, self.cfg)["computed"], 4)
        self.cfg.radius_miles = 0.8
        out = travel.update_commutes(self.conn, self.cfg)
        n = self.conn.execute("SELECT COUNT(*) FROM commutes WHERE home_key = ?", (self.cfg.home_key,)).fetchone()[0]
        self.assertEqual((out["removed"], n), (4 - out["in_range"], out["in_range"]))
        self.assertLess(n, 4)

    def test_osrm_batches_and_url(self):
        urls = []
        def fake(url):
            urls.append(url)
            n = url.split("/driving/")[1].split("?")[0].count(";")  # destinations count = coordinates - 1
            return {"code": "Ok", "durations": [[600.0] * n] if "sources=0" in url else [[1200.0]] * n}
        sch = [{"lat": 38.5, "lng": -121.4}] * 3
        with mock.patch.object(travel, "_http_json", fake), mock.patch.object(travel, "OSRM_PAUSE", 0):
            out = travel.osrm(HOME, sch, config.Config())
        self.assertEqual(out, [(10.0, 20.0)] * 3)
        self.assertEqual(len(urls), 2)
        self.assertIn("/driving/-121.495,38.577;", urls[0])  # longitude first


class Drives(Base):
    def setUp(self):
        super().setUp()
        for cds in (SCHOOLS[0][0], SCHOOLS[1][0]):
            self.conn.execute("INSERT INTO commutes VALUES (?, ?, 1, 20, 20, 'estimate', '2026-11-16')", (cds, self.cfg.home_key))

    def factors(self):
        return tuple(self.conn.execute("SELECT factor_am, factor_pm FROM homes WHERE home_key = ?", (self.cfg.home_key,)).fetchone())

    def test_factors(self):
        travel.record_drive(self.conn, self.cfg, SCHOOLS[0][0], 30, "am")
        self.assertEqual(self.factors(), (1.5, 1.5))  # pm borrows am
        travel.record_drive(self.conn, self.cfg, SCHOOLS[0][0], 40, "pm")
        self.assertEqual(self.factors(), (1.5, 2.0))
        travel.record_drive(self.conn, self.cfg, SCHOOLS[1][0], 100, "am")  # ratio 5 clamps to 2.0; median(1.5, 5) = 3.25 -> 2.0
        self.assertEqual(self.factors()[0], 2.0)

    def test_no_commute(self):
        with self.assertRaises(travel.NoCommute):
            travel.record_drive(self.conn, self.cfg, SCHOOLS[4][0], 30, "am")


if __name__ == "__main__":
    unittest.main()
