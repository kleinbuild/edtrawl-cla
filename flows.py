"""Guided flows: setup, the daily session, the triage deck, and the small commands around them.

Every sentence is a ui.COPY key. Each command is cmd(args, conn, cfg) -> exit code (None = 0), like edtrawl.py's.
"""
import re
import statistics
import webbrowser
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlparse

import config as config_mod
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
    cond, args = ("s.cds_code = ?", [text]) if re.fullmatch(r"\d{14}", text) else (
        "instr(lower(s.school_name), lower(?)) > 0", [text])
    if direction:
        cond += f" AND c.{direction}_minutes IS NOT NULL"
    rows = conn.execute(
        f"SELECT s.cds_code, s.school_name, s.city, c.cds_code IS NOT NULL AS near FROM schools s "
        f"LEFT JOIN commutes c ON c.cds_code = s.cds_code AND c.home_key = ? WHERE {cond} "
        f"ORDER BY near DESC, s.school_name LIMIT 10", [cfg.home_key] + args).fetchall()
    return [dict(r) for r in rows]


def _choose(found, name):
    """The one school, or None when the user skips (or nobody can answer)."""
    if len(found) == 1:
        return found[0]
    ui.say("known_drive_which", name=name)
    shown = found[:9]
    for n, s in enumerate(shown, 1):
        ui.say("known_drive_option", n=n, school=s["school_name"], city=s["city"])
    if len(found) > 9:
        ui.say("school_many", n=9)
    answer = ui.ask("pick_prompt")
    return shown[int(answer) - 1] if answer and answer.isdigit() and 1 <= int(answer) <= len(shown) else None


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
    """Record a known drive and show one before-and-after line (typical = median over schools in range)."""
    before = _typical(conn, cfg, d)
    factor = travel.record_drive(conn, cfg, code, minutes, d)[0 if d == "am" else 1]
    after = _typical(conn, cfg, d)
    if round(before) == round(after):
        return ui.say("drove_unchanged")
    ui.say("drove_adjusted_" + d, before=round(before), after=round(after))
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
    if not _count(conn, "SELECT COUNT(*) FROM commutes WHERE home_key = ?", cfg.home_key):
        _step(2, "step_schools")
        if not _reveal(conn, cfg, args):
            return 1
        _step(3, "step_routing")
        _drive_times(conn, cfg, args)
    if not _count(conn, "SELECT COUNT(*) FROM known_drives WHERE home_key = ?", cfg.home_key):
        _step(4, "step_known_drive")
        _known_drive(conn, cfg)
    ui.say("setup_done")
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
        offer = min(100, miles * 2)
        ui.say("reveal_none", radius=miles, wider=offer)
    info = {r[0]: r for r in conn.execute("SELECT cds_code, district_code, school_name FROM schools")}
    ui.say("reveal", radius=cfg.radius_miles, schools=len(near),
           districts=len({info[s["cds_code"]][1] for s in near}))
    ui.say("reveal_nearest", school=info[near[0]["cds_code"]][2], miles=round(near[0]["miles"], 1))
    return True


def _drive_times(conn, cfg, args):
    server = urlparse(cfg.osrm_url).netloc
    while True:
        cfg.routing = "osrm" if ui.ask("routing_ask", choices="or", default="o", server=server) == "r" else "estimate"
        ui.say("routing_saved_roads" if cfg.routing == "osrm" else "routing_saved_offline")
        try:
            travel.update_commutes(conn, cfg, on_progress=cli.prog("progress_drives"))
            break
        except travel.RoutingUnavailable:  # batches already done are kept; offer the choice again
            ui.say("err_routing_unreachable_setup")
    config_mod.set("routing", cfg.routing, args.config)
    ui.say("drives_ready", n=_count(conn, "SELECT COUNT(*) FROM commutes WHERE home_key = ?", cfg.home_key))
    if cfg.routing == "osrm":
        ui.say("attribution_osm")


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


# ---- the daily session ----

def go(args, conn, cfg):
    if not _has_home(conn, cfg):
        return setup(args, conn, cfg)
    try:
        r = travel.update_commutes(conn, cfg, on_progress=cli.prog("progress_drives"))  # cheap when fresh
    except travel.RoutingUnavailable:
        ui.say("err_routing_unreachable")  # saved drive times still work
        r = {"in_range": 1}
    if not r["in_range"]:
        return ui.say("reveal_none", radius=cfg.radius_miles, wider=int(cfg.radius_miles * 2)) or 1
    return session(conn, cfg)


def session(conn, cfg):
    last = conn.execute("SELECT MAX(last_seen) FROM jobs").fetchone()[0]
    prev = date.fromisoformat(last) if last else None
    # 31 days on the first cast or after more than a week away; otherwise 7 (edjoin accepts 1, 7 or 31)
    days = 31 if prev is None or (date.today() - prev).days > 7 else 7
    code = cli.cmd_fetch(SimpleNamespace(days=days, limit=None, from_file=None), conn, cfg)
    return code or deck(conn, cfg, prev)


def _card(conn, cfg, row, i, n):
    """Show one card and return k, t, s or q. `open` and `more` come back to the same card."""
    ui.show(ui.job_card(row, i, n))
    district = not row["cds_code"]  # no school to tell about
    while True:
        key = ui.ask("triage_keys_district" if district else "triage_keys",
                     choices="ktsoq" if district else "ktsomq", default="s")
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


