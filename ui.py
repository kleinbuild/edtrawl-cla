"""Everything EdTrawl says, and the only module that writes to the terminal.

Other modules refer to COPY keys and call `say`, `ask`, `progress` and the renderers here.
Text from edjoin, from CDE and from any model is untrusted: it reaches the screen only through `clean`.
"""
import datetime
import html
import os
import re
import shutil
import sys
import textwrap
import time
import unicodedata

# ── Words ────────────────────────────────────────────────────────────────────────────────────────
# Templates use str.format fields. `{n:job|jobs}` prints the count with the right noun ("1 job", "3 jobs").
# A line starting with four spaces is a command to type: it is never wrapped.
# Voice: a warm colleague. Plain words, "I" for the program, no exclamation marks, the trawler theme
# only in labels (home port, catch, keepers, toss, logbook, casting the net), never in an error.
COPY = {
    # ── first run and setup ──
    "welcome": (
        "Welcome to EdTrawl.\n"
        "It finds California teaching jobs within driving distance of home and shows you each new "
        "one once, so you can keep it or toss it. Setup is four short steps, and you can change "
        "any answer later."),
    "setup_step": "Step {n} of {total} · {title}",
    "step_home": "Home port",
    "step_schools": "Schools near you",
    "step_routing": "Drive times",
    "step_known_drive": "One drive you know",
    "home_ask": (
        "Your street address is never saved; I keep only a spot rounded to about a city block.\n"
        "Where is home? Any one of these works:\n"
        "    a street address    123 Main St, Fresno\n"
        "    a ZIP code          93721\n"
        "    a map position      36.74,-119.79"),
    "geocode_notice": "To find that address I'll send it once to the US Census Bureau's free geocoder (geocoding.geo.census.gov). Nothing else goes with it, and it isn't saved. Type y to send it, or n.",
    "home_saved": "Home is set.",
    "home_zip_note": (
        "A ZIP code puts home at the middle of that ZIP's schools, which can be a mile or two off, "
        "so drive times will be a little rougher. To give an address later:\n"
        "    python edtrawl.py home \"your street address\""),
    "radius_ask": "How many miles from home should I look, as the crow flies? Press Enter for {default}.",
    "reveal": "Within {radius} miles of home, as the crow flies: {schools:public school|public schools} in {districts:district|districts}.",
    "reveal_nearest": "The nearest is {school}, about {miles} miles away.",
    "reveal_none": 'There are no public schools within {radius} miles of that spot. To look farther, try a bigger radius:\n    python edtrawl.py radius {wider}\nIf home is in the wrong place, set it again, with your own address or ZIP code in place of the words:\n    python edtrawl.py home "your address or ZIP code"',
    "routing_ask": "How should I work out drive times?\n  [o]ffline: a formula on straight-line distance. Nothing leaves this computer, but it can't see bays, mountains or freeways.\n  [r]oads: real road distances from a free OpenStreetMap routing server ({server}). It receives your home spot, rounded to about a city block, and the positions of schools near you. Nothing else.\nBoth add typical rush-hour traffic, and both are estimates. Type o or r; Enter means offline.",
    "routing_saved_offline": 'Drive times are ready for {n:school|schools}, worked out offline. To use road distances instead:\n    python edtrawl.py routing roads',
    "routing_saved_roads": 'Drive times are ready for {n:school|schools}, from road distances. To go back to offline:\n    python edtrawl.py routing offline',
    "known_drive_ask": (
        "Is there a school you drive to now, or used to? Its real morning drive time lets me fit "
        "every estimate to your roads. Type the school's name, or press Enter to skip."),
    "known_drive_which": "More than one school matches \"{name}\". Which one?",
    "known_drive_option": "  [{n}] {school}, {city}",
    "known_drive_not_found": "I couldn't find a school called \"{name}\" near home. Check the spelling, or press Enter to skip.",
    "known_drive_minutes": 'About how many minutes is the morning drive to {school}, door to door? Press Enter to skip.',
    "drove_adjusted_am": "For {school} you said {minutes} min, and I'd estimated ~{est}. I've scaled every morning estimate by the same amount: half the schools near you are now within ~{after} min (it was ~{before}).",
    "drove_adjusted_pm": "For {school} you said {minutes} min, and I'd estimated ~{est}. I've scaled every afternoon estimate by the same amount: half the schools near you are now within ~{after} min (it was ~{before}).",
    "drove_unchanged": "Thanks. That's close to my estimate, so the other drive times barely move.",
    "drove_clamped": (
        "That's far from my estimate, so I adjusted as far as I allow (half or double). If that "
        "day's traffic was unusual, a typical day's time will fit better."),
    "setup_done": "Setup is done.",
    "empty_none_saved": "None of the jobs I've saved are within {radius} miles. To check for new ones:\n    python edtrawl.py",
    "edjoin_notice": "Job listings come from edjoin.org. I ask it for teaching jobs in the counties around you, and read a few postings to find the school. Your home isn't sent.",

    # ── progress lines (label on the left, real counts on the right) ──
    "progress_schools": "Loading California schools",
    "progress_drives": "Working out drive times",
    "progress_fetch": "Casting the net",
    "progress_details": "Reading postings for school names",
    "progress_match": "Matching listings to schools",
    "schools_loaded": "{n:school|schools} loaded from the California Department of Education, {year}.",
    "drives_ready": "Drive times are ready for {n:school|schools}.",
    "attribution_osm": "Road distances: © OpenStreetMap contributors, routed by OSRM.",

    # ── the daily loop ──
    "welcome_back": "{n:new job|new jobs} since {since}.",
    "catch_intro": "{n:job|jobs} to look at, nearest first, ten at a time. Enter skips a card; q stops, and the rest wait for next time.",
    "keepers_closed": "Since you last looked, {n:keeper has|keepers have} closed. The keepers list marks which.",
    "triage_keys": '[k]eep   [t]oss   [s]kip   [b]ack   [o]pen   [m]ore about the school   [q]uit',
    "triage_keys_short": '[k]eep [t]oss [s]kip [b]ack [o]pen [m]ore [q]uit',
    "triage_keys_district": '[k]eep   [t]oss   [s]kip   [b]ack   [o]pen posting   [q]uit',
    "triage_keys_district_short": '[k]eep [t]oss [s]kip [b]ack [o]pen [q]uit',
    "kept": "Kept.",
    "tossed": "Tossed.",
    "skipped": "Skipped. It'll come up again next time.",
    "opened": "Opened the posting in your browser.",
    "first_keep": "Your first keeper. It'll wait in your list, with its deadline, until you apply or toss it.",
    "triage_end": "That's the whole catch: {tally}.\nNothing else is new today, so you're done.",
    "triage_quit": "Stopped here: {tally}. Everything you didn't keep or toss will be here next time.",
    "triage_list_only": "To keep or toss these, run this in a terminal window:\n    python edtrawl.py",
    "tally_kept": "kept {n}",
    "tally_tossed": "tossed {n}",
    "tally_skipped": "skipped {n}",
    "tally_none": "nothing marked",
    "since_today": "earlier today",
    "since_yesterday": "yesterday",

    # ── keepers, applied, logbook ──
    "keepers_header": "Keepers: {n:job|jobs}, soonest deadline first",
    "keepers_empty": "No keepers yet. Press k on a job's card and it will wait here.",
    "keepers_apply_hint": "When you apply for one, note it by its number:\n    python edtrawl.py applied {example}",
    "applied_done": "Marked as applied: {title}.",
    "first_applied": "First one in the logbook. That's the hard part done.",
    "logbook_header": "Logbook",
    "logbook_week": "This week: decided on {looked}, kept {kept}, applied to {applied}.",
    "logbook_total": "Since {start}: decided on {looked}, kept {kept}, applied to {applied}.",
    "logbook_line": "{date}  {status:<8} {title} · {where}",
    "logbook_empty": "Nothing in the logbook yet. It fills in as you keep, toss and apply.",
    "mark_kept": "kept",
    "mark_tossed": "tossed",
    "mark_applied": "applied",

    # ── empty states ──
    "empty_no_new": "Nothing new since {since}. You have {k:keeper|keepers} waiting:\n    python edtrawl.py keepers",
    "empty_no_new_no_keepers": "Nothing new since {since}, so you're done for today.",
    "empty_in_range": "Nothing within {max} minutes today.",
    "empty_nearly": "{n:job opens|jobs open} up at {minutes} minutes:\n    python edtrawl.py search --max-commute {minutes}",
    "empty_none_near": "No teaching jobs are posted within {radius} miles right now. To look again another day:\n    python edtrawl.py",
    "match_set_aside": "{n:listing|listings} didn't clearly match a school or district, so I set those aside instead of guessing. Nothing is lost. To place them yourself:\n    python edtrawl.py match --review",
    "fetch_done": "{new:new listing|new listings} saved, and {seen} I'd seen before.",
    "search_header": "{n:job|jobs}, nearest drive first.",
    "search_header_more": "The nearest {n:job|jobs}. There are more: add --limit and a bigger number to see them.",
    "empty_nearly_filtered": "{n:job opens|jobs open} up at {minutes} minutes. Run the same search again, with:\n    --max-commute {minutes}",
    "keepers_all_applied": "No keepers waiting. You've applied to {n:job|jobs}, listed in the logbook:\n    python edtrawl.py logbook",
    "empty_filtered": "No jobs fit those filters. Try dropping one.",
    "review_header": "{n:listing|listings} set aside. Under each are the closest names I found; 1.00 would be identical.",
    "review_empty": "Nothing is set aside.",
    "home_declined": 'Nothing was sent. A ZIP code or a map position needs no geocoder. Put your own ZIP code in place of 93721:\n    python edtrawl.py home --zip 93721',

    # ── errors: what happened, whether anything is lost, the one next step ──
    "err_no_home": "There's no home set yet, so I can't measure any drives. This sets one up in a few steps:\n    python edtrawl.py",
    "err_home_unreadable": "I couldn't read that as an address, ZIP code or map position. A ZIP code is five digits, like 93721; a map position looks like 36.74,-119.79.",
    "err_address_not_found": "I couldn't place that address, so nothing was saved. Your ZIP code works too, and needs no internet. Put your own in place of 93721:\n    python edtrawl.py home --zip 93721",
    "err_address_not_found_setup": "I couldn't place that address, so nothing was saved. Try just your ZIP code; that needs no internet.",
    "err_geocoder_unreachable": "The Census geocoder isn't answering, or this computer is offline. Nothing was saved. Your ZIP code works without the internet. Put your own in place of 93721:\n    python edtrawl.py home --zip 93721",
    "err_geocoder_unreachable_setup": "The Census geocoder isn't answering, or this computer is offline. Nothing was saved. Try just your ZIP code; that needs no internet.",
    "err_outside_california": "That spot is outside California, and EdTrawl only knows California schools. Nothing was saved. Check the address, or try your ZIP code.",
    "err_unknown_zip": "I couldn't find any California schools in ZIP {zip}, and I place a ZIP by its schools, so it has to be a California ZIP code. Nothing was saved. Try a neighboring ZIP code or your street address.",
    "err_file_not_found": "I couldn't find a file at {path}. Check the spelling and try again.",
    "err_no_commutes": "There are no drive times yet, so I don't know which counties to look in. This works them out:\n    python edtrawl.py commute",
    "err_radius": "Type a number of miles from 1 to 100.",
    "err_minutes": "Type the minutes as a number from 1 to 240.",
    "err_schools_download": "The state's data site (data.ca.gov) didn't answer, so the school list isn't loaded. Nothing is lost. Try again in a few minutes:\n    python edtrawl.py ingest --year {year}",
    "err_routing_unreachable": "The road-distance server isn't answering. Your saved drive times still work, and I'll use them; a school without one shows no drive time until the server is back. To try again later:\n    python edtrawl.py",
    "err_routing_unreachable_setup": "The road-distance server isn't answering right now. Nothing is lost. Choose offline for now; you can switch later with:\n    python edtrawl.py routing roads",
    "err_edjoin_refused": "edjoin.org turned the request away, so I stopped. Nothing you've already saved is lost. Try again tomorrow:\n    python edtrawl.py",
    "err_edjoin_busy": "edjoin.org asked me to slow down, so I stopped for now. Nothing you've already saved is lost. Try again in a few hours:\n    python edtrawl.py",
    "err_edjoin_down": "edjoin.org isn't working properly right now, so I stopped. Nothing you've already saved is lost. Try again later today:\n    python edtrawl.py",
    "err_offline": "This computer doesn't seem to be online, so I couldn't reach {service}. Nothing you've saved has changed. Once you're connected:\n    python edtrawl.py",
    "err_llm_unreachable": "The matching model at {url} didn't answer, so matching ran without it. Nothing is lost; anything it would have helped with is in the review list:\n    python edtrawl.py match --review",
    "err_unknown_posting": "I don't have a job numbered {id}. Each job's number is the first thing on its line here:\n    python edtrawl.py keepers",
    "err_open_browser": "I couldn't open a browser from here. The posting is at:\n    {url}",
    "err_unexpected": "Something unexpected went wrong, so I stopped. A note of where it happened is in {path}.",
    "stopped": "Stopped. Nothing already saved is lost.",
    "ask_again": "Type one of these letters, then Enter: {choices}.",

    # ── card pieces ──
    "label_drive": "Drive",
    "label_school": "School",
    "label_pay": "Pay",
    "label_grades": "Grades",
    "label_students": "Students",
    "label_staff": "Staff",
    "label_groups": "Groups",
    "label_ethnicity": "Ethnicity",
    "label_website": "Website",
    "site_not_listed": "Site not listed",
    "pay_not_listed": "not listed",
    "students": "{n:student|students}",
    "teachers": "{n:teacher|teachers}",
    "staff_total": "{n:staff member|staff} in all",
    "title_i": "Title I",
    "charter": "charter",
    "magnet": "magnet",
    "virtual_F": "fully virtual",
    "virtual_V": "mostly virtual",
    "drive_both": "{am} there · {pm} home if you leave at 3:30   ({week})",
    "drive_am_only": "{am} there · no afternoon time yet",
    "drive_pm_only": "{pm} home if you leave at 3:30 · no morning time yet",
    "drive_none": "no drive time yet",
    "drive_range": "{lo} to {hi} min across the district's {n:school|schools} in range",
    "drive_range_one": "{lo} min to the district's one school in range",
    "drive_range_same": "{lo} min to each of the district's {n:school|schools} in range",
    "week_hours": "about {h} hrs a week",
    "week_hour": "about 1 hr a week",
    "week_minutes": "about {m} min a week",
    "trend_up": "growing ({pct} in a year)",
    "trend_flat": "steady ({pct} in a year)",
    "trend_same": "steady (same as a year before)",
    "trend_down": "shrinking ({pct} in a year)",
    "deadline_today": "closes today",
    "deadline_tomorrow": "closes tomorrow",
    "deadline_soon": "closes {day} ({n} days)",
    "deadline_later": "closes {date}",
    "deadline_passed": "closed {date}",
    "table_head": "Number   Drive    Closes   Job",
    "table_today": "today",
    "table_closed": "closed",
    "more_times": "Drive times assume arriving by 7:00 and leaving at 3:30 on a weekday. Later in the afternoon is usually slower.",
    "more_rush": "Afternoon traffic here builds fast; leaving after 4 is usually slower than this.",
    "chart_done": "Chart written to {path} and opened in your browser. It shows where home is, so keep the file to yourself.",
    "chart_saved": "Chart written to {path}. It shows where home is, so keep the file to yourself.",
    "chart_written": "Chart written to {path}. I couldn't open a browser from here, so open that file yourself.",
    "more_source": "School figures: California Department of Education, {year}.",

    # ── flows: setup needs a terminal, picking among several schools, the interactive review ──
    "setup_needs_terminal": "Setup asks a few questions, so it needs a terminal window to type in. Open one and run:\n    python edtrawl.py",
    "school_not_found": "I couldn't find a school called \"{name}\". Check the spelling, or try just part of the name.",
    "err_school_usage": "Tell me which school, like this:\n    python edtrawl.py school \"Lincoln Elementary, Fresno\"",
    "school_many": "Showing the first {n}. Add more of the name to narrow it down.",
    "pick_prompt": "Type its number, or press Enter to skip.",
    "review_option": "  [{n}] {name}  {score}",
    "review_pick": "Type a number to choose one, n if none of these is right, or press Enter to skip.",
    "review_saved": "Saved. That settles {n:listing|listings}.",
    # ── fix round: hands of ten, back, by-number marks, resuming, settings, plainer errors ──
    "catch_intro_few": "{n:job|jobs} to look at, nearest first. Enter skips a card; q stops, and the rest wait for next time.",
    "triage_hand": "That's {done} of {total}: {tally}.\nGo on with the next {next}? Type y to keep going; Enter stops here.",
    "triage_pause": "Good place to stop: {tally}. Everything you didn't keep or toss will be here next time.",
    "triage_end_offline": "That's everything I had saved: {tally}. When you're online, this checks for new jobs:\n    python edtrawl.py",
    "back_done": "Back one card. Whatever you chose on it is undone.",
    "back_first": "This is the first card, so there's nothing before it.",
    "fetch_offline": "I couldn't check for new jobs, because this computer doesn't seem to be online. Here are the ones I'd already saved.",
    "marked_kept": "Marked as kept: {title}.",
    "marked_tossed": "Marked as tossed: {title}.",
    "already_applied": "You'd already marked this one as applied: {title}.",
    "err_posting_number": "That doesn't look like a job's number. It's the first thing on each line of a list, like 2295141. Nothing was changed. To see a list:\n    python edtrawl.py search",
    "err_drove_usage": "I need a school and the minutes, like this:\n    python edtrawl.py drove \"Lincoln Elementary, Fresno\" 30\nAdd --pm if it was the afternoon drive home.",
    "err_routing_word": "Say which one, roads or offline, like this:\n    python edtrawl.py routing offline",
    "err_routing_switch": "The road-distance server isn't answering, so I kept your current setting. Nothing is lost. Try again in a few minutes, or work offline:\n    python edtrawl.py routing offline",
    "err_routing_unreachable_none": "The road-distance server isn't answering, and there are no drive times saved for this home yet. Nothing is lost. To work offline instead:\n    python edtrawl.py routing offline",
    "reveal_none_setup": "There are no public schools within {radius} miles of that spot. Try a bigger number below, up to 100. If home is in the wrong place, press Ctrl-C to stop, then set it again, with your own address or ZIP code in place of the words:\n    python edtrawl.py home \"your address or ZIP code\"",
    "reveal_none_max": "There are no public schools within {radius} miles of that spot, which is as far as I look. If home is in the wrong place, set it again, with your own address or ZIP code in place of the words:\n    python edtrawl.py home \"your address or ZIP code\"",
    "reveal_nearest_here": "The nearest is {school}, less than a tenth of a mile away.",
    "home_declined_setup": "Nothing was sent. A ZIP code or a map position needs no geocoder.",
    "err_config_unknown": "I couldn't read {path}: it has a setting called \"{setting}\" that I don't know. Nothing was changed. Remove that line in a text editor, or delete the file. Your jobs and marks stay in the database; your settings go back to their defaults.",
    "err_config_value": "I couldn't read {path}: the setting \"{setting}\" has a value I can't use. Nothing was changed. Fix that line in a text editor, or delete the file. Your jobs and marks stay in the database; your settings go back to their defaults.",
    "err_config_broken": "I couldn't read {path}: it isn't written in the form I expect{where}. Nothing was changed. Fix that line in a text editor, or delete the file. Your jobs and marks stay in the database; your settings go back to their defaults.",
    "err_db_unreadable": "I couldn't read {path}, the file that holds your jobs and marks, so I stopped. To start again, move that file somewhere else and run the command below. The school files in the data folder aren't touched.\n    python edtrawl.py",
    "err_db_busy": "Another EdTrawl window seems to be busy, so I stopped. Try again in a minute.",
    "err_unexpected_nolog": "Something unexpected went wrong, so I stopped. I couldn't keep a note of the details here.",
    "no_listings_yet": "I haven't fetched any job listings yet, so there's nothing to show. To fetch them:\n    python edtrawl.py",
    "school_list_missing": "The school list isn't loaded yet, so I can't look up schools. Setup loads it:\n    python edtrawl.py",
    "school_ambiguous": "That could be more than one school, so nothing was changed. Add more of the name, or the city after a comma, like this:\n    python edtrawl.py {example}",
    "pick_again": "Type a number from 1 to {n}, or press Enter to skip.",
    "review_again": "Type a number from 1 to {n}, n if none of these is right, or press Enter to skip.",
    "drove_out_of_range": "{school} is outside the {radius} miles I'm looking, so I have no drive time for it to fit. To look farther:\n    python edtrawl.py radius {wider}",
    "title_missing": "(no title)",
}

