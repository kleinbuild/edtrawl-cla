import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import config
import db
import edjoin
import edtrawl
import ingest
import travel
import ui

FX = Path(__file__).parent / "tests" / "fixtures"
CDE, LISTING = str(FX / "cde_2025-26.csv"), str(FX / "edjoin_listing.json")
HOME = "38.577,-121.495"
ADDRESS = "1315 10th St, Sacramento CA"  # a sample typed address: must never be stored or logged


class FakeMatch:
    """Stands in for match.py, which another agent writes."""
    def __init__(self, unsure=0, detail=()):
        self.calls, self.detail, self.unsure = [], list(detail), unsure
        self.aside = 2  # listings currently set aside, as review() reports them

    def match_jobs(self, conn, cfg, limit=None, on_progress=None):
        self.calls.append("match_jobs")
        return {"school": 0, "district": 0, "unsure": self.unsure, "unmatched": 1, "llm_failed": False}

    def needs_detail(self, conn, cfg, limit=40):
        return self.detail

    def review(self, conn):
        return [{"district_raw": "Odd USD", "location_raw": "Odd Site", "jobs": self.aside,
                 "candidates": [("0123456", "Odd Unified", 0.8), ("0123457", "Even Unified", 0.7)]}]


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db, self.cfg = str(self.tmp / "t.db"), str(self.tmp / "c.toml")
        self.keys = []
        self.out, self.err = io.StringIO(), io.StringIO()
        self.match = FakeMatch()
        for p in (mock.patch.object(ui, "say", lambda key, **kw: self.keys.append((key, kw))),
                  mock.patch.object(ui, "progress", lambda *a: None),
                  mock.patch.object(ui, "ask", lambda key, **kw: kw.get("default")),
                  mock.patch.dict(sys.modules, {"match": self.match}),
                  mock.patch.object(edtrawl, "DATA", self.tmp / "data")):
            p.start()
            self.addCleanup(p.stop)

    def run_cli(self, *argv):
        self.keys.clear()
        with contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.err):
            code = edtrawl.main(["--db", self.db, "--config", self.cfg, "--plain", *argv])
        return code

    def names(self):
        return [k for k, _ in self.keys]

    def q(self, sql, *a):
        conn = db.connect(self.db)
        try:
            return [tuple(r) for r in conn.execute(sql, a)]
        finally:
            conn.close()

    def prepared(self):
        self.assertEqual(self.run_cli("ingest", "--file", CDE), 0)
        self.assertEqual(self.run_cli("home", HOME), 0)
        self.assertEqual(self.run_cli("commute"), 0)

    # ---- the commands ----

    def test_no_command_is_go_and_go_without_home_needs_a_terminal(self):
        with mock.patch.object(sys, "stdin", io.StringIO()):  # not a terminal, whatever runs the tests
            self.assertEqual(self.run_cli(), 1)
        self.assertEqual(self.names(), ["setup_needs_terminal"])

    def test_ingest_file(self):
        self.assertEqual(self.run_cli("ingest", "--file", CDE), 0)
        self.assertEqual(self.q("SELECT COUNT(*) FROM schools"), [(20,)])
        self.assertEqual(self.names(), ["schools_loaded"])

    def test_ingest_downloads_a_missing_year(self):
        def fake(year):
            path = self.tmp / f"{year}.csv"
            path.write_bytes(Path(CDE).read_bytes())
            return path
        with mock.patch.object(ingest, "download", fake) as d:
            self.assertEqual(self.run_cli("ingest", "--year", "2025-26"), 0)
        self.assertEqual(self.q("SELECT COUNT(*) FROM schools"), [(20,)])

    def test_ingest_download_failure(self):
        with mock.patch.object(ingest, "download", side_effect=OSError):
            self.assertEqual(self.run_cli("ingest"), 1)
        self.assertEqual(self.names(), ["err_schools_download"])

    def test_home_coordinates_zip_and_config(self):
        self.assertEqual(self.run_cli("home", HOME), 0)
        self.assertEqual(self.names(), ["home_saved"])
        self.assertEqual(self.q("SELECT home_key, label FROM homes"), [(HOME, "home")])
        self.assertEqual(config.load(self.cfg).home_key, HOME)
        self.run_cli("ingest", "--file", CDE)
        self.assertEqual(self.run_cli("home", "--zip", "95818"), 0)
        self.assertEqual(self.names(), ["home_saved", "home_zip_note"])
        self.assertEqual(self.run_cli("home", "95818"), 0)  # a bare ZIP works too

    def test_home_bad_input(self):
        self.assertEqual(self.run_cli("home", "hello"), 1)
        self.assertEqual(self.names(), ["err_home_unreadable"])
        self.assertEqual(self.run_cli("home", "10.0,-119.79"), 1)
        self.assertEqual(self.names(), ["err_outside_california"])
        self.assertEqual(self.run_cli("home", "--zip", "99999"), 1)
        self.assertEqual(self.names(), ["err_unknown_zip"])
        self.assertEqual(self.q("SELECT COUNT(*) FROM homes"), [(0,)])

    def test_home_address_asks_then_geocodes_once_and_stores_nothing(self):
        with mock.patch.object(travel, "geocode", return_value=(38.5766, -121.4944)) as g:
            self.assertEqual(self.run_cli("home", ADDRESS), 0)
        g.assert_called_once_with(ADDRESS)
        self.assertEqual(self.q("SELECT home_key FROM homes"), [("38.577,-121.494",)])
        for path in self.tmp.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"10th St", path.read_bytes())
        self.assertNotIn("10th St", self.out.getvalue() + self.err.getvalue())

    def test_home_address_declined_or_not_found(self):
        with mock.patch.object(travel, "geocode") as g, mock.patch.object(ui, "ask", lambda *a, **k: "n"):
            self.assertEqual(self.run_cli("home", ADDRESS), 1)
        g.assert_not_called()
        with mock.patch.object(travel, "geocode", return_value=None):
            self.assertEqual(self.run_cli("home", ADDRESS), 1)
        self.assertEqual(self.names(), ["err_address_not_found"])

    def test_commute(self):
        self.prepared()
        self.assertGreater(self.q("SELECT COUNT(*) FROM commutes")[0][0], 0)
        self.assertEqual(self.names(), ["drives_ready"])

    def test_commute_without_home(self):
        self.assertEqual(self.run_cli("commute"), 1)
        self.assertEqual(self.names(), ["err_no_home"])

    def test_fetch_from_file_matches_once_and_skips_posting_pages(self):
        self.prepared()
        self.match.detail = [1]
        with mock.patch.object(edjoin, "fetch_sites") as sites, mock.patch.object(edjoin, "fetch_listings") as live:
            self.assertEqual(self.run_cli("fetch", "--from-file", LISTING), 0)
        sites.assert_not_called()
        live.assert_not_called()
        self.assertGreater(self.q("SELECT COUNT(*) FROM jobs")[0][0], 0)
        self.assertEqual(self.match.calls, ["match_jobs"])

    def test_fetch_pipeline_order_and_second_match(self):
        self.prepared()
        order = []
        self.match.detail = [7]
        rows = edjoin._parse_page(Path(LISTING).read_bytes())[0]
        with mock.patch.object(edjoin, "fetch_listings", lambda ids, days, limit, on_progress: order.append(("list", days, limit)) or rows), \
                mock.patch.object(edjoin, "fetch_sites", lambda conn, ids, on_progress: order.append(("sites", ids)) or 1):
            self.match.aside = 0  # nothing set aside before this run; the run sets 2 aside
            self.match.match_jobs = lambda *a, **k: order.append("match") or setattr(self.match, "aside", 2) or {"unsure": 2, "llm_failed": True}
            self.assertEqual(self.run_cli("fetch", "--days", "7", "--limit", "5"), 0)
        self.assertEqual(order, [("list", 7, 5), "match", ("sites", [7]), "match"])
        self.assertGreater(self.q("SELECT COUNT(*) FROM jobs")[0][0], 0)
        self.assertEqual(self.names(), ["edjoin_notice", "fetch_done", "err_llm_unreachable", "match_set_aside"])

    def test_set_aside_is_announced_only_when_it_grew(self):
        self.prepared()
        self.match.unsure = 2  # two set aside, the same two as yesterday
        with mock.patch.object(edjoin, "fetch_listings", lambda *a, **k: edjoin._parse_page(Path(LISTING).read_bytes())[0]):
            self.run_cli("fetch")
        self.assertNotIn("match_set_aside", self.names())
        self.run_cli("match")  # asking for it by name always answers
        self.assertIn("match_set_aside", self.names())

    def test_partial_rows_are_saved_before_the_problem_is_reported(self):
        self.prepared()
        rows = edjoin._parse_page(Path(LISTING).read_bytes())[0][:3]
        err = edjoin.EdjoinServerError("edjoin answered HTTP 503")
        err.partial_rows = rows

        def failing(*a, **k):
            raise err
        with mock.patch.object(edjoin, "fetch_listings", failing):
            self.assertEqual(self.run_cli("fetch"), 1)
        self.assertEqual(self.q("SELECT COUNT(*) FROM jobs"), [(3,)])
        self.assertEqual(self.names()[-1], "err_edjoin_down")

    def test_fetch_without_home(self):
        self.assertEqual(self.run_cli("fetch", "--from-file", LISTING), 1)
        self.assertEqual(self.names(), ["err_no_home"])

    def test_match_and_review(self):
        self.match.unsure = 3
        self.assertEqual(self.run_cli("match"), 0)
        self.assertEqual(self.names(), ["match_set_aside"])
        self.assertEqual(self.run_cli("match", "--review"), 0)
        self.assertRegex(self.out.getvalue(), r"Odd USD . Odd Site  \(2 jobs\)")
        self.assertIn("0123457  Even Unified  0.70", self.out.getvalue())

    def test_search_and_empty_states(self):
        self.prepared()
        self.run_cli("fetch", "--from-file", LISTING)
        conn = db.connect(self.db)
        code = conn.execute("SELECT cds_code, am_minutes FROM commutes ORDER BY am_minutes LIMIT 1").fetchone()
        conn.execute("UPDATE jobs SET cds_code = ? WHERE posting_id = (SELECT MIN(posting_id) FROM jobs)", (code[0],))
        conn.commit()
        conn.close()
        self.out.truncate(0)
        self.assertEqual(self.run_cli("search"), 0)
        self.assertIn("Number", self.out.getvalue())
        self.assertEqual(self.names(), ["search_header"])
        self.assertEqual(self.run_cli("search", "--max-commute", "1"), 0)
        self.assertEqual(self.names()[0], "empty_in_range")
        self.assertEqual(self.names()[1], "empty_nearly")
        self.assertEqual(self.keys[1][1]["minutes"] % 5, 0)
        self.assertEqual(self.run_cli("search", "--status", "kept"), 0)
        self.assertEqual(self.names(), ["empty_filtered"])  # a filter emptied it, not a lack of jobs nearby

    def test_flags_after_the_command(self):
        self.assertEqual(self.run_cli("search", "--plain", "--no-emoji"), 0)

    # ---- errors ----

    def test_mapped_exceptions(self):
        cases = [
            (travel.GeocoderUnavailable("x"), "err_geocoder_unreachable"),
            (travel.RoutingUnavailable("x"), "err_routing_unreachable_none"),  # no saved drive times in this empty database
            (travel.OutsideCalifornia("x"), "err_outside_california"),
            (travel.UnknownZip("x"), "err_unknown_zip"),
            (travel.NoHome("x"), "err_no_home"),
            (edjoin.EdjoinRefused(403), "err_edjoin_refused"),
            (edjoin.EdjoinRefused(429), "err_edjoin_busy"),
            (edjoin.EdjoinServerError("edjoin answered HTTP 503"), "err_edjoin_down"),
            (edjoin.EdjoinBadResponse("x"), "err_edjoin_down"),
            (urllib.error.URLError("boom"), "err_offline"),
            (ConnectionResetError(), "err_offline"),
            (TimeoutError(), "err_offline"),
        ]
        for exc, key in cases:
            with self.subTest(exc=repr(exc)), mock.patch.object(travel, "update_commutes", side_effect=exc):
                self.out.truncate(0), self.err.truncate(0)
                self.assertEqual(self.run_cli("commute"), 1)
                self.assertEqual(self.names(), [key])
                self.assertNotIn("Traceback", self.out.getvalue() + self.err.getvalue())
        self.assertFalse((self.tmp / "edtrawl-error.log").exists())

    def test_ctrl_c(self):
        with mock.patch.object(travel, "update_commutes", side_effect=KeyboardInterrupt):
            self.assertEqual(self.run_cli("commute"), 130)
        self.assertEqual(self.names(), ["stopped"])

    def test_unexpected_is_logged_without_the_address(self):
        with mock.patch.object(travel, "geocode", side_effect=RuntimeError(f"bad {ADDRESS}")):
            self.assertEqual(self.run_cli("home", ADDRESS), 1)
        self.assertEqual(self.names(), ["err_unexpected"])
        log = (self.tmp / "edtrawl-error.log").read_text()
        self.assertIn("RuntimeError", log)
        self.assertIn("cmd_home", log)
        self.assertNotIn("10th St", log)
        self.assertNotIn("Traceback", self.out.getvalue() + self.err.getvalue())
        self.assertIn("edtrawl-error.log", self.keys[0][1]["path"])

    def test_log_that_cannot_be_written_gives_one_plain_line(self):
        self.assertIsNone(edtrawl._log_unexpected(RuntimeError("x"), "/proc/no/such/dir/t.db"))
        with mock.patch.object(travel, "update_commutes", side_effect=RuntimeError), \
                mock.patch.object(edtrawl, "_log_unexpected", lambda e, p: None):
            self.assertEqual(self.run_cli("commute"), 1)
        self.assertEqual(self.names(), ["err_unexpected_nolog"])
        self.assertNotIn("log", ui.COPY["err_unexpected_nolog"].replace("a note of", ""))

    def test_settings_file_problems_each_get_their_own_message(self):
        cases = [("bogus = 1\n", "err_config_unknown", "bogus"),
                 ('routing = "google"\n', "err_config_value", "routing"),
                 ('radius_miles = "far"\n', "err_config_value", "radius_miles"),
                 ("radius_miles = = 3\n", "err_config_broken", None)]
        for text, key, setting in cases:
            Path(self.cfg).write_text(text)
            self.assertEqual(self.run_cli("logbook"), 1, text)
            self.assertEqual(self.names(), [key], text)
            self.assertEqual(self.keys[0][1]["path"], self.cfg)
            if setting:
                self.assertEqual(self.keys[0][1]["setting"], setting)
            else:
                self.assertIn("line 1", self.keys[0][1]["where"])
        self.assertFalse((self.tmp / "edtrawl-error.log").exists())

    def test_unreadable_and_locked_databases(self):
        Path(self.db).write_bytes(b"this is not a database" * 100)
        self.assertEqual(self.run_cli("logbook"), 1)
        self.assertEqual(self.names(), ["err_db_unreadable"])
        args = SimpleNamespace(db="x.db")
        self.assertEqual(edtrawl._speak(sqlite3.OperationalError("database is locked"), args)[0], "err_db_busy")
        self.assertIsNone(edtrawl._speak(sqlite3.OperationalError("no such column: x"), args))

    def test_missing_file_is_not_called_offline(self):
        self.assertEqual(self.run_cli("ingest", "--file", str(self.tmp / "nope.csv")), 1)
        self.assertEqual(self.names(), ["err_file_not_found"])


if __name__ == "__main__":
    unittest.main()