def deck(conn, cfg, prev):
    today = date.today()
    # New = no mark, a drive time (school in range, or a district with schools in range), not already closed.
    rows = [r for r in query.search(conn, cfg, new_only=True, limit=None)
            if r["drive_minutes"] is not None and not _closed(r["deadline"], today)]
    if prev:
        shut = _count(conn, "SELECT COUNT(*) FROM job_marks m JOIN jobs j USING (posting_id) WHERE m.status = 'kept' "
                      "AND j.deadline >= ? AND j.deadline < ?", prev.isoformat(), today.isoformat())
        if shut:
            ui.say("keepers_closed", n=shut)
        fresh = sum(1 for r in rows if r["first_seen"] > prev.isoformat())  # dates only: a same-day recast adds none
        if fresh:
            ui.say("welcome_back", n=fresh, since=ui.since(prev, today))
    if not rows:
        return _empty(conn, cfg, prev, today)
    ui.say("catch_intro", n=len(rows))
    if not ui.CAPS["interactive"]:  # never wait on nobody
        ui.show(ui.table(rows))
        return ui.say("triage_list_only")
    t = {"kept": 0, "tossed": 0, "skipped": 0}
    try:
        for i, row in enumerate(rows, 1):
            key = _card(conn, cfg, row, i, len(rows))
            if key == "q":
                break
            if key == "s":
                t["skipped"] += 1
                ui.say("skipped")
                continue
            status = "kept" if key == "k" else "tossed"
            first = _mark(conn, row["posting_id"], status)
            t[status] += 1
            ui.say(status)
            if first and key == "k":
                ui.say("first_keep")
        else:
            return ui.say("triage_end", tally=ui.tally(**t))
    except KeyboardInterrupt:
        ui.say("triage_quit", tally=ui.tally(**t), left=len(rows) - sum(t.values()))
        return 130
    ui.say("triage_quit", tally=ui.tally(**t), left=len(rows) - sum(t.values()))


def _empty(conn, cfg, prev, today):
    # query.nearly needs a max_commute to relax and the session sets none, so it cannot help here:
    # "nothing in range at all" is the radius message instead.
    if all(r["drive_minutes"] is None for r in query.search(conn, cfg, limit=None)):
        return ui.say("empty_none_near", radius=cfg.radius_miles)
    k = _count(conn, "SELECT COUNT(*) FROM job_marks m JOIN jobs j USING (posting_id) "
               "WHERE m.status = 'kept' AND (j.deadline IS NULL OR j.deadline >= ?)", today.isoformat())
    ui.say("empty_no_new" if k else "empty_no_new_no_keepers", since=ui.since(prev or today, today), k=k)


# ---- small commands ----

def school(args, conn, cfg):
    name = " ".join(args.name)
    found = find_schools(conn, cfg, name)
    if not found:
        return ui.say("school_not_found", name=name) or 1
    pick = _choose(found, name)
    if pick:
        show_school(conn, cfg, pick["cds_code"])


def keepers(args, conn, cfg):
    rows = query.search(conn, cfg, status="kept", limit=None)
    if not rows:
        return ui.say("keepers_empty")
    today = date.today()
    # open first by deadline, then open-ended, then closed
    rows.sort(key=lambda r: (_closed(r["deadline"], today), not r["deadline"], r["deadline"] or ""))
    ui.say("keepers_header", n=len(rows))
    ui.show(ui.table(rows, today=today))
    ui.say("keepers_apply_hint", example=rows[0]["posting_id"])


def applied(args, conn, cfg):
    job = conn.execute("SELECT title FROM jobs WHERE posting_id = ?", (args.posting,)).fetchone()
    if not job:
        return ui.say("err_unknown_posting", id=args.posting) or 1
    first = _mark(conn, args.posting, "applied")
    ui.say("applied_done", title=job["title"])
    if first:
        ui.say("first_applied")


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
        ui.say("logbook_line", date=SHORT(date.fromisoformat(r["marked_on"][:10])),
               status=ui.text("mark_" + r["status"]), title=r["title"], where=r["place"])


def drove(args, conn, cfg):
    if not _has_home(conn, cfg):
        raise travel.NoHome("no home is set")
    if not 1 <= args.minutes <= 240:
        return ui.say("err_minutes") or 1
    d = "pm" if args.pm else "am"
    found = find_schools(conn, cfg, args.school, d)
    if not found:
        return ui.say("school_not_found", name=args.school) or 1
    pick = _choose(found, args.school)
    if pick is None:
        return 1
    _record_known(conn, cfg, pick["cds_code"], args.minutes, d)


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
        answer = ui.ask("review_pick")
        if answer and answer.lower().startswith("n"):
            code = None
        elif answer and answer.isdigit() and 1 <= int(answer) <= len(cands):
            code = cands[int(answer) - 1][0]
        else:
            continue  # skip: it stays set aside
        # 14 characters is a school (a site, or a charter standing as its own district); 7 is a district
        kw = {"cds_code": code} if code and len(code) == 14 else {"district_code": code}
        ui.say("review_saved", n=match.resolve(conn, r["district_raw"], r["location_raw"], **kw))