# CDE student-group and race/ethnicity columns, in CDE's published order. Shown as figures only: never
# sorted, ranked, coloured or summarised (PLAN §4 "No judgement of schools").
GROUPS = (("english_learner_pct", "English learners"),
          ("socioeconomically_disadvantaged_pct", "socioeconomically disadvantaged"),
          ("students_with_disabilities_pct", "students with disabilities"),
          ("foster_pct", "foster"), ("homeless_pct", "homeless"), ("migrant_pct", "migrant"))
ETHNICITY = (("african_american_pct", "African American"), ("american_indian_pct", "American Indian"),
             ("asian_pct", "Asian"), ("filipino_pct", "Filipino"), ("hispanic_pct", "Hispanic"),
             ("pacific_islander_pct", "Pacific Islander"), ("white_pct", "White"),
             ("two_or_more_races_pct", "two or more races"), ("not_reported_pct", "not reported"))

# ── Terminal capabilities, detected once ─────────────────────────────────────────────────────────
CAPS = {}
_ASCII = str.maketrans({"·": "-", "─": "-", "–": "-", "—": "-", "©": "(c)"})


def configure(plain=False, no_emoji=False, interactive=None):
    """Read the terminal once. `--plain` and NO_COLOR turn colour and emoji off; a pipe turns off animation too."""
    out = sys.stdout
    tty = _isatty(out)
    enc = getattr(out, "encoding", None) or "ascii"
    utf8 = enc.lower().replace("-", "") == "utf8"
    CAPS.update(
        tty=tty, encoding=enc, utf8=utf8,
        interactive=_isatty(sys.stdin) if interactive is None else interactive,
        color=tty and not plain and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb",
        emoji=tty and utf8 and not plain and not no_emoji,
        # Never wider than 80 (a card is a card, not a spreadsheet) and never narrower than 40.
        width=max(40, min(80, shutil.get_terminal_size((80, 24)).columns)) if tty else 80,
    )


