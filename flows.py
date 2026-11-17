"""Guided flows: setup, the daily session, the triage deck, and the small commands around them.

Every sentence is a ui.COPY key. Each command is cmd(args, conn, cfg) -> exit code (None = 0), like edtrawl.py's.
"""
import re
import statistics
import textwrap
import webbrowser
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlparse

import config as config_mod
import edjoin
import query
import travel
import ui

cli = None  # the edtrawl module, set by it at import: flows reuses its cmd_ingest, cmd_fetch, locate and prog
YEARS = ("2025-26", "2024-25")  # both, so enrollment trends work
SHORT = lambda d: f"{d:%b} {d.day}"


# ---- small helpers ----

def _has_home(conn, cfg):
    return bool(cfg.home_key and conn.execute("SELECT 1 FROM homes WHERE home_key = ?", (cfg.home_key,)).fetchone())


def _line(key, **values):
    """A typed line for a question ui.ask can't carry (its `default` is not a template value).
    '' for Enter, None at end of input. Only used inside setup, which already requires a terminal."""
    ui.say(key, **values)
    try:
        return input(" > ").strip()
    except EOFError:
        return None


def _posting(value):
    """A job number typed on the command line, as an int, or None. Read as text so the message is ours, not argparse's."""
    return int(value) if value and re.fullmatch(r"\s*\d{1,12}\s*", str(value)) else None


def say_none(radius, setup=False):
    """No school within the radius: a step that works. The suggestion is capped at 100, the most I look."""
    radius = int(radius)
    key = "reveal_none_max" if radius >= 100 else "reveal_none_setup" if setup else "reveal_none"
    ui.say(key, radius=radius, wider=min(100, radius * 2))


def routing_down(conn, cfg):
    """Say the road server is down, truthfully about saved drive times. True when this home has some."""
    has = _count(conn, "SELECT COUNT(*) FROM commutes WHERE home_key = ?", cfg.home_key)
    ui.say("err_routing_unreachable" if has else "err_routing_unreachable_none")
    return bool(has)


def _step(n, title_key):
    ui.say("setup_step", n=n, total=4, title=ui.text(title_key))


