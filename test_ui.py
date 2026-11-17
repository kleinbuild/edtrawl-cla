"""Offline tests for ui.py: python3 -m unittest test_ui -v"""
import contextlib
import datetime
import io
import re
import string
import unittest
from unittest import mock

import ui

TODAY = datetime.date(2026, 11, 16)  # a Monday

# One sample value for every field any COPY template uses (also used to print the whole set for review).
SAMPLE = dict(
    n=7, total=4, title="Math Teacher, Grades 7-8", default=20, radius=20, schools=412, districts=37,
    school="Roosevelt Middle", miles=1.2, wider=30, server="router.project-osrm.org", name="Lincoln",
    city="Fresno", before=22, after=29, year="2025-26", since="yesterday", k=3, tally="kept 2, tossed 4, skipped 1",
    left=4, example="2295141", looked=23, kept=5, applied=2, start="Oct 30", date="Nov 12", status="kept",
    where="Roosevelt Middle", max=20, minutes=25, zip="93721", service="edjoin.org", url="https://www.edjoin.org/Home/JobPosting/2295141",
    id="2295141", path="edtrawl-error.log", choices="k, t, s, o, m, q", am="~22 min", pm="~26", week="about 4 hrs a week",
    lo="~12", hi="~41", score="0.84", done=10, next=10, est=22, setting="routing", new=3, seen=12, h="4.5", m=40, pct="+1%", day="Fri",
)

SCHOOL_JOB = dict(
    posting_id=2295141, title="Math Teacher, Grades 7-8", cds_code="10621666006284", school_name="Roosevelt Middle",
    district_name="Fresno Unified", district_raw="Fresno Unified School District", provider="estimate",
    am_minutes=21.6, pm_minutes=26.2, enroll_total=612, prev_enroll_total=606, staff_teacher=24, title_i="Y",
    salary_info="$58,400-$104,200", deadline="2026-11-19",
)
DISTRICT_JOB = dict(
    posting_id=2295142, title="Teacher, Special Education, Preschool", cds_code=None, school_name=None,
    district_name="Fresno Unified", provider="osrm", district_min_minutes=12.2, district_max_minutes=41.4,
    district_schools_in_range=14, salary_info="Placement on the Certificated Salary Schedule", deadline="2026-12-04",
)
LONG_JOB = dict(
    posting_id=2295143, cds_code="10621666006285", school_name="Theodore Judah Elementary",
    district_name="Sacramento City Unified", provider="osrm", am_minutes=9, pm_minutes=11,
    title=("Teacher, Special Education, Mild/Moderate Support Needs, Resource Specialist Program, Grades "
           "TK-6 Dual Immersion Spanish"),
    salary_info=None, deadline=None,
)
CARDS = (SCHOOL_JOB, DISTRICT_JOB, LONG_JOB)
ESC = re.compile("\x1b")
EMOJI = re.compile("[\u2600-\u27bf\U0001f000-\U0001faff]")