def _isatty(stream):
    try:
        return stream.isatty()
    except (AttributeError, ValueError):
        return False


configure()


def _paint(s, code):
    return f"\x1b[{code}m{s}\x1b[0m" if CAPS["color"] and s else s


def _accent(s):
    return _paint(s, "36")  # the one accent colour; never the only carrier of meaning


def _keys(s):
    return re.sub(r"\[(\w)\]", lambda m: "[" + _accent(m.group(1)) + "]", s)


_progress_open = [False, 0.0]  # a progress line is on screen without its newline; time of last draw


def _write(s):
    if _progress_open[0]:
        s = "\n" + s
        _progress_open[0] = False
    if not CAPS["utf8"]:
        enc = CAPS["encoding"]
        s = s.translate(_ASCII).encode(enc, "replace").decode(enc)
    sys.stdout.write(s)
    sys.stdout.flush()


# ── Untrusted text ───────────────────────────────────────────────────────────────────────────────
_ESCAPES = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?"   # OSC (titles, hyperlinks)
                      r"|\x1b\[[0-?]*[ -/]*[@-~]"            # CSI (colour, cursor, clear screen)
                      r"|\x1b[@-_]?|\x9b[0-?]*[ -/]*[@-~]")  # other escapes, 8-bit CSI


def clean(text):
    """Text safe for one terminal line: entities decoded, escape sequences and control/format
    characters (including bidi overrides) removed, whitespace collapsed. None becomes ''."""
    if text is None:
        return ""
    text = _ESCAPES.sub("", html.unescape(str(text)))
    text = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in text)
    return " ".join(text.split())