def _count(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def _mark(conn, posting_id, status):
    """Write one decision. True when it is the first of its kind ever, so the caller can say the warm line.
    Decided from job_marks itself: a keeper that was later applied for still counts as a first keep."""
    first = status != "tossed" and not conn.execute(
        "SELECT 1 FROM job_marks WHERE status = ? OR (? = 'kept' AND status = 'applied')", (status, status)).fetchone()
    conn.execute("INSERT INTO job_marks (posting_id, status, marked_on) VALUES (?, ?, ?) "
                 "ON CONFLICT(posting_id) DO UPDATE SET status = excluded.status, marked_on = excluded.marked_on",
                 (posting_id, status, datetime.now().isoformat(timespec="seconds")))
    conn.commit()  # at once: Ctrl-C a moment later must not lose it
    return first


def _closed(deadline, today):
    # A keeper is closed when its deadline has passed. Never inferred from last_seen: later casts only look
    # 7 days back, so an older open job is simply not re-seen.
    return bool(deadline) and deadline < today.isoformat()


def _typical(conn, cfg, d):
    """Median minutes (after the personal factor) over every school in range, for 'am' or 'pm'."""
    vals = [r[0] for r in conn.execute(
        f"SELECT c.{d}_minutes * h.factor_{d} FROM commutes c JOIN homes h ON h.home_key = c.home_key "
        f"WHERE c.home_key = ? AND c.{d}_minutes IS NOT NULL", (cfg.home_key,))]
    return statistics.median(vals) if vals else None


def find_schools(conn, cfg, text, direction=None):
    """Up to 10 schools by name fragment or 14-digit code, in-range ones first. With a direction ('am'/'pm'),
    only schools that have a drive time that way for this home."""
    text = text.strip()
    name, comma, city = text.rpartition(",")  # "Name, City" is how the program's own lists print a school
    if re.fullmatch(r"\d{14}", text):
        cond, args = "s.cds_code = ?", [text]
    elif comma and name.strip() and city.strip():
        cond, args = ("instr(lower(s.school_name), lower(?)) > 0 AND instr(lower(s.city), lower(?)) > 0",
                      [name.strip(), city.strip()])
    else:
        cond, args = "instr(lower(s.school_name), lower(?)) > 0", [text]
    if direction:
        cond += f" AND c.{direction}_minutes IS NOT NULL"
    rows = conn.execute(
        f"SELECT s.cds_code, s.school_name, s.city, c.cds_code IS NOT NULL AS near FROM schools s "
        f"LEFT JOIN commutes c ON c.cds_code = s.cds_code AND c.home_key = ? WHERE {cond} "
        f"ORDER BY near DESC, s.school_name LIMIT 10", [cfg.home_key] + args).fetchall()
    return [dict(r) for r in rows]


def _choose(found, name, example=None):
    """The one school, or None when the user skips, answers badly, or nobody can be asked.
    With `example` (the command tail), None also says that nothing was changed and how to narrow it."""
    if len(found) == 1:
        return found[0]
    ui.say("known_drive_which", name=name)
    shown = found[:9]
    for n, sc in enumerate(shown, 1):
        ui.say("known_drive_option", n=n, school=sc["school_name"], city=sc["city"])
    if len(found) > 9:
        ui.say("school_many", n=9)
    key = "pick_prompt"
    while True:
        answer = ui.ask(key, n=len(shown))
        if not answer:
            break
        if answer.isdigit() and 1 <= int(answer) <= len(shown):
            return shown[int(answer) - 1]
        key = "pick_again"  # a bad number asks again rather than guessing
    if example:
        ui.say("school_ambiguous", example=example)


def _schools_loaded(conn):
    return bool(conn.execute("SELECT 1 FROM schools LIMIT 1").fetchone())


def show_school(conn, cfg, code):
    cols = ", ".join("cur." + c for c, _ in ui.GROUPS + ui.ETHNICITY)
    row = conn.execute(
        f"SELECT s.*, cur.academic_year, cur.enroll_total, cur.staff_total, cur.staff_teacher, cur.title_i, {cols}, "
        f"prev.enroll_total AS prev_enroll_total FROM schools s "
        f"LEFT JOIN school_years cur ON cur.cds_code = s.cds_code AND cur.academic_year = "
        f"(SELECT MAX(academic_year) FROM school_years WHERE cds_code = s.cds_code) "
        f"LEFT JOIN school_years prev ON prev.cds_code = s.cds_code AND prev.academic_year = "
        f"(SELECT MAX(academic_year) FROM school_years WHERE cds_code = s.cds_code AND academic_year < cur.academic_year) "
        f"WHERE s.cds_code = ?", (code,)).fetchone()
    row = dict(row)
    drive = conn.execute(
        "SELECT c.am_minutes * h.factor_am AS am_minutes, c.pm_minutes * h.factor_pm AS pm_minutes, c.provider "
        "FROM commutes c JOIN homes h ON h.home_key = c.home_key WHERE c.cds_code = ? AND c.home_key = ?",
        (code, cfg.home_key)).fetchone()
    if drive:
        row.update(dict(drive))
    county = row.get("geo_county_name") or row.get("county_name")
    ui.show(ui.school_card(row, rush_pm=travel.rush(county, "pm", cfg)))


def _record_known(conn, cfg, code, minutes, d):
    """Record a known drive and show its result: that drive (estimated vs said), then the typical school
    (median over schools in range) before and after."""
    before = _typical(conn, cfg, d)
    est = conn.execute(f"SELECT c.{d}_minutes * h.factor_{d} FROM commutes c JOIN homes h ON h.home_key = c.home_key "
                       f"WHERE c.home_key = ? AND c.cds_code = ?", (cfg.home_key, code)).fetchone()[0]
    name = conn.execute("SELECT school_name FROM schools WHERE cds_code = ?", (code,)).fetchone()[0]
    factor = travel.record_drive(conn, cfg, code, minutes, d)[0 if d == "am" else 1]
    after = _typical(conn, cfg, d)
    if round(before) == round(after):
        return ui.say("drove_unchanged")
    ui.say("drove_adjusted_" + d, school=name, minutes=f"{minutes:g}", est=round(est), before=round(before),
           after=round(after))
    if factor in (0.5, 2.0):  # sitting on a limit means the real ratio was at or beyond it
        ui.say("drove_clamped")


def _ask_minutes(key, **values):
    while True:
        answer = ui.ask(key, **values)
        if not answer:
            return None
        try:
            m = float(answer)
        except ValueError:
            m = 0
        if 1 <= m <= 240:
            return m
        ui.say("err_minutes")


# ---- setup ----

def setup(args, conn, cfg):
    fresh = not _has_home(conn, cfg)
    if fresh:
        if not ui.CAPS["interactive"]:
            return ui.say("setup_needs_terminal") or 1
        ui.say("welcome")
    if _load_schools(conn):  # first: a ZIP home is placed by the schools already loaded
        return 1
    if fresh:
        _step(1, "step_home")
        if not _ask_home(conn, cfg, args):
            return 1
    first_cast = not _count(conn, "SELECT COUNT(*) FROM commutes WHERE home_key = ?", cfg.home_key)
    if first_cast:
        _step(2, "step_schools")
        if not _reveal(conn, cfg, args):
            return 1
        _step(3, "step_routing")
        if not _drive_times(conn, cfg, args):
            return 1
    if not _count(conn, "SELECT COUNT(*) FROM known_drives WHERE home_key = ?", cfg.home_key):
        _step(4, "step_known_drive")
        _known_drive(conn, cfg)
    ui.say("setup_done")
    if first_cast:  # straight into the first catch; a later `setup` only fills in what was skipped
        return session(conn, cfg)


def _load_schools(conn):
    have = {r[0] for r in conn.execute("SELECT DISTINCT academic_year FROM school_years")}
    missing = [y for y in YEARS if y not in have]
    if missing:  # cmd_ingest says what went wrong; whatever loaded stays loaded
        return cli.cmd_ingest(SimpleNamespace(file=None, year=missing), conn, None)


def _ask_home(conn, cfg, args):
    while True:
        answer = _line("home_ask")
        if answer is None:  # end of input: nobody is there to answer
            return ui.say("stopped") or False
        try:
            lat, lng, is_zip = cli.locate(conn, answer)
            travel.set_home(conn, cfg, lat, lng, args.config)
        except cli.HomeProblem as p:
            ui.say(p.key + "_setup" if p.key + "_setup" in ui.COPY else p.key)
        except travel.UnknownZip:
            ui.say("err_unknown_zip", zip=answer if re.fullmatch(r"\d{5}", answer) else "")
        except travel.OutsideCalifornia:
            ui.say("err_outside_california")
        except travel.GeocoderUnavailable:
            ui.say("err_geocoder_unreachable_setup")
        else:
            ui.say("home_saved")
            if is_zip:
                ui.say("home_zip_note")
            return True


def _say_reveal(conn, cfg, near):
    info = {r[0]: r for r in conn.execute("SELECT cds_code, district_code, school_name FROM schools")}
    ui.say("reveal", radius=cfg.radius_miles, schools=len(near),
           districts=len({info[s["cds_code"]][1] for s in near}))
    miles = round(near[0]["miles"], 1)
    ui.say("reveal_nearest" if miles else "reveal_nearest_here", school=info[near[0]["cds_code"]][2], miles=miles)


def _reveal(conn, cfg, args):
    offer = int(cfg.radius_miles)  # Enter keeps it; 20 suits a city, a rural home may want more
    while True:
        answer = _line("radius_ask", default=offer)
        if answer is None:
            return ui.say("stopped") or False
        try:
            miles = int(answer or offer)
        except ValueError:
            miles = 0
        if not 1 <= miles <= 100:
            ui.say("err_radius")
            continue
        if miles != cfg.radius_miles:
            cfg.radius_miles = miles
            config_mod.set("radius_miles", miles, args.config)
        near = travel.schools_in_radius(conn, cfg)
        if near:
            break
        say_none(miles, setup=True)
        if miles >= 100:
            return False
        offer = min(100, miles * 2)
    _say_reveal(conn, cfg, near)
    return True


def _say_ready(conn, cfg):
    """One line: how many schools have drive times, by which method, and the command to switch.
    The method is the configured one: switching to offline clears road rows first, so the two always agree."""
    ui.say("routing_saved_roads" if cfg.routing == "osrm" else "routing_saved_offline",
           n=_count(conn, "SELECT COUNT(*) FROM commutes WHERE home_key = ?", cfg.home_key))
    if cfg.routing == "osrm":
        ui.say("attribution_osm")


def _drop_road_times(conn, cfg):
    conn.execute("DELETE FROM commutes WHERE home_key = ? AND provider = 'osrm'", (cfg.home_key,))
    conn.commit()


def _drive_times(conn, cfg, args):
    server = urlparse(cfg.osrm_url).netloc
    while True:
        choice = ui.ask("routing_ask", choices="or", default="o", words={"o": "offline", "r": "roads"}, eof=None,
                        server=server)
        if choice is None:  # input ended: nobody chose, so do not go on to fetch with a default
            return ui.say("stopped") or False
        cfg.routing = "osrm" if choice == "r" else "estimate"
        try:
            travel.update_commutes(conn, cfg, on_progress=cli.prog("progress_drives"))
            break
        except travel.RoutingUnavailable:  # batches already done are dropped, so "offline" stays true; ask again
            cfg.routing = "estimate"
            _drop_road_times(conn, cfg)
            ui.say("err_routing_unreachable_setup")
    config_mod.set("routing", cfg.routing, args.config)
    _say_ready(conn, cfg)  # only now that the drive times exist
    return True


def _known_drive(conn, cfg):
    while True:
        name = ui.ask("known_drive_ask")  # Enter (or no terminal) skips
        if not name:
            return
        found = find_schools(conn, cfg, name, "am")
        if not found:
            ui.say("known_drive_not_found", name=name)
            continue
        pick = _choose(found, name)
        if pick is None:
            return
        minutes = _ask_minutes("known_drive_minutes", school=pick["school_name"])
        if minutes is not None:
            _record_known(conn, cfg, pick["cds_code"], minutes, "am")
        return


# ---- settings commands ----

def radius(args, conn, cfg):
    if not _has_home(conn, cfg):
        raise travel.NoHome("no home is set")
    try:
        miles = int(str(args.miles or "").strip())
    except ValueError:
        miles = 0
    if not 1 <= miles <= 100:
        return ui.say("err_radius") or 1
    old, cfg.radius_miles = cfg.radius_miles, miles
    near = travel.schools_in_radius(conn, cfg)
    if not near:  # nothing to look at: leave the setting alone
        cfg.radius_miles = old
        return say_none(miles) or 1
    config_mod.set("radius_miles", miles, args.config)
    try:
        travel.update_commutes(conn, cfg, on_progress=cli.prog("progress_drives"))
    except travel.RoutingUnavailable:
        routing_down(conn, cfg)
        return 1
    _say_reveal(conn, cfg, near)
    _say_ready(conn, cfg)


def routing(args, conn, cfg):
    want = {"roads": "osrm", "road": "osrm", "offline": "estimate"}.get((args.choice or "").strip().lower())
    if not want:
        return ui.say("err_routing_word") or 1
    if not _has_home(conn, cfg):
        raise travel.NoHome("no home is set")
    old, cfg.routing = cfg.routing, want
    if want == "estimate":
        _drop_road_times(conn, cfg)  # estimate rows are never "fresher" than road ones, so clear them to really switch
    try:
        travel.update_commutes(conn, cfg, on_progress=cli.prog("progress_drives"))
    except travel.RoutingUnavailable:
        cfg.routing = old  # keep the previous setting, and say so
        if old == "estimate":  # batches that did finish are road rows: drop them so the cache matches the setting
            _drop_road_times(conn, cfg)
            travel.update_commutes(conn, cfg)
        return ui.say("err_routing_switch") or 1
    config_mod.set("routing", want, args.config)
    _say_ready(conn, cfg)


# ---- the daily session ----

def go(args, conn, cfg):
    if not _has_home(conn, cfg) or (ui.CAPS["interactive"] and not _count(
            conn, "SELECT COUNT(*) FROM commutes WHERE home_key = ?", cfg.home_key)):
        return setup(args, conn, cfg)  # no home, or setup was interrupted before drive times: carry on from there
    try:
        r = travel.update_commutes(conn, cfg, on_progress=cli.prog("progress_drives"))  # cheap when fresh
    except travel.RoutingUnavailable:
        if not routing_down(conn, cfg):
            return 1
        r = {"in_range": 1}
    if not r["in_range"]:
        return say_none(cfg.radius_miles) or 1
    return session(conn, cfg)


def _deck_rows(conn, cfg, today):
    # New = no mark, a drive time (school in range, or a district with schools in range), not already closed.
    return [r for r in query.search(conn, cfg, new_only=True, limit=None)
            if r["drive_minutes"] is not None and not _closed(r["deadline"], today)]


def session(conn, cfg):
    last = conn.execute("SELECT MAX(last_seen) FROM jobs").fetchone()[0]
    prev = date.fromisoformat(last) if last else None
    # 31 days on the first cast or after more than a week away; otherwise 7 (edjoin accepts 1, 7 or 31)
    days = 31 if prev is None or (date.today() - prev).days > 6 else 7  # 7 days back from a cast 7 days ago could miss a day
    offline = False
    try:
        code = cli.cmd_fetch(SimpleNamespace(days=days, limit=None, from_file=None), conn, cfg)
    except cli.OFFLINE:
        if not _deck_rows(conn, cfg, date.today()):
            raise  # nothing saved to show: stop with the offline message
        ui.say("fetch_offline")
        code, offline = None, True
    except edjoin.EdjoinError as e:  # refused or failing partway: what was already saved is still worth showing
        if not _deck_rows(conn, cfg, date.today()):
            raise
        ui.say(cli._speak(e, None)[0])
        code, offline = None, True
    return code or deck(conn, cfg, prev, offline)


def _card(conn, cfg, row, i, n):
    """Show one card and return k, t, s, b or q. `open` and `more` come back to the same card.
    End of input counts as q: nobody is there, so the rest must not be skipped silently."""
    ui.show(ui.job_card(row, i, n))
    district = not row["cds_code"]  # no school to tell about
    while True:
        key = ui.ask("triage_keys_district" if district else "triage_keys",
                     choices="ktsobq" if district else "ktsobmq", default="s", eof="q")
        if key == "o":
            try:
                opened = webbrowser.open(row["url"])
            except Exception:
                opened = False
            ui.say("opened") if opened else ui.say("err_open_browser", url=row["url"])
        elif key == "m":
            show_school(conn, cfg, row["cds_code"])
            ui.show(ui.job_card(row, i, n))
        else:
            return key


HAND = 10  # cards dealt before asking whether to go on


def deck(conn, cfg, prev, offline=False):
    today = date.today()
    rows = _deck_rows(conn, cfg, today)
    if prev:
        shut = _count(conn, "SELECT COUNT(*) FROM job_marks m JOIN jobs j USING (posting_id) WHERE m.status = 'kept' "
                      "AND j.deadline >= ? AND j.deadline < ?", prev.isoformat(), today.isoformat())
        if shut:
            ui.say("keepers_closed", n=shut)
        fresh = sum(1 for r in rows if r["first_seen"] > prev.isoformat())  # dates only: a same-day recast adds none
        if fresh and not offline:
            ui.say("welcome_back", n=fresh, since=ui.since(prev, today))
    if not rows:
        return _empty(conn, cfg, prev, today)
    n = len(rows)
    ui.say("catch_intro" if n > HAND else "catch_intro_few", n=n)
    if not ui.CAPS["interactive"]:  # never wait on nobody
        ui.show(ui.table(rows))
        return ui.say("triage_list_only")
    t = {"kept": 0, "tossed": 0, "skipped": 0}
    did = {}       # card index -> "kept" / "tossed" / "skipped", so [b]ack can undo it
    asked = set()  # hand boundaries already offered, so going back over one doesn't ask twice
    warmed = False  # the first-keeper line was said this session; an undo must not bring it back
    i = 0
    try:
        while i < n:
            if i and i % HAND == 0 and i not in asked:
                asked.add(i)
                more = ui.ask("triage_hand", choices="yn", default="n", eof="n", done=i, total=n,
                              tally=ui.tally(**t), next=min(HAND, n - i))
                if more != "y":
                    return ui.say("triage_pause", tally=ui.tally(**t), left=n - sum(t.values()))
            key = _card(conn, cfg, rows[i], i + 1, n)
            if key == "q":
                break
            if key == "b":
                if i == 0:
                    ui.say("back_first")
                    continue
                i -= 1
                undone = did.pop(i, None)
                if undone:
                    t[undone] -= 1
                    if undone != "skipped":
                        conn.execute("DELETE FROM job_marks WHERE posting_id = ?", (rows[i]["posting_id"],))
                        conn.commit()
                ui.say("back_done")
                continue
            if key == "s":
                status = "skipped"
                ui.say("skipped")
            else:
                status = "kept" if key == "k" else "tossed"
                first = _mark(conn, rows[i]["posting_id"], status)
                ui.say(status)
                if first and key == "k" and not warmed:
                    ui.say("first_keep")
                    warmed = True
            t[status] += 1
            did[i] = status
            i += 1
        else:
            return ui.say("triage_end_offline" if offline else "triage_end", tally=ui.tally(**t))
    except KeyboardInterrupt:
        ui.say("triage_quit", tally=ui.tally(**t), left=n - sum(t.values()))
        return 130
    ui.say("triage_quit", tally=ui.tally(**t), left=n - sum(t.values()))


def _empty(conn, cfg, prev, today):
    # query.nearly needs a max_commute to relax and the session sets none, so it cannot help here:
    # "nothing in range at all" is the radius message instead. (The session has just cast, so "none posted"
    # is a checked statement here; search, keepers and chart check whether a cast ever happened.)
    if all(r["drive_minutes"] is None for r in query.search(conn, cfg, limit=None)):
        return ui.say("empty_none_near", radius=cfg.radius_miles)
    k = _count(conn, "SELECT COUNT(*) FROM job_marks m JOIN jobs j USING (posting_id) "
               "WHERE m.status = 'kept' AND (j.deadline IS NULL OR j.deadline >= ?)", today.isoformat())
    ui.say("empty_no_new" if k else "empty_no_new_no_keepers", since=ui.since(prev or today, today), k=k)


# ---- small commands ----

def school(args, conn, cfg):
    name = " ".join(args.name or []).strip()
    if not name:
        return ui.say("err_school_usage") or 1
    if not _schools_loaded(conn):
        return ui.say("school_list_missing") or 1
    found = find_schools(conn, cfg, name)
    if not found:
        return ui.say("school_not_found", name=name) or 1
    pick = _choose(found, name, example='school "Lincoln Elementary, Fresno"')
    if pick:
        show_school(conn, cfg, pick["cds_code"])


def keepers(args, conn, cfg):
    rows = query.search(conn, cfg, status="kept", limit=None)
    if not rows:
        n = _count(conn, "SELECT COUNT(*) FROM job_marks WHERE status = 'applied'")
        if n:
            return ui.say("keepers_all_applied", n=n)
        return ui.say("keepers_empty" if _count(conn, "SELECT COUNT(*) FROM jobs") else "no_listings_yet")
    today = date.today()
    # open first by deadline, then open-ended, then closed
    rows.sort(key=lambda r: (_closed(r["deadline"], today), not r["deadline"], r["deadline"] or ""))
    ui.say("keepers_header", n=len(rows))
    ui.show(ui.table(rows, today=today))
    still_open = [r for r in rows if not _closed(r["deadline"], today)]
    if still_open:  # the hint's example is a job you could still apply for
        ui.say("keepers_apply_hint", example=still_open[0]["posting_id"])


def _job(conn, value):
    """(posting_id, title) for a typed job number; says why and returns None when it can't."""
    pid = _posting(value)
    if pid is None:
        ui.say("err_posting_number")
        return None
    job = conn.execute("SELECT title FROM jobs WHERE posting_id = ?", (pid,)).fetchone()
    if not job:
        ui.say("err_unknown_posting", id=pid)
        return None
    return pid, job["title"] or ui.text("title_missing")


def applied(args, conn, cfg):
    found = _job(conn, args.posting)
    if not found:
        return 1
    pid, title = found
    if conn.execute("SELECT 1 FROM job_marks WHERE posting_id = ? AND status = 'applied'", (pid,)).fetchone():
        return ui.say("already_applied", title=title)
    first = _mark(conn, pid, "applied")
    ui.say("applied_done", title=title)
    if first:
        ui.say("first_applied")


def set_mark(conn, value, status):
    """`keep <number>` / `toss <number>`: any job in the database, so a slip can be undone from the command line."""
    found = _job(conn, value)
    if not found:
        return 1
    first = _mark(conn, found[0], status)
    ui.say("marked_" + status, title=found[1])
    if first and status == "kept":
        ui.say("first_keep")


def keep(args, conn, cfg):
    return set_mark(conn, args.posting, "kept")


def toss(args, conn, cfg):
    return set_mark(conn, args.posting, "tossed")


def logbook(args, conn, cfg):
    marks = conn.execute("SELECT m.status, m.marked_on, j.title, COALESCE(s.school_name, j.district_raw) AS place "
                         "FROM job_marks m JOIN jobs j USING (posting_id) LEFT JOIN schools s ON s.cds_code = j.cds_code "
                         "ORDER BY m.marked_on DESC").fetchall()
    ui.say("logbook_header")
    if not marks:
        return ui.say("logbook_empty")

    def sums(rows):  # a job applied for was kept first, though the mark now says applied; skips are not recorded
        return dict(looked=len(rows), kept=sum(r["status"] != "tossed" for r in rows),
                    applied=sum(r["status"] == "applied" for r in rows))
    week_ago = (date.today() - timedelta(days=6)).isoformat()
    ui.say("logbook_week", **sums([r for r in marks if r["marked_on"][:10] >= week_ago]))
    ui.say("logbook_total", start=SHORT(date.fromisoformat(marks[-1]["marked_on"][:10])), **sums(marks))
    for r in marks[:10]:
        line = ui.text("logbook_line", date=SHORT(date.fromisoformat(r["marked_on"][:10])),
                       status=ui.text("mark_" + r["status"]), title=ui.clean(r["title"]) or ui.text("title_missing"),
                       where=r["place"])
        # a long line wraps with its continuation indented, so each entry reads as one item
        ui.show("\n".join(textwrap.wrap(line, ui.CAPS["width"] - 1, subsequent_indent="  ", break_on_hyphens=False)))


def drove(args, conn, cfg):
    if not _has_home(conn, cfg):
        raise travel.NoHome("no home is set")
    if not args.school or args.minutes is None:
        return ui.say("err_drove_usage") or 1
    try:
        minutes = float(str(args.minutes).strip())
    except ValueError:
        minutes = 0
    if not 1 <= minutes <= 240:
        return ui.say("err_minutes") or 1
    if not _schools_loaded(conn):
        return ui.say("school_list_missing") or 1
    d = "pm" if args.pm else "am"
    found = find_schools(conn, cfg, args.school, d)
    example = f'drove "Lincoln Elementary, Fresno" {minutes:g}' + (" --pm" if args.pm else "")
    if not found:
        anywhere = find_schools(conn, cfg, args.school)
        if len(anywhere) == 1:  # it exists, but home has no drive time to it
            return ui.say("drove_out_of_range", school=anywhere[0]["school_name"], radius=int(cfg.radius_miles),
                          wider=min(100, int(cfg.radius_miles) * 2)) or 1
        if anywhere:
            return ui.say("school_ambiguous", example=example) or 1
        return ui.say("school_not_found", name=args.school) or 1
    pick = _choose(found, args.school, example=example)
    if pick is None:
        return 1
    _record_known(conn, cfg, pick["cds_code"], minutes, d)


def review(conn, cfg):
    """`match --review` on a terminal: pick the right name for each set-aside pair, or none, or skip."""
    import match
    pairs = match.review(conn)
    if not pairs:
        return ui.say("review_empty")
    ui.say("review_header", n=sum(r["jobs"] for r in pairs))
    for r in pairs:
        ui.show(cli.pair_line(r))
        cands = r["candidates"][:3]
        for n, (_code, name, score) in enumerate(cands, 1):
            ui.say("review_option", n=n, name=name, score=f"{score:.2f}")
        key = "review_pick"
        while True:
            answer = (ui.ask(key, n=len(cands)) or "").strip().lower()
            if not answer:
                code = False  # Enter: skip, it stays set aside
                break
            if answer in ("n", "none"):
                code = None
                break
            if answer.isdigit() and 1 <= int(answer) <= len(cands):
                code = cands[int(answer) - 1][0]
                break
            key = "review_again"  # an answer I don't recognise asks again; it never skips silently
        if code is False:
            continue
        # 14 characters is a school (a site, or a charter standing as its own district); 7 is a district
        kw = {"cds_code": code} if code and len(code) == 14 else {"district_code": code}
        ui.say("review_saved", n=match.resolve(conn, r["district_raw"], r["location_raw"], **kw))
