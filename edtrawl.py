"""Command-line entry point. Wires the modules together; every word goes through ui.py (COPY keys)."""
import argparse
import re
import socket
import sys
import traceback
import urllib.error
from datetime import datetime
from pathlib import Path

import config as config_mod
import db
import edjoin
import ingest as ingest_mod
import query
import travel
import ui

DATA = Path(ingest_mod.__file__).with_name("data")
LATLNG = re.compile(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*")


def prog(key):
    """An on_progress that shows COPY[key] whatever label the module reports."""
    return lambda done, total, _label: ui.progress(done, total, key)


# ---- commands: each is cmd(args, conn, cfg) -> exit code (None = 0) ----

def cmd_home(args, conn, cfg):
    target = (args.target or "").strip()
    zip_code = args.zip or (target if re.fullmatch(r"\d{5}", target) else None)
    if args.zip and not re.fullmatch(r"\d{5}", args.zip):
        return ui.say("err_home_unreadable") or 1
    if zip_code:
        lat, lng = travel.zip_centroid(conn, zip_code)
    elif m := LATLNG.fullmatch(target):
        lat, lng = float(m[1]), float(m[2])
    elif len(target) >= 5 and re.search(r"\d", target):
        # Consent first. Not on a terminal nobody can answer, and typing the address on the command line is the ask.
        if ui.ask("geocode_notice", choices="yn", default="y") != "y":
            return ui.say("home_declined") or 1
        found = travel.geocode(target)  # the one use of the address; it is never stored, logged or echoed
        if found is None:
            return ui.say("err_address_not_found") or 1
        lat, lng = found
    else:
        return ui.say("err_home_unreadable") or 1
    travel.set_home(conn, cfg, lat, lng, args.config)
    ui.say("home_saved")
    if zip_code:
        ui.say("home_zip_note")


def cmd_ingest(args, conn, cfg):
    if args.file:
        if not Path(args.file).is_file():
            return ui.say("err_file_not_found", path=args.file) or 1
        jobs = [(args.file, None)]
    else:
        jobs = []
        for year in args.year or ["2025-26"]:
            path = DATA / f"schools_{year}.csv"
            if not path.exists():  # download only what is missing
                try:
                    path = ingest_mod.download(year)
                except (RuntimeError, OSError):  # not ready, or offline: the same advice
                    return ui.say("err_schools_download", year=year) or 1
            jobs.append((path, year))
    for path, year in jobs:
        r = ingest_mod.ingest(conn, path, year, on_progress=prog("progress_schools"))
        ui.say("schools_loaded", n=r["schools"], year=r["academic_year"])


def cmd_commute(args, conn, cfg):
    r = travel.update_commutes(conn, cfg, on_progress=prog("progress_drives"))
    if not r["in_range"]:
        return ui.say("reveal_none", radius=cfg.radius_miles, wider=cfg.radius_miles * 2) or 1
    ui.say("drives_ready", n=r["in_range"])
    if cfg.routing == "osrm":
        ui.say("attribution_osm")


def cmd_fetch(args, conn, cfg):
    import match  # imported late: written by another agent, and only fetch/match need it
    if not cfg.home_key:
        raise travel.NoHome("no home is set")
    if args.from_file:
        if not Path(args.from_file).is_file():
            return ui.say("err_file_not_found", path=args.from_file) or 1
        new, seen = edjoin.load_file(conn, args.from_file)
    else:
        ids = edjoin.county_ids_in_range(conn, cfg)
        if not ids:
            return ui.say("err_no_commutes") or 1
        ui.say("edjoin_notice")
        rows = edjoin.fetch_listings(ids, args.days, args.limit, on_progress=prog("progress_fetch"))
        new, seen = edjoin.save_listings(conn, rows)
    ui.say("fetch_done", new=new, seen=seen)
    result = match.match_jobs(conn, cfg, on_progress=prog("progress_match"))
    if not args.from_file:  # a saved file never triggers posting-page requests
        wanted = match.needs_detail(conn, cfg)
        if wanted and edjoin.fetch_sites(conn, wanted, on_progress=prog("progress_details")):
            result = match.match_jobs(conn, cfg, on_progress=prog("progress_match"))
    _match_notes(result, cfg)


def _match_notes(result, cfg):
    if result.get("llm_failed"):
        ui.say("err_llm_unreachable", url=cfg.llm_base_url)
    if result.get("unsure"):
        ui.say("match_set_aside", n=result["unsure"])


def cmd_match(args, conn, cfg):
    import match
    if args.review:
        pairs = match.review(conn)
        ui.say("review_header", n=sum(r["jobs"] for r in pairs)) if pairs else ui.say("review_empty")
        for r in pairs:
            place = " · ".join(x for x in (ui.clean(r["district_raw"]), ui.clean(r["location_raw"])) if x)
            ui.show(f"{place}  ({ui.count(r['jobs'], 'job')})")
            for code, name, score in r["candidates"][:3]:
                ui.show(f"    {ui.clean(code)}  {ui.clean(name)}  {score:.2f}")
        return
    _match_notes(match.match_jobs(conn, cfg, on_progress=prog("progress_match")), cfg)


def cmd_search(args, conn, cfg):
    flag = {"yes": True, "no": False, None: None}
    filters = dict(max_commute=args.max_commute, posted_within=args.posted_within, level=args.level,
                   charter=flag[args.charter], min_enrollment=args.min_enrollment, title_i=flag[args.title_i],
                   status=args.status, new_only=args.new)
    if args.max_commute is not None and args.max_commute.is_integer():
        filters["max_commute"] = int(args.max_commute)  # so the message says 15, not 15.0
    rows = query.search(conn, cfg, limit=args.limit, **filters)
    if rows:
        ui.say("search_header", n=len(rows))
        return ui.show(ui.table(rows))
    near = query.nearly(conn, cfg, **filters)
    if args.max_commute is not None:
        ui.say("empty_in_range", max=filters["max_commute"])
    if near:
        ui.say("empty_nearly", minutes=near[0], n=near[1])
    elif any(v not in (None, False) for k, v in filters.items() if k != "max_commute"):
        ui.say("empty_filtered")  # some other filter emptied it: "no jobs near you" would be untrue
    elif args.max_commute is None:
        ui.say("empty_none_near", radius=cfg.radius_miles)


COMMANDS = {"home": cmd_home, "ingest": cmd_ingest, "commute": cmd_commute, "fetch": cmd_fetch,
            "match": cmd_match, "search": cmd_search}  # the next wave adds setup, go, school, keepers, ... here


# ---- parser ----

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS on the copy every subparser inherits, so a flag given before the command isn't overwritten by a default
    top =argparse.ArgumentParser(prog="edtrawl.py", description="Find teaching jobs within commute range of home.")
    for p, sup in ((top, False), (common, True)):
        dflt = (lambda v: argparse.SUPPRESS) if sup else (lambda v: v)
        p.add_argument("--db", default=dflt("edtrawl.db"), help="database file (default edtrawl.db)")
        p.add_argument("--config", default=dflt("config.toml"), help="config file (default config.toml)")
        p.add_argument("--plain", action="store_true", default=dflt(False), help="no colour or emoji")
        p.add_argument("--no-emoji", action="store_true", default=dflt(False), help="no emoji")
    sub = top.add_subparsers(dest="command")
    add = lambda name, **kw: sub.add_parser(name, parents=[common], **kw)
    p = add("home", help="set home from an address, ZIP code or lat,lng")
    p.add_argument("target", nargs="?", help='"street address" or 36.74,-119.79 or a 5-digit ZIP')
    p.add_argument("--zip", help="ZIP code, placed at the middle of its schools")
    p = add("ingest", help="load California school data")
    p.add_argument("--year", action="append", choices=sorted(ingest_mod.URLS), help="academic year, repeatable")
    p.add_argument("--file", help="load this CDE csv instead")
    add("commute", help="work out drive times to schools near home")
    p = add("fetch", help="fetch and match job listings")
    p.add_argument("--days", type=int, choices=(1, 7, 31), default=31)
    p.add_argument("--limit", type=int, help="stop after this many listings")
    p.add_argument("--from-file", help="load a saved listing response instead of fetching")
    p = add("match", help="match listings to schools again")
    p.add_argument("--review", action="store_true", help="list the listings set aside")
    p = add("search", help="list jobs, nearest first")
    p.add_argument("--max-commute", type=float, help="minutes, the slower direction")
    p.add_argument("--posted-within", type=int, help="days")
    p.add_argument("--level", help="elementary, middle or high")
    p.add_argument("--charter", choices=("yes", "no"))
    p.add_argument("--min-enrollment", type=int)
    p.add_argument("--title-i", choices=("yes", "no"))
    p.add_argument("--status", choices=("kept", "tossed", "applied"))
    p.add_argument("--new", action="store_true", help="only jobs you haven't marked")
    p.add_argument("--limit", type=int, default=50)
    return top


# ---- errors: the one place exceptions become messages ----

def zip_of(args):
    """The ZIP the user typed, never anything else (a target could be an address)."""
    t = getattr(args, "zip", None) or getattr(args, "target", None) or ""
    return t if re.fullmatch(r"\d{5}", t) else ""


def _speak(e, args):
    """The COPY key (and values) for an exception, or None when it is not one we planned for."""
    if isinstance(e, travel.GeocoderUnavailable):
        return "err_geocoder_unreachable", {}
    if isinstance(e, travel.RoutingUnavailable):
        return "err_routing_unreachable", {}
    if isinstance(e, travel.OutsideCalifornia):
        return "err_outside_california", {}
    if isinstance(e, travel.UnknownZip):
        return "err_unknown_zip", {"zip": zip_of(args)}
    if isinstance(e, travel.NoHome):
        return "err_no_home", {}
    if isinstance(e, edjoin.EdjoinRefused):
        return ("err_edjoin_busy" if e.status == 429 else "err_edjoin_refused"), {}
    if isinstance(e, edjoin.EdjoinError):  # server error or a reply we can't read
        return "err_edjoin_down", {}
    if isinstance(e, (urllib.error.URLError, ConnectionError, TimeoutError, socket.gaierror)):
        # not every OSError: a missing --file is the user's typo, not the network
        return "err_offline", {"service": {"ingest": "data.ca.gov", "fetch": "edjoin.org"}.get(args.command, "the internet")}
    return None


def _log_unexpected(e, db_path):
    """Append the exception type and the frames (file, line, function) to edtrawl-error.log next to the database.
    Never str(e), never frame text or locals: argument values (an address) could be in them."""
    path = Path(db_path).resolve().with_name("edtrawl-error.log")
    frames = [f"  {Path(f.filename).name}:{f.lineno} in {f.name}" for f in traceback.extract_tb(e.__traceback__)]
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {type(e).__name__}\n" + "\n".join(frames) + "\n")
    return path


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    ui.configure(plain=args.plain, no_emoji=args.no_emoji)
    if not args.command:
        parser.print_help()  # the guided flow replaces this
        return 0
    conn = None
    try:
        cfg = config_mod.load(args.config)
        conn = db.connect(args.db)
        db.init_db(conn)
        return COMMANDS[args.command](args, conn, cfg) or 0
    except KeyboardInterrupt:
        ui.say("stopped")
        return 130
    except Exception as e:
        spoken = _speak(e, args)
        if spoken:
            ui.say(spoken[0], **spoken[1])
        else:
            ui.say("err_unexpected", path=str(_log_unexpected(e, args.db)))
        return 1
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