# ── Formatting copy ──────────────────────────────────────────────────────────────────────────────
_PLURAL = re.compile(r"\{(\w+):([^{}|]*)\|([^{}]*)\}")


class _Blank(dict):
    def __missing__(self, key):  # a missing value prints as nothing rather than crashing an error message
        return ""


def launcher():
    """The name to type in front of edtrawl.py: many Macs and Linux machines only have python3."""
    return "python" if shutil.which("python") else "python3"


def text(key, **values):
    """COPY[key] filled in. String values are cleaned; `{n:one|many}` gives "1 one" / "3 many".
    Commands in COPY are written `python edtrawl.py`; the launcher that exists here replaces `python`."""
    values = {k: clean(v) if isinstance(v, str) else v for k, v in values.items()}
    template = _PLURAL.sub(lambda m: count(values.get(m.group(1)), m.group(2), m.group(3))
                           .replace("{", "{{").replace("}", "}}"), COPY[key])
    return template.format_map(_Blank(values)).replace("python edtrawl.py", launcher() + " edtrawl.py")


def count(n, noun, plural=None):
    n = n or 0
    return f"{n:,} {noun if n == 1 else plural or noun + 's'}"


def tally(kept=0, tossed=0, skipped=0):
    parts = [text(k, n=n) for k, n in (("tally_kept", kept), ("tally_tossed", tossed),
                                        ("tally_skipped", skipped)) if n]
    return ", ".join(parts) or text("tally_none")