def captured(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return buf.getvalue(), result


class Formatters(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(ui.minutes(21.6, "osrm"), "~22 min")
        self.assertEqual(ui.minutes(21.6, "estimate"), "~22 min")
        self.assertEqual(ui.minutes(0, "estimate"), "~1 min")  # next door is still a modelled drive
        self.assertEqual(ui.minutes(None, "osrm"), "")
        self.assertEqual(ui.minutes(34, "known"), "34 min")    # the user's own number is not hedged

    def test_drive_line(self):
        self.assertEqual(ui.drive_line(21.6, 26.2),
                         "~22 min there · ~26 home if you leave at 3:30   (about 4 hrs a week)")
        self.assertIn("about 1 hr a week", ui.drive_line(6, 6))
        self.assertIn("about 4.5 hrs a week", ui.drive_line(25, 29))
        self.assertIn("about 20 min a week", ui.drive_line(2, 2))
        self.assertEqual(ui.drive_line(22, None), "~22 min there · no afternoon time yet")
        self.assertIn("3:30", ui.drive_line(None, 26))  # the afternoon figure always names its departure
        self.assertEqual(ui.drive_line(None, None), "no drive time yet")
        self.assertIn("~1 min there", ui.drive_line(0, 0))

    def test_range_line(self):
        self.assertEqual(ui.range_line(12.2, 41.4, 14), "~12 to ~41 min across the district's 14 schools in range")
        self.assertEqual(ui.range_line(12, 12, 1), "~12 min to the district's one school in range")
        self.assertEqual(ui.range_line(12, 12.2, 3), "~12 min to each of the district's 3 schools in range")
        self.assertEqual(ui.range_line(None, None, 0), "no drive time yet")

    def test_trend(self):
        self.assertEqual(ui.trend(612, 606), "steady (+1% in a year)")
        self.assertEqual(ui.trend(650, 600), "growing (+8% in a year)")
        self.assertEqual(ui.trend(560, 600), "shrinking (-7% in a year)")
        self.assertEqual(ui.trend(600, 600), "steady (same as a year before)")
        self.assertEqual(ui.trend(612, None), "")
        self.assertEqual(ui.trend(None, 606), "")
        self.assertEqual(ui.trend(612, 0), "")

    def test_deadline(self):
        self.assertEqual(ui.deadline("2026-11-16", TODAY), "closes today")
        self.assertEqual(ui.deadline("2026-11-17", TODAY), "closes tomorrow")
        self.assertEqual(ui.deadline("2026-11-20", TODAY), "closes Fri (4 days)")
        self.assertEqual(ui.deadline("2026-12-04", TODAY), "closes Dec 4")
        self.assertEqual(ui.deadline("2026-11-12", TODAY), "closed Nov 12")
        self.assertEqual(ui.deadline(None, TODAY), "")
        self.assertEqual(ui.deadline("", TODAY), "")
        self.assertEqual(ui.deadline("Until Filled", TODAY), "")
        # edjoin's 11:55 pm Pacific deadline arrives as the next day in UTC; it is read as Pacific.
        self.assertEqual(ui.deadline("2026-11-20T07:55:00Z", TODAY), "closes Thu (3 days)")

    def test_count_and_tally(self):
        self.assertEqual(ui.count(1, "job"), "1 job")
        self.assertEqual(ui.count(1412, "school"), "1,412 schools")
        self.assertEqual(ui.count(None, "job"), "0 jobs")
        self.assertEqual(ui.tally(2, 4, 1), "kept 2, tossed 4, skipped 1")
        self.assertEqual(ui.tally(0, 3, 0), "tossed 3")
        self.assertEqual(ui.tally(), "nothing marked")

    def test_since_and_grades(self):
        self.assertEqual(ui.since("2026-11-15", TODAY), "yesterday")
        self.assertEqual(ui.since("2026-11-12", TODAY), "Thursday")
        self.assertEqual(ui.since("2026-10-30", TODAY), "Oct 30")
        self.assertEqual(ui.grades("KG", "05"), "K–5")
        self.assertEqual(ui.grades("09", "12"), "9–12")
        self.assertEqual(ui.grades(None, None), "")


class Copy(unittest.TestCase):
    def test_every_entry_formats_and_plurals_agree(self):
        for key, template in ui.COPY.items():
            fields = {f for _, f, _, _ in string.Formatter().parse(ui._PLURAL.sub("", template)) if f}
            self.assertLessEqual(fields, set(SAMPLE), key)
            self.assertNotIn("{", ui.text(key, **SAMPLE), key)
        self.assertEqual(ui.text("reveal", radius=20, schools=1, districts=1),
                         "Within 20 miles of home, as the crow flies: 1 public school in 1 district.")

    def test_voice_rules(self):
        everything = "\n".join(ui.COPY.values())
        self.assertLessEqual(everything.count("!"), 1)
        self.assertIsNone(EMOJI.search(everything))
        for word in ("awesome", "great job", "hurry", "streak", "oops", "sorry", "error:"):
            self.assertNotIn(word, everything.lower())

    def test_text_cleans_values(self):
        self.assertEqual(ui.text("applied_done", title="Art\x1b[2J Teacher"), "Marked as applied: Art Teacher.")


class Clean(unittest.TestCase):
    def test_strips_escapes_and_controls(self):
        self.assertEqual(ui.clean("Math\x1b[2J Teacher"), "Math Teacher")
        self.assertEqual(ui.clean("A\x1b]0;owned\x07B\x07\x00C"), "AB C")
        self.assertEqual(ui.clean("evil\u202etxt.exe"), "evil txt.exe")
        self.assertEqual(ui.clean("Art &amp; Music\n\tK-5"), "Art & Music K-5")
        self.assertEqual(ui.clean("&#27;[31mred"), "[31mred")  # an encoded ESC is decoded, then removed
        self.assertEqual(ui.clean(None), "")


class Renderers(unittest.TestCase):
    def setUp(self):
        self.saved = dict(ui.CAPS)

    def tearDown(self):
        ui.CAPS.clear()
        ui.CAPS.update(self.saved)

    def test_card_matches_the_mock(self):
        ui.CAPS.update(color=False)
        card = ui.job_card(SCHOOL_JOB, 2, 7, width=80, today=TODAY).split("\n")
        self.assertTrue(card[0].startswith(" ── 2 of 7 ──") and card[0].endswith("── closes Thu (3 days)"))
        self.assertEqual(card[1:], [
            " Math Teacher, Grades 7-8",
            " Roosevelt Middle · Fresno Unified",
            " Drive   ~22 min there · ~26 home if you leave at 3:30   (about 4 hrs a week)",
            " School  612 students, steady (+1% in a year) · 24 teachers · Title I",
            " Pay     $58,400-$104,200",
        ])

    def test_district_card(self):
        ui.CAPS.update(color=False)
        card = ui.job_card(DISTRICT_JOB, 1, 1, width=80, today=TODAY)
        self.assertIn(" Site not listed · Fresno Unified", card)
        self.assertIn(" Drive   ~12 to ~41 min across the district's 14 schools in range", card)
        self.assertNotIn("School  ", card)

    def test_cards_fit_80_and_60(self):
        for color in (False, True):
            ui.CAPS.update(color=color)
            for width in (80, 60):
                for row in CARDS:
                    card = ui.job_card(row, 3, 12, width=width, today=TODAY)
                    for line in re.sub("\x1b\\[[0-9;]*m", "", card).split("\n"):
                        self.assertLess(len(line), width, line)
        ui.CAPS.update(color=False)
        long = ui.job_card(LONG_JOB, 1, 1, width=60, today=TODAY)
        self.assertIn("Pay     not listed", long)
        self.assertIn("...", long)  # a title past two lines is cut, not allowed to push the card around

    def test_plain_mode_has_no_escapes_or_emoji(self):
        with mock.patch.dict("os.environ", {"NO_COLOR": ""}), mock.patch.object(ui, "_isatty", return_value=True):
            ui.configure(plain=True)
        self.assertFalse(ui.CAPS["color"] or ui.CAPS["emoji"])
        out, _ = captured(lambda: [
            ui.show(ui.job_card(row, 1, 3, today=TODAY)) for row in CARDS] + [
            ui.show(ui.school_card({**SCHOOL_JOB, "hispanic_pct": 41.2, "academic_year": "2025-26"}, rush_pm=1.5)),
            ui.show(ui.table(CARDS, today=TODAY)), ui.say("triage_keys"),
            ui.progress(5, 10, "progress_fetch"), ui.progress(10, 10, "progress_fetch")])
        self.assertIsNone(ESC.search(out))
        self.assertIsNone(EMOJI.search(out))
        self.assertIn("\\_/", out)

    def test_no_color_env(self):
        with mock.patch.dict("os.environ", {"NO_COLOR": "1"}), mock.patch.object(ui, "_isatty", return_value=True):
            ui.configure()
        self.assertFalse(ui.CAPS["color"])
        self.assertTrue(ui.CAPS["tty"])

    def test_pipe_gets_no_animation(self):
        with mock.patch.object(ui, "_isatty", return_value=False):
            ui.configure()
        out, _ = captured(lambda: [ui.progress(i, 3, "progress_drives") for i in range(4)])
        self.assertEqual(out, "Working out drive times: 3 of 3.\n")

    def test_school_card_is_facts_only(self):
        ui.CAPS.update(color=False)
        row = {**SCHOOL_JOB, "grade_low": "06", "grade_high": "08", "school_level": "Middle", "city": "Fresno",
               "county_name": "Fresno", "staff_total": 41, "english_learner_pct": 18.8, "white_pct": 21.2,
               "hispanic_pct": 52.0, "academic_year": "2025-26"}
        card = ui.school_card(row, width=60, rush_pm=1.5)
        self.assertIn("6–8 · Middle · Title I", card)
        self.assertIn("English learners 19%", card)
        self.assertLess(card.index("Hispanic 52%"), card.index("White 21%"))  # CDE order, not by size
        self.assertIn("leaving after 4", card)
        self.assertNotIn("leaving after 4", ui.school_card(row, width=60, rush_pm=1.1))
        for line in card.split("\n"):
            self.assertLess(len(line), 60, line)

    def test_ask_returns_default_without_a_terminal(self):
        ui.CAPS.update(interactive=False)
        with mock.patch("builtins.input", side_effect=AssertionError("blocked")):
            self.assertEqual(ui.ask("triage_keys", "ktsomq", default="s"), "s")
            self.assertIsNone(ui.ask("home_ask"))

    def test_ask_reads_a_letter_and_asks_again_on_nonsense(self):
        ui.CAPS.update(interactive=True, color=False)
        with mock.patch("builtins.input", side_effect=["x", "Keep"]):
            out, answer = captured(ui.ask, "triage_keys", "ktsomq", default="s")
        self.assertEqual(answer, "k")
        self.assertIn("Type one of these letters", out)
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertEqual(captured(ui.ask, "triage_keys", "ktsomq", "s")[1], "s")

    def test_say_wraps_but_leaves_commands_whole(self):
        ui.CAPS.update(color=False, width=60, utf8=True)
        with mock.patch.object(ui, "launcher", lambda: "python"):
            out, _ = captured(ui.say, "err_address_not_found")
        self.assertTrue(all(len(l) < 60 for l in out.splitlines()))
        self.assertIn("    python edtrawl.py home --zip 93721\n", out)

    def test_launcher_is_python3_when_python_is_missing(self):
        with mock.patch("shutil.which", lambda name: None):
            self.assertEqual(ui.launcher(), "python3")
            self.assertIn("    python3 edtrawl.py home --zip 93721", ui.text("home_declined"))
        with mock.patch("shutil.which", lambda name: "/usr/bin/python"):
            self.assertEqual(ui.launcher(), "python")
            self.assertIn("    python edtrawl.py home --zip 93721", ui.text("home_declined"))

    def test_ask_takes_one_letter_or_the_whole_word_and_nothing_else(self):
        ui.CAPS.update(interactive=True, color=False)
        with mock.patch("builtins.input", side_effect=["ok", "thanks", " QUIT ", ]):
            out, answer = captured(ui.ask, "triage_keys", "ktsobmq", default="s")
        self.assertEqual(answer, "q")  # "ok" and "thanks" were refused, not read as o or t
        self.assertEqual(out.count("Type one of these letters"), 2)
        with mock.patch("builtins.input", side_effect=["Offline"]):
            self.assertEqual(captured(ui.ask, "routing_ask", "or", "o", words={"o": "offline", "r": "roads"}, server="x")[1], "o")

    def test_ask_tells_the_caller_input_ended(self):
        ui.CAPS.update(interactive=True, color=False)
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertEqual(captured(ui.ask, "triage_keys", "ktsobmq", default="s", eof="q")[1], "q")

    def test_progress_on_a_narrow_terminal_drops_the_boat(self):
        ui.CAPS.update(tty=True, color=False, width=40, utf8=True, emoji=False)
        out, _ = captured(ui.progress, 10, 40, "progress_details")
        line = out.strip("\r\n")
        self.assertLess(len(line), 40)
        self.assertIn("10 of 40", line)
        self.assertNotIn("\\_/", line)

    def test_empty_title_gets_a_placeholder(self):
        card = ui.job_card(dict(SCHOOL_JOB, title=""), 1, 1, width=80, today=TODAY)
        self.assertIn("(no title)", card)

    def test_ascii_terminal_gets_ascii(self):
        ui.CAPS.update(color=False, utf8=False, encoding="ascii")
        out, _ = captured(ui.show, ui.job_card(DISTRICT_JOB, 1, 2, width=80, today=TODAY))
        out.encode("ascii")
        self.assertIn("Site not listed - Fresno Unified", out)


if __name__ == "__main__":
    unittest.main()
