import builtins
import contextlib
import os
import urllib.error
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config
import db
import edjoin
import edtrawl
import flows
import ingest
import travel
import ui

FX = Path(__file__).parent / "tests" / "fixtures"
ROWS = edjoin._parse_page((FX / "edjoin_listing.json").read_bytes())[0]
ADDRESS = "1315 10th St, Sacramento CA"


class TTY(io.StringIO):
    def isatty(self):
        return True


class Base(unittest.TestCase):
    """A temp directory, every network function replaced, a scripted keyboard."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db, self.cfg = str(self.tmp / "t.db"), str(self.tmp / "c.toml")
        self.downloads, self.opened, self.geocoded = [], [], []
        self.keys = iter(())
        self.tty = True
        for p in (mock.patch.object(builtins, "input", self.fake_input),
                  mock.patch.object(ui, "launcher", lambda: "python"),
                  mock.patch.object(edtrawl, "DATA", self.tmp / "data"),
                  mock.patch.object(ingest, "download", self.download),
                  mock.patch.object(travel, "geocode", self.geocode),
                  mock.patch.object(travel, "_osrm_table", side_effect=AssertionError("no network")),
                  mock.patch.object(edjoin, "fetch_listings", lambda ids, days, limit, on_progress=None: ROWS),
                  mock.patch.object(edjoin, "fetch_sites", lambda *a, **k: 0),
                  mock.patch("webbrowser.open", lambda url: self.opened.append(url) or True)):
            p.start()
            self.addCleanup(p.stop)

    def fake_input(self, prompt=""):
        try:
            key = next(self.keys)
        except StopIteration:
            raise EOFError
        if isinstance(key, BaseException):
            raise key
        return key

    def download(self, year):
        self.downloads.append(year)
        path = self.tmp / f"dl_{year}.csv"
        path.write_bytes((FX / f"cde_{year}.csv").read_bytes())
        return path

    def geocode(self, address):
        self.geocoded.append(address)
        return (38.5766, -121.4944)

    def run_cli(self, *argv, keys=()):
        self.keys = iter(keys)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(sys, "stdin", TTY() if self.tty else io.StringIO()):
            code = edtrawl.main(["--db", self.db, "--config", self.cfg, "--plain", *argv])
        self.out = out.getvalue()
        self.flat = " ".join(self.out.split())  # wrapped lines joined, for matching sentences
        return code

    def q(self, sql, *a):
        conn = db.connect(self.db)
        try:
            return [tuple(r) for r in conn.execute(sql, a)]
        finally:
            conn.close()

    def add_jobs(self, n):
        """n more unmarked jobs at the nearby Washington school, to fill several hands."""
        conn = sqlite3.connect(self.db)
        code = conn.execute("SELECT cds_code FROM schools WHERE school_name LIKE 'Washington%'").fetchone()[0]
        for i in range(n):
            conn.execute("INSERT INTO jobs (posting_id, title, district_raw, district_code, cds_code, url, first_seen, "
                         "last_seen) VALUES (?, ?, 'x', ?, ?, ?, '2026-11-16', '2026-11-16')",
                         (9000 + i, f"Extra {i}", code[:7], code, f"https://www.edjoin.org/Home/JobPosting/{9000 + i}"))
        conn.commit()
        conn.close()

    def first_run(self, *keys):
        return self.run_cli(keys=("95814", "", "", "") + keys)  # ZIP, radius 20, offline, skip the known drive


class Setup(Base):
    def test_zip_home_on_an_empty_database(self):
        self.assertEqual(self.first_run("t", "t"), 0)
        self.assertEqual(self.downloads, ["2025-26", "2024-25"])  # schools first, both years
        for step in ("Step 1 of 4", "Step 2 of 4", "Step 3 of 4", "Step 4 of 4"):
            self.assertIn(step, self.out)
        self.assertIn("public schools in 1 district", self.out)
        self.assertIn("The nearest is", self.out)
        self.assertIn("1 of 6", self.out)
        self.assertEqual(self.q("SELECT COUNT(DISTINCT academic_year) FROM school_years"), [(2,)])
        self.assertEqual(config.load(self.cfg).home_key, self.q("SELECT home_key FROM homes")[0][0])

    def test_rerun_skips_finished_steps(self):
        self.first_run()
        self.downloads.clear()
        self.assertEqual(self.run_cli("setup", keys=()), 0)
        self.assertEqual(self.downloads, [])
        for step in ("Step 1", "Step 2", "Step 3"):
            self.assertNotIn(step, self.out)
        self.assertIn("Setup is done.", self.out)

    def test_geocoder_failure_stays_at_the_home_question(self):
        calls = []

        def failing(address):
            calls.append(address)
            raise travel.GeocoderUnavailable("down")
        with mock.patch.object(travel, "geocode", failing):
            self.assertEqual(self.run_cli(keys=(ADDRESS, "y", "95814", "", "", "")), 0)
        self.assertEqual(len(calls), 1)
        self.assertIn("Try just your ZIP code; that needs no internet.", self.out)
        self.assertNotIn("Traceback", self.out)
        self.assertEqual(self.out.count("Where is home?"), 2)  # asked again
        self.assertTrue(config.load(self.cfg).home_key)

    def test_address_is_never_stored_or_echoed(self):
        self.run_cli(keys=(ADDRESS, "y", "", "", "", "k"))
        self.assertEqual(self.geocoded, [ADDRESS])
        self.assertEqual(self.q("SELECT home_key FROM homes"), [("38.577,-121.494",)])
        for path in self.tmp.rglob("*"):
            if path.is_file() and path.suffix not in (".csv",):
                self.assertNotIn(b"10th St", path.read_bytes(), path.name)
        self.assertNotIn("10th St", self.out)

    def test_declining_the_notice_sends_nothing_and_asks_again(self):
        self.run_cli(keys=(ADDRESS, "n", "95814", "", "", ""))
        self.assertEqual(self.geocoded, [])
        self.assertIn("Nothing was sent.", self.out)

    def test_known_drive_in_setup(self):
        self.run_cli(keys=("95814", "", "", "Washington", "12"))
        self.assertEqual(self.q("SELECT COUNT(*), MIN(minutes) FROM known_drives"), [(1, 12.0)])
        self.assertRegex(self.flat, r"(typical school near you went from ~\d+ to ~\d+ min|already close)")

    def test_no_terminal_no_home(self):
        self.tty = False
        self.assertEqual(self.run_cli(), 1)
        self.assertIn("needs a terminal window", self.out)


class Session(Base):
    def setUp(self):
        super().setUp()
        self.first_run("q")  # set up, then quit on the first card

    def test_quit_midway_marks_nothing_and_says_how_many_remain(self):
        self.assertIn("Stopping here: nothing marked. The other 6 jobs", self.flat)
        self.assertEqual(self.q("SELECT COUNT(*) FROM job_marks"), [(0,)])

    def test_keep_toss_and_end_line(self):
        self.assertEqual(self.run_cli("go", keys="ktssss"), 0)
        self.assertEqual(self.q("SELECT status FROM job_marks ORDER BY status"), [("kept",), ("tossed",)])
        self.assertIn("That's the whole catch: kept 1, tossed 1, skipped 4.", self.out)

    def test_ctrl_c_saves_marks_so_far_and_exits_130(self):
        self.assertEqual(self.run_cli("go", keys=("k", "t", KeyboardInterrupt())), 130)
        self.assertEqual(self.q("SELECT COUNT(*) FROM job_marks"), [(2,)])
        self.assertIn("Stopping here: kept 1, tossed 1. The other 4 jobs", self.flat)

    def test_first_keep_line_once_across_sessions(self):
        self.run_cli("go", keys="k")
        self.assertIn("Your first keeper.", self.out)
        self.run_cli("go", keys="k")
        self.assertNotIn("Your first keeper.", self.out)

    def test_more_shows_the_school_card_and_returns_to_the_same_card(self):
        # card 4 of 6 is the one with a school; skip three, then ask for more
        self.run_cli("go", keys="sssmq")
        self.assertIn("Washington Elementary", self.out)
        self.assertIn("California Department of Education", self.out)  # the school card's source line
        self.assertEqual(self.out.count("4 of 6"), 2)

    def test_district_wide_card_does_not_offer_more(self):
        self.run_cli("go", keys="q")
        card = self.out.split("1 of 6")[1].split("[q]uit")[0]
        self.assertNotIn("more about the school", card)

    def test_open_says_so_and_stays_on_the_card(self):
        self.run_cli("go", keys="oq")
        self.assertEqual(len(self.opened), 1)
        self.assertIn("Opened the posting in your browser.", self.out)
        self.assertEqual(self.out.count("1 of 6"), 1)

    def test_nothing_new_is_a_proper_end(self):
        self.run_cli("go", keys="kttttt")
        self.run_cli("go", keys="")
        self.assertIn("Nothing new since earlier today. Your 1 keeper is still open.", self.flat)

    def test_empty_when_no_keepers(self):
        self.run_cli("go", keys="tttttt")
        self.run_cli("go", keys="")
        self.assertIn("Nothing new since earlier today, so you're done for today.", self.flat)

    def test_non_terminal_prints_the_list_and_never_waits(self):
        self.tty = False
        with mock.patch.object(builtins, "input", side_effect=AssertionError("blocked")):
            self.assertEqual(self.run_cli("go"), 0)
        self.assertIn("Number", self.out)
        self.assertIn("run this in a terminal window", self.out)

    def test_marked_and_unmarked_come_back(self):
        self.run_cli("go", keys="kt")  # skip the rest implicitly (EOF gives skip)
        self.run_cli("go", keys="q")
        self.assertIn("1 of 4", self.out)  # the two marked are gone, the four skipped return

    def test_nearly_is_not_needed_when_nothing_is_near(self):
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM job_marks")
        conn.execute("DELETE FROM jobs")
        conn.commit()
        conn.close()
        with mock.patch.object(edjoin, "fetch_listings", lambda *a, **k: []):
            self.run_cli("go", keys="")
        self.assertIn("No teaching jobs are posted within 20 miles", self.flat)


class SmallCommands(Base):
    def setUp(self):
        super().setUp()
        self.first_run(*"kkkkkk")  # everything kept

    def test_keepers_lists_with_hint_and_marks_closed(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE jobs SET deadline = '2020-01-01' WHERE posting_id = (SELECT MIN(posting_id) FROM jobs "
                     "WHERE posting_id IN (SELECT posting_id FROM job_marks))")
        conn.commit()
        conn.close()
        self.run_cli("keepers")
        self.assertIn("Keepers: 6 jobs, soonest deadline first", self.out)
        self.assertIn("closed", self.out.splitlines()[-3] + self.out.splitlines()[-2])  # closed ones sort last
        self.assertIn("python edtrawl.py applied ", self.out)

    def test_applied_unknown_number(self):
        self.assertEqual(self.run_cli("applied", "12"), 1)
        self.assertIn("I don't have a job numbered 12.", self.out)

    def test_first_application_line_once_across_two_commands(self):
        ids = [r[0] for r in self.q("SELECT posting_id FROM job_marks ORDER BY posting_id")]
        self.run_cli("applied", str(ids[0]))
        self.assertIn("First one in the logbook.", self.out)
        self.assertIn("Marked as applied:", self.out)
        self.run_cli("applied", str(ids[1]))
        self.assertNotIn("First one in the logbook.", self.out)
        self.assertEqual(self.q("SELECT COUNT(*) FROM job_marks WHERE status = 'applied'"), [(2,)])

    def test_logbook(self):
        self.run_cli("applied", str(self.q("SELECT MIN(posting_id) FROM job_marks")[0][0]))
        self.run_cli("logbook")
        self.assertIn("This week: looked at 6, kept 6, applied to 1.", self.out)
        self.assertRegex(self.out, r"Since \w+ \d+: looked at 6")
        self.assertRegex(self.flat, r"applied .* - Sacramento")

    def test_logbook_empty(self):
        self.q("SELECT 1")
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM job_marks")
        conn.commit()
        conn.close()
        self.run_cli("logbook")
        self.assertIn("Nothing in the logbook yet.", self.out)

    def test_school_by_name_and_by_code_and_not_found(self):
        self.run_cli("school", "Washington")
        self.assertIn("Washington Elementary", self.out)
        self.assertIn("Students", self.out)
        code = self.q("SELECT cds_code FROM schools WHERE school_name LIKE 'Washington%' LIMIT 1")[0][0]
        self.run_cli("school", code)
        self.assertIn("Washington Elementary", self.out)
        self.assertEqual(self.run_cli("school", "Nonesuch"), 1)
        self.assertIn('I couldn\'t find a school called "Nonesuch"', self.out)

    def test_school_with_several_matches_asks_which(self):
        self.run_cli("school", "Elementary", keys=("2",))
        self.assertIn('More than one school matches "Elementary"', self.out)
        self.assertIn("[2]", self.out)
        self.assertIn("Grades", self.out)

    def test_drove_updates_the_factor_and_shows_before_and_after(self):
        before = self.q("SELECT factor_am FROM homes")[0][0]
        self.assertEqual(self.run_cli("drove", "Washington", "30"), 0)
        self.assertNotEqual(self.q("SELECT factor_am FROM homes")[0][0], before)
        self.assertRegex(self.flat, r"you said 30 min, and I'd estimated ~\d+. I've scaled every morning estimate by the same amount, so the typical school near you went from ~\d+ to ~\d+ min")
        self.assertEqual(self.q("SELECT direction, minutes FROM known_drives"), [("am", 30.0)])

    def test_drove_pm_clamped_and_unchanged_and_bad_minutes(self):
        self.run_cli("drove", "Washington", "240", "--pm")
        self.assertIn("afternoon estimate", self.out)
        self.assertIn("as far as I allow", self.flat)
        self.assertEqual(self.run_cli("drove", "Washington", "500"), 1)
        self.assertIn("Type the minutes", self.out)
        modelled = self.q("SELECT am_minutes * (SELECT factor_am FROM homes) FROM commutes c JOIN schools s USING (cds_code) "
                          "WHERE school_name LIKE 'Washington%'")[0][0]
        self.run_cli("drove", "Washington", str(modelled))  # exactly what we already thought
        self.assertIn("already close", self.out)

    def test_review_stores_a_manual_choice(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO jobs (posting_id, title, district_raw, county, url, first_seen, last_seen) "
                     "VALUES (1, 'Teacher', 'Sacramento Cty Unfd', 'Sacramento', 'https://www.edjoin.org/Home/JobPosting/1', "
                     "'2026-11-16', '2026-11-16')")
        conn.execute("DELETE FROM name_matches WHERE district_raw = 'Sacramento Cty Unfd'")
        conn.execute("INSERT INTO name_matches (district_raw, location_raw, method, matched_on) "
                     "VALUES ('Sacramento Cty Unfd', '', 'unsure', '2026-11-16')")
        conn.commit()
        conn.close()
        self.assertEqual(self.run_cli("match", "--review", keys=("1",)), 0)
        self.assertIn("[1]", self.out)
        self.assertIn("Saved. That settles 1 listing.", self.out)
        self.assertEqual(self.q("SELECT method FROM name_matches WHERE district_raw = 'Sacramento Cty Unfd'"), [("manual",)])
        self.assertTrue(self.q("SELECT district_code FROM jobs WHERE posting_id = 1")[0][0])


class DeckRound2(Base):
    """Hands of ten, the back key, strict input, end of input, offline sessions."""
    def setUp(self):
        super().setUp()
        self.first_run("q")
        self.add_jobs(12)  # 6 + 12 = 18 cards: two hands

    def test_hands_of_ten_with_a_pause_and_a_proper_stop(self):
        self.run_cli("go", keys=["s"] * 10 + [""])  # Enter at the hand boundary stops
        self.assertIn("ten at a time. Enter skips a card; q stops and keeps your place.", self.flat)
        self.assertIn("That's 10 of 18: skipped 10. Go on with the next 8?", self.flat)
        self.assertIn("Good place to stop: skipped 10. The other 8 jobs will be here next time.", self.flat)
        self.assertNotIn("whole catch", self.out)
        self.assertNotIn("11 of 18", self.out)
        self.run_cli("go", keys=["s"] * 10 + ["y"] + ["s"] * 8)  # two full hands, then the real end
        self.assertIn("18 of 18", self.out)
        self.assertIn("That's the whole catch: skipped 18.", self.flat)

    def test_back_undoes_the_mark_and_the_tally(self):
        self.run_cli("go", keys=["k", "b", "t", "q"])
        self.assertEqual(self.out.count(" 1 of 18"), 2)  # card one came back
        self.assertIn("Back one card. Whatever you chose on it is undone.", self.flat)
        self.assertEqual(self.q("SELECT status FROM job_marks"), [("tossed",)])
        self.assertIn("Stopping here: tossed 1.", self.flat)

    def test_back_on_the_first_card_does_nothing_surprising(self):
        self.run_cli("go", keys=["b", "q"])
        self.assertIn("This is the first card", self.out)
        self.assertEqual(self.q("SELECT COUNT(*) FROM job_marks"), [(0,)])

    def test_back_is_on_both_key_lines_and_they_fit(self):
        for key in ("triage_keys", "triage_keys_district"):
            self.assertIn("[b]ack", ui.COPY[key])
            self.assertIn("[b]ack", ui.COPY[key + "_short"])
        self.assertLessEqual(max(len(l) for k in ("triage_keys", "triage_keys_district") for l in ui.COPY[k].split("\n")), 79)

    def test_only_a_letter_or_the_whole_word_acts(self):
        self.run_cli("go", keys=["ok", "thanks", "x", "Open", " QUIT "])
        self.assertEqual(len(self.opened), 1)  # "ok" did not open, "Open" did
        self.assertEqual(self.out.count("Type one of these letters"), 3)
        self.assertEqual(self.q("SELECT COUNT(*) FROM job_marks"), [(0,)])  # "thanks" did not toss

    def test_end_of_input_takes_the_quit_path(self):
        self.run_cli("go", keys=["k"])  # one answer, then the input closes
        self.assertIn("Stopping here: kept 1. The other 17 jobs will be here next time.", self.flat)
        self.assertNotIn("whole catch", self.out)
        self.assertEqual(self.q("SELECT COUNT(*) FROM job_marks"), [(1,)])

    def test_offline_with_saved_jobs_goes_on_to_the_deck(self):
        with mock.patch.object(edjoin, "fetch_listings", side_effect=urllib.error.URLError("down")):
            self.run_cli("go", keys=["k"] * 2 + ["q"])
        self.assertEqual(self.out.count("couldn't check for new jobs"), 1)
        self.assertIn("1 of 18", self.out)
        with mock.patch.object(edjoin, "fetch_listings", side_effect=urllib.error.URLError("down")):
            self.run_cli("go", keys=["s"] * 10 + ["y"] + ["s"] * 8)
        self.assertIn("That's everything I had saved", self.flat)

    def test_offline_with_nothing_saved_stops_without_mentioning_keepers(self):
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM job_marks")
        conn.execute("DELETE FROM jobs")
        conn.commit()
        conn.close()
        with mock.patch.object(edjoin, "fetch_listings", side_effect=urllib.error.URLError("down")):
            self.assertEqual(self.run_cli("go"), 1)
        self.assertIn("doesn't seem to be online", self.out)
        self.assertNotIn("keeper", self.out)
        self.assertNotIn("couldn't check for new jobs", self.out)

    def test_enter_means_is_said_in_each_question(self):
        self.assertIn("Enter means offline", ui.COPY["routing_ask"])
        self.assertIn("Enter means yes", ui.COPY["geocode_notice"])
        self.assertIn("Enter to skip", ui.COPY["known_drive_ask"])
        self.assertIn("Enter to skip", ui.COPY["known_drive_minutes"])
        self.assertIn("Enter for {default}", ui.COPY["radius_ask"])


class Resume(Base):
    def test_interrupted_setup_resumes_at_the_first_unfinished_step(self):
        self.assertEqual(self.run_cli(keys=("95814",)), 1)  # input ends at the radius question
        self.assertTrue(config.load(self.cfg).home_key)
        self.assertEqual(self.q("SELECT COUNT(*) FROM commutes"), [(0,)])
        self.assertEqual(self.run_cli(keys=("", "", "")), 0)  # bare command: asked again, not silently offline
        self.assertIn("How many miles from home", self.out)
        self.assertIn("How should I work out drive times?", self.out)
        self.assertNotIn("Step 1", self.out)
        self.assertGreater(self.q("SELECT COUNT(*) FROM commutes")[0][0], 0)


class Settings(Base):
    def setUp(self):
        super().setUp()
        self.first_run("q")

    def test_radius_command(self):
        self.assertEqual(self.run_cli("radius", "5"), 0)
        self.assertEqual(config.load(self.cfg).radius_miles, 5)
        self.assertIn("Within 5 miles of home", self.out)
        self.assertEqual(self.run_cli("radius", "500"), 1)
        self.assertIn("from 1 to 100", self.out)
        self.assertEqual(self.run_cli("radius", "abc"), 1)
        self.assertEqual(self.run_cli("radius"), 1)

    def test_routing_roads_then_offline(self):
        with mock.patch.object(travel, "osrm", lambda home, part, cfg: [(10.0, 12.0)] * len(part)):
            self.assertEqual(self.run_cli("routing", "roads"), 0)
        self.assertEqual(config.load(self.cfg).routing, "osrm")
        self.assertIn("from road distances. To go back to offline:", self.flat)
        self.assertEqual(self.q("SELECT DISTINCT provider FROM commutes"), [("osrm",)])
        self.assertEqual(self.run_cli("routing", "offline"), 0)
        self.assertEqual(config.load(self.cfg).routing, "estimate")
        self.assertEqual(self.q("SELECT DISTINCT provider FROM commutes"), [("estimate",)])
        self.assertIn("worked out offline. To use road distances instead:", self.flat)

    def test_routing_roads_with_the_server_down_keeps_the_old_setting(self):
        with mock.patch.object(travel, "osrm", side_effect=travel.RoutingUnavailable("x")):
            self.assertEqual(self.run_cli("routing", "roads"), 1)
        self.assertEqual(config.load(self.cfg).routing, "estimate")
        self.assertIn("kept your current setting", self.flat)
        self.assertIn("routing offline", self.out)
        self.assertEqual(self.run_cli("routing", "sideways"), 1)
        self.assertIn("roads or offline", self.out)

    def test_no_message_tells_anyone_to_edit_config_toml_or_use_a_code(self):
        everything = "\n".join(ui.COPY.values())
        self.assertNotIn("config.toml", everything)
        self.assertNotIn("14-digit", everything)
        self.assertNotIn("CDS", everything)

    def test_a_spot_with_no_school_gives_a_next_step_and_the_suggestion_is_capped(self):
        self.assertEqual(self.run_cli("home", "32.6,-124.4"), 0)  # the ocean, inside the bounding box
        self.assertIn("Home is set.", self.out)
        self.assertIn("    python edtrawl.py radius 40", self.out)
        self.assertIn("home \"your address or ZIP code\"", self.out)
        self.assertIn("radius 100", ui.text("reveal_none", radius=60, wider=100))
        self.assertNotIn("radius 200", ui.text("reveal_none_max", radius=100, wider=100))
        self.assertIn("as far as I look", ui.text("reveal_none_max", radius=100, wider=100))

    def test_setup_says_drive_times_only_after_working_them_out(self):
        self.tmp2 = Path(tempfile.mkdtemp())
        self.db, self.cfg = str(self.tmp2 / "t.db"), str(self.tmp2 / "c.toml")
        with mock.patch.object(travel, "osrm", side_effect=travel.RoutingUnavailable("x")):
            self.run_cli(keys=("95814", "", "r", "o", ""))
        order = [self.out.index(t) for t in ("isn't answering right now", "worked out offline")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("will use roads", self.out)
        self.assertNotIn("config.toml", self.out)

    def test_server_down_with_and_without_saved_drive_times(self):
        config.set("routing", "osrm", self.cfg)
        self.tty = False
        with mock.patch.object(travel, "osrm", side_effect=travel.RoutingUnavailable("x")):
            self.run_cli("go")
            self.assertIn("saved drive times still work", self.flat)
            conn = sqlite3.connect(self.db)
            conn.execute("DELETE FROM commutes")
            conn.commit()
            conn.close()
            self.assertEqual(self.run_cli("go"), 1)
        self.assertIn("no drive times saved for this home yet", self.flat)
        self.assertNotIn("still work", self.out)
        self.assertIn("routing offline", self.out)

    def test_zip_wording_and_setup_decline(self):
        for key in ("home_declined", "err_address_not_found", "err_geocoder_unreachable"):
            self.assertIn("own", ui.COPY[key])
            self.assertIn("in place of 93721", ui.COPY[key])
        self.assertNotIn("python", ui.COPY["home_declined_setup"])
        self.assertIn("California", ui.COPY["err_unknown_zip"])

    def test_nearest_never_says_zero_miles(self):
        self.assertNotIn("0.0 miles", self.out)
        self.assertIn("less than a tenth of a mile away", self.out)


class Commands(Base):
    def setUp(self):
        super().setUp()
        self.first_run(*"kkkkkk")

    def test_keep_and_toss_by_number_and_unknown_number(self):
        pid = self.q("SELECT MIN(posting_id) FROM job_marks")[0][0]
        self.assertEqual(self.run_cli("toss", str(pid)), 0)
        self.assertEqual(self.q("SELECT status FROM job_marks WHERE posting_id = ?", pid), [("tossed",)])
        self.assertIn("Marked as tossed:", self.out)
        self.run_cli("keep", str(pid))
        self.assertEqual(self.q("SELECT status FROM job_marks WHERE posting_id = ?", pid), [("kept",)])
        self.assertEqual(self.run_cli("keep", "12"), 1)
        self.assertIn("I don't have a job numbered 12.", self.out)
        self.assertEqual(self.run_cli("keep", "abc"), 1)
        self.assertIn("doesn't look like a job's number", self.out)
        self.assertNotIn("usage:", self.out)

    def test_applied_twice_and_bad_numbers(self):
        pid = self.q("SELECT MIN(posting_id) FROM job_marks")[0][0]
        self.run_cli("applied", str(pid))
        self.run_cli("applied", str(pid))
        self.assertIn("You'd already marked this one as applied", self.out)
        self.assertNotIn("Marked as applied", self.out)
        for argv in (("applied", "abc"), ("applied",)):
            self.assertEqual(self.run_cli(*argv), 1)
            self.assertIn("doesn't look like a job's number", self.out)

    def test_keepers_hint_uses_a_keeper_that_is_still_open(self):
        first = self.q("SELECT posting_id FROM jobs WHERE posting_id IN (SELECT posting_id FROM job_marks) "
                       "ORDER BY deadline LIMIT 1")[0][0]
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE jobs SET deadline = '2020-01-01' WHERE posting_id = ?", (first,))
        conn.commit()
        conn.close()
        self.run_cli("keepers")
        self.assertNotIn(f"applied {first}", self.out)
        self.assertRegex(self.out, r"applied \d+")

    def test_school_and_drove_take_name_comma_city_as_listed(self):
        self.assertEqual(self.run_cli("school", "Washington", "Elementary,", "Sacramento"), 0)
        self.assertIn("Students", self.out)
        self.assertEqual(self.run_cli("drove", "Washington Elementary, Sacramento", "30"), 0)
        self.assertIn("For Washington Elementary you said 30 min", self.flat)
        self.assertEqual(self.run_cli("school", "Washington Elementary, Nowhere"), 1)

    def test_several_matches_with_nobody_to_ask_or_a_bad_number(self):
        self.tty = False
        self.assertEqual(self.run_cli("drove", "Elementary", "30"), 1)
        self.assertIn("nothing was changed", self.flat)
        self.assertIn('drove "Lincoln Elementary, Fresno" 30', self.out)
        self.assertEqual(self.q("SELECT COUNT(*) FROM known_drives"), [(0,)])
        self.tty = True
        self.run_cli("school", "Elementary", keys=("0", "x", "2"))
        self.assertEqual(self.out.count("Type a number from 1 to"), 2)  # re-asked on each bad answer
        self.assertIn("Grades", self.out)

    def test_drove_for_a_school_out_of_range(self):
        name = self.q("SELECT school_name FROM schools WHERE cds_code NOT IN (SELECT cds_code FROM commutes) "
                      "AND school_name NOT IN (SELECT school_name FROM schools GROUP BY school_name HAVING COUNT(*) > 1) "
                      "LIMIT 1")[0][0]
        self.assertEqual(self.run_cli("drove", name, "30"), 1)
        self.assertIn("is outside the 20 miles I'm looking", self.flat)
        self.assertNotIn("couldn't find", self.out)

    def test_drove_missing_or_wrong_arguments_get_our_words(self):
        for argv in (("drove",), ("drove", "Washington"), ("drove", "Washington", "soon")):
            self.run_cli(*argv)
            self.assertNotIn("usage:", self.out)
            self.assertTrue("Type the minutes" in self.out or "I need a school and the minutes" in self.out)

    def test_logbook_continuation_lines_are_indented(self):
        self.run_cli("logbook")
        lines = self.out.splitlines()
        entries = [i for i, l in enumerate(lines) if l.startswith("Nov ")]
        self.assertTrue(entries)
        for l in lines[entries[0]:]:
            self.assertTrue(l.startswith("Nov ") or l.startswith("  "), l)

    def test_deleted_config_adopts_the_home_the_database_remembers(self):
        home = config.load(self.cfg).home_key
        os.remove(self.cfg)
        self.run_cli("keepers")
        self.assertIn("Keepers: 6 jobs", self.out)
        self.assertEqual(config.load(self.cfg).home_key, home)


class NothingFetchedYet(Base):
    def test_search_keepers_and_school_do_not_report_searches_that_never_happened(self):
        self.assertEqual(self.run_cli("school", "Lincoln"), 1)
        self.assertIn("school list isn't loaded yet", self.flat)
        self.assertNotIn("couldn't find", self.out)
        self.run_cli(keys=("95814", "", "", "", "q"))  # set up fully, then quit
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM job_marks")
        conn.execute("DELETE FROM jobs")
        conn.commit()
        conn.close()
        for cmd in ("search", "keepers"):
            self.run_cli(cmd)
            self.assertIn("haven't fetched any job listings yet", self.flat, cmd)
            self.assertNotIn("No teaching jobs are posted", self.out)


class Review(Base):
    def test_an_unrecognised_answer_asks_again_and_a_choice_is_stored(self):
        self.first_run("q")
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO jobs (posting_id, title, district_raw, county, url, first_seen, last_seen) "
                     "VALUES (1, 'Teacher', 'Sacramento Cty Unfd', 'Sacramento', 'https://www.edjoin.org/Home/JobPosting/1', "
                     "'2026-11-16', '2026-11-16')")
        conn.execute("DELETE FROM name_matches WHERE district_raw = 'Sacramento Cty Unfd'")
        conn.execute("INSERT INTO name_matches (district_raw, location_raw, method, matched_on) "
                     "VALUES ('Sacramento Cty Unfd', '', 'unsure', '2026-11-16')")
        conn.commit()
        conn.close()
        self.run_cli("match", "--review", keys=("banana", "1"))
        self.assertIn("Type a number from 1 to", self.out)
        self.assertEqual(self.q("SELECT method FROM name_matches WHERE district_raw = 'Sacramento Cty Unfd'"), [("manual",)])


if __name__ == "__main__":
    unittest.main()