def _wrap(s, width):
    """Wrap each line to the width, keeping its indent. Lines indented four spaces are commands: untouched."""
    out = []
    for line in s.split("\n"):
        lead = line[:len(line) - len(line.lstrip(" "))]
        if lead.startswith("    ") or len(line) < width:
            out.append(line)
        else:
            out += textwrap.wrap(line.strip(), width - 1, initial_indent=lead, break_on_hyphens=False,
                                 subsequent_indent=lead + ("  " if lead else ""))
    return "\n".join(out)


def _show(s):
    lines = [_accent(l) if l.startswith("    ") else _keys(l) for l in s.split("\n")]
    _write("\n".join(lines) + "\n")


def say(key, **values):
    """Print one COPY message, wrapped to the terminal. The way every other module speaks."""
    _show(_wrap(text(key, **values), CAPS["width"]))


def show(block):
    """Print a block a renderer already built (job_card, school_card, table)."""
    _write(block + "\n")


# ── Formatters (pure) ────────────────────────────────────────────────────────────────────────────
def _approx(m, provider=None):
    if m is None:
        return ""
    # Every modelled time carries "~". Only a drive the user typed in ('known') is shown bare.
    return ("" if provider == "known" else "~") + str(max(1, round(m)))


def minutes(m, provider=None):
    """'~22 min', or '' when there is no time."""
    return _approx(m, provider) + " min" if m is not None else ""


def week(am, pm):
    total = (am + pm) * 5
    if total < 60:
        return text("week_minutes", m=max(5, round(total / 5) * 5))
    h = round(total / 30) / 2  # nearest half hour
    return text("week_hour") if h == 1 else text("week_hours", h=f"{h:g}")


def drive_line(am, pm, provider=None):
    if am is not None and pm is not None:
        return text("drive_both", am=minutes(am, provider), pm=_approx(pm, provider), week=week(am, pm))
    if am is not None:
        return text("drive_am_only", am=minutes(am, provider))
    if pm is not None:
        return text("drive_pm_only", pm=_approx(pm, provider))
    return text("drive_none")


def range_line(lo, hi, n, provider=None):
    if lo is None or hi is None or not n:
        return text("drive_none")
    key = "drive_range_one" if n == 1 else "drive_range_same" if round(lo) == round(hi) else "drive_range"
    return text(key, lo=_approx(lo, provider), hi=_approx(hi, provider), n=n)


def trend(now, before):
    """'steady (+1% in a year)', or '' when either year is missing."""
    if not now or not before:
        return ""
    pct = round((now - before) / before * 100)
    if now == before or pct == 0:
        return text("trend_same")
    key = "trend_up" if pct >= 2 else "trend_down" if pct <= -2 else "trend_flat"
    return text(key, pct=f"{pct:+d}%")


def _date(value):
    """A date from an ISO string, date or datetime. Instants are read in California time."""
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            try:
                value = datetime.date.fromisoformat(value.strip()[:10])
            except ValueError:
                return None
    if isinstance(value, datetime.datetime):
        if value.tzinfo:
            try:
                from zoneinfo import ZoneInfo
                value = value.astimezone(ZoneInfo("America/Los_Angeles"))
            except Exception:  # no tz database on this machine: local time is the next best
                value = value.astimezone()
        return value.date()
    return value


def _short(d):
    return f"{d:%b} {d.day}"


def deadline(value, today=None):
    """'closes Fri (3 days)', 'closes today', 'closed Nov 12', or '' when there is none."""
    d = _date(value)
    if d is None:
        return ""
    days = (d - (today or datetime.date.today())).days
    if days < 0:
        return text("deadline_passed", date=_short(d))
    if days == 0:
        return text("deadline_today")
    if days == 1:
        return text("deadline_tomorrow")
    if days < 7:
        return text("deadline_soon", day=f"{d:%a}", n=days)
    return text("deadline_later", date=_short(d))


def since(value, today=None):
    """'earlier today', 'yesterday', 'Monday' within a week, else 'Oct 30'."""
    d = _date(value)
    if d is None:
        return ""
    days = ((today or datetime.date.today()) - d).days
    if days <= 0:
        return text("since_today")
    if days == 1:
        return text("since_yesterday")
    return f"{d:%A}" if days < 7 else _short(d)


def grades(low, high):
    def g(x):
        x = clean(x)
        return "K" if x == "KG" else x.lstrip("0") or x
    low, high = g(low), g(high)
    return f"{low}–{high}" if low and high and low != high else low or high


# ── Renderers ────────────────────────────────────────────────────────────────────────────────────
def _pack(value, avail):
    """Wrap preferring breaks at ' · ' and three-space gaps; long pieces wrap normally."""
    parts = re.split(r"( · |   )", value)
    lines, cur = [], parts[0]
    for sep, piece in zip(parts[1::2], parts[2::2]):
        if len(cur) + len(sep) + len(piece) <= avail:
            cur += sep + piece
        else:
            lines.append(cur)
            cur = piece
    lines.append(cur)
    return [w for line in lines for w in (textwrap.wrap(line, avail, break_on_hyphens=False) or [""])]


def _clip(lines, n, avail):
    if len(lines) > n:
        lines = lines[:n]
        lines[-1] = lines[-1][:avail - 3].rstrip() + "..."
    return lines


def _field(label, value, w, label_w=8, max_lines=3):
    pad = " " * (label_w + 1)
    lines = _clip(_pack(value, w - len(pad)), max_lines, w - len(pad))
    return [(" " + f"{text(label):<{label_w}}" if i == 0 else pad) + line for i, line in enumerate(lines)]


def _rule(left, right, w):
    head = f" ── {left} " if left else " "
    tail = f" {right}" if right else ""
    return head + "─" * max(3, w - len(head) - len(tail)) + tail


def job_card(row, i, n, width=None, today=None):
    """One job, as label: value lines. `row` is a job_search row (dict or sqlite3.Row)."""
    row = dict(row)
    w = (width or CAPS["width"]) - 1  # leave the last column empty so no terminal wraps early
    lines = [_accent(_rule(f"{i} of {n}", deadline(row.get("deadline"), today), w))]
    title = textwrap.wrap(clean(row.get("title")) or text("title_missing"), w - 1, break_on_hyphens=False) or [""]
    lines += [_paint(" " + l, "1") for l in _clip(title, 2, w - 1)]
    school = clean(row.get("school_name")) if row.get("cds_code") else ""
    where = " · ".join(x for x in (school or text("site_not_listed"),
                                   clean(row.get("district_name")) or clean(row.get("district_raw"))) if x)
    lines += [" " + l for l in _clip(_pack(where, w - 1), 2, w - 1)]
    provider = row.get("provider")
    if row.get("cds_code"):
        drive = drive_line(row.get("am_minutes"), row.get("pm_minutes"), provider)
    else:
        drive = range_line(row.get("district_min_minutes"), row.get("district_max_minutes"),
                           row.get("district_schools_in_range"), provider)
    lines += _field("label_drive", drive, w)
    facts = []
    if row.get("cds_code") and row.get("enroll_total"):
        t = trend(row.get("enroll_total"), row.get("prev_enroll_total"))
        facts.append(text("students", n=row["enroll_total"]) + (", " + t if t else ""))
    if row.get("cds_code") and row.get("staff_teacher"):
        facts.append(text("teachers", n=row["staff_teacher"]))
    if row.get("cds_code") and row.get("title_i") == "Y":
        facts.append(text("title_i"))
    if facts:
        lines += _field("label_school", " · ".join(facts), w)
    lines += _field("label_pay", clean(row.get("salary_info")) or text("pay_not_listed"), w, max_lines=2)
    return "\n".join(lines)


def _pct(row, columns):
    return " · ".join(f"{label} {row[c]:.0f}%" for c, label in columns if row.get(c) is not None)


def school_card(row, width=None, rush_pm=None):
    """The [m]ore card: facts about one school, as published. No adjectives, no scores, no order by size.
    `row` is a schools + school_years row, optionally with prev_enroll_total, am/pm_minutes, provider."""
    row = dict(row)
    w = (width or CAPS["width"]) - 1
    lines = [_accent(_rule(clean(row.get("school_name"))[:w - 8], "", w))]
    place = " · ".join(x for x in (clean(row.get("district_name")), clean(row.get("city")),
                                   clean(row.get("county_name")) and clean(row.get("county_name")) + " County") if x)
    lines += [" " + l for l in _pack(place, w - 1)]
    kind = [grades(row.get("grade_low"), row.get("grade_high")), clean(row.get("school_level"))]
    kind += [text("charter")] if row.get("charter") == "Y" else []
    kind += [text("magnet")] if row.get("magnet") == "Y" else []
    kind += [text("virtual_" + row["virtual"])] if row.get("virtual") in ("F", "V") else []
    kind += [text("title_i")] if row.get("title_i") == "Y" else []
    field = lambda label, value, **kw: _field(label, value, w, label_w=10, **kw) if value else []
    lines += field("label_grades", " · ".join(k for k in kind if k))
    if row.get("enroll_total"):
        t = trend(row["enroll_total"], row.get("prev_enroll_total"))
        lines += field("label_students", f"{row['enroll_total']:,}" + (", " + t if t else ""))
    staff = [text("teachers", n=row["staff_teacher"])] if row.get("staff_teacher") else []
    staff += [text("staff_total", n=row["staff_total"])] if row.get("staff_total") else []
    lines += field("label_staff", " · ".join(staff))
    lines += field("label_groups", _pct(row, GROUPS), max_lines=4)
    lines += field("label_ethnicity", _pct(row, ETHNICITY), max_lines=4)
    if "am_minutes" in row or "pm_minutes" in row:
        lines += field("label_drive", drive_line(row.get("am_minutes"), row.get("pm_minutes"), row.get("provider")))
    lines += field("label_website", clean(row.get("website")))
    notes = [text("more_times")] + ([text("more_rush")] if rush_pm and rush_pm > 1.3 else [])
    if row.get("academic_year"):
        notes.append(text("more_source", year=clean(row["academic_year"])))
    for note in notes:
        lines += textwrap.wrap(note, w - 1, initial_indent=" ", subsequent_indent=" ")
    return "\n".join(lines)


def _table_drive(row):
    if row.get("cds_code"):
        m = [x for x in (row.get("am_minutes"), row.get("pm_minutes")) if x is not None]
        return _approx(max(m), row.get("provider")) if m else "-"
    lo, hi = row.get("district_min_minutes"), row.get("district_max_minutes")
    return f"{_approx(lo, row.get('provider'))}-{round(hi)}" if lo is not None and hi is not None else "-"


def table(rows, width=None, today=None):
    """A compact list, one job per line: number, slower drive, deadline, title · place."""
    w = (width or CAPS["width"]) - 1
    lines = [" " + text("table_head")]
    today = today or datetime.date.today()
    for row in map(dict, rows):
        d = _date(row.get("deadline"))
        closes = ("-" if d is None else text("table_today") if d == today
                  else _short(d) if d > today else text("table_closed"))
        where = clean(row.get("school_name")) if row.get("cds_code") else ""
        where = where or clean(row.get("district_name")) or clean(row.get("district_raw"))
        job = (clean(row.get("title")) or text("title_missing")) + (" · " + where if where else "")
        line = f" {row.get('posting_id', ''):<8} {_table_drive(row):<8} {closes:<8} {job}"
        lines.append(line if len(line) <= w else line[:w - 3].rstrip() + "...")
    return "\n".join(lines)


def progress(done, total, label):
    """An `on_progress(done, total, label)` callback. `label` is a COPY key or plain text.
    On a terminal: one line that redraws, with a small boat crossing it. Otherwise: one line when done."""
    name = text(label) if label in COPY else clean(label)
    final = bool(total) and done >= total
    if not CAPS["tty"]:
        if final:
            _write(f"{name}: {done:,} of {total:,}.\n")
        return
    now = time.monotonic()
    if not final and now - _progress_open[1] < 0.08:  # redraw at most ~12 times a second
        return
    _progress_open[1] = now
    counted = f"{done:,} of {total:,}" if total else f"{done:,}"
    boat = "⛵" if CAPS["emoji"] else "\\_/"  # the emoji is two columns wide, the ASCII hull three
    w = CAPS["width"] - 1
    track = min(28, w - len(name) - len(counted) - 8)
    if track < 4:  # too narrow for the boat: name and count only, so the line still fits and can redraw
        sys.stdout.write("\r" + f" {name[:max(0, w - len(counted) - 3)]}  {counted}".ljust(w))
        if final:
            sys.stdout.write("\n")
            _progress_open[1] = 0.0
        sys.stdout.flush()
        _progress_open[0] = not final
        return
    pos = round(min(done / total, 1) * track) if total else done % (track + 1)
    water = "·" if CAPS["utf8"] else "."
    plain = f" {name}  {'~' * pos}{boat}{water * (track - pos)}  {counted}"
    sys.stdout.write("\r" + plain.ljust(w - CAPS["emoji"]).replace(boat, _accent(boat), 1))  # the emoji is 1 char, 2 columns
    if final:
        sys.stdout.write("\n")
        _progress_open[1] = 0.0  # the next progress line draws its first frame at once
    sys.stdout.flush()
    _progress_open[0] = not final


WORDS = {"k": "keep", "t": "toss", "s": "skip", "o": "open", "m": "more", "b": "back", "q": "quit",
         "y": "yes", "n": "no"}  # a lettered choice may also be typed as its whole word
_UNSET = object()


def ask(key, choices=None, default=None, words=None, eof=_UNSET, **values):
    """Show COPY[key] and read one line. With `choices` (e.g. "ktsomq") return the letter chosen: exactly one
    letter or that letter's whole word (WORDS, overridden by `words`), any case, spaces ignored. Anything else,
    "ok" or "thanks" included, asks again. Enter gives `default`. At end of input returns `eof` (default: `default`)
    so a caller can tell nobody is there. Never blocks when stdin is not a terminal."""
    if not CAPS["interactive"]:
        return default
    w = CAPS["width"]
    s = text(key, **values)
    if key + "_short" in COPY and max(map(len, s.split("\n"))) > w - 1:
        s = text(key + "_short", **values)
    _show(_wrap(s, w))
    names = {**WORDS, **(words or {})}
    while True:
        try:
            answer = input(" > ").strip()
        except EOFError:
            return default if eof is _UNSET else eof
        if not choices:
            return answer or default
        if not answer and default is not None:
            return default
        low = answer.lower()
        for letter in choices:
            if low == letter or low == names.get(letter):
                return letter
        say("ask_again", choices=", ".join(choices))
