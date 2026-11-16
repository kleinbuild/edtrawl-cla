"""Developer-only: fit travel.COEFFS against OSRM road times and report how good the offline formula is.

  python3 calibrate.py --db PATH     fetch (resumable) into data/calibration.csv, then report. PATH = a database built with
                                     db.init_db + ingest.ingest; never the user's edtrawl.db.
  python3 calibrate.py --report      reprint the report from data/calibration.csv; no network.
Stand-in homes are schools (public coordinates); direction is home -> school only (free-flow OSRM is nearly symmetric)."""
import argparse
import collections
import csv
import random
import statistics
import sys
from pathlib import Path

import config
import db
import travel

CSV = Path(__file__).with_name("data") / "calibration.csv"
FIELDS = ["home_cds", "school_cds", "home_locale", "school_locale", "home_county", "school_county",
          "home_name", "school_name", "straight_miles", "osrm_minutes"]
SEED, HOMES, PER_HOME, MAX_REQUESTS, MIN_MILES, RADIUS = 20261116, 60, 48, 150, 0.3, 20
GROUPS = {"1": "City", "2": "Suburban", "3": "Town", "4": "Rural"}
OLD = {"1": (4.0, 2.0), "2": (4.0, 1.8), "3": (3.0, 1.6), "4": (3.0, 1.4)}  # the guesses this script replaced


def candidates(conn):
    rows = conn.execute(
        f"SELECT cds_code, school_name, COALESCE(geo_county_name, county_name) AS county, substr(locale, 1, 1) AS g, "
        f"COALESCE(lat_override, lat) AS lat, COALESCE(lng_override, lng) AS lng FROM schools "
        f"WHERE COALESCE(lat_override, lat) IS NOT NULL AND COALESCE(lng_override, lng) IS NOT NULL AND {travel.OPEN} "
        f"AND substr(locale, 1, 1) IN ('1','2','3','4') ORDER BY cds_code")
    return [dict(r) for r in rows]


def pick_homes(schools, rng):
    """HOMES/4 per locale group, round-robin over counties in random order so no county dominates."""
    homes = []
    for g in GROUPS:
        by_county = collections.defaultdict(list)
        for s in schools:
            if s["g"] == g:
                by_county[s["county"]].append(s)
        counties = sorted(by_county)
        rng.shuffle(counties)
        for c in counties:
            rng.shuffle(by_county[c])
        chosen = []
        while len(chosen) < HOMES // 4 and any(by_county.values()):
            for c in counties:
                while by_county[c]:
                    h = by_county[c].pop()
                    h["lat"], h["lng"] = round(h["lat"], 3), round(h["lng"], 3)  # as travel.set_home does
                    near = [{**s, "m": m} for s in schools if s is not h
                            and MIN_MILES <= (m := travel.haversine_miles(h["lat"], h["lng"], s["lat"], s["lng"])) <= RADIUS]
                    if len(near) >= 25:  # a home with too few neighbours teaches little
                        chosen.append((h, near))
                        break
                if len(chosen) >= HOMES // 4:
                    break
        homes += chosen
    return homes


def spread(near, rng):
    """PER_HOME schools spread evenly over distance: equal quota per 2-mile band, shortfalls filled at random."""
    bands = collections.defaultdict(list)
    for s in near:
        bands[int(s["m"] // 2)].append(s)
    quota, out = PER_HOME // 10, []
    for b in bands.values():
        rng.shuffle(b)
        out += b[:quota]
    rest = [s for s in near if s not in out]
    rng.shuffle(rest)
    return out + rest[:PER_HOME - len(out)]


def fetch(conn, cfg):
    rng = random.Random(SEED)
    homes = pick_homes(candidates(conn), rng)
    plan = [(h, spread(near, rng)) for h, near in homes]  # drawn for every home even when done, so reruns agree
    CSV.parent.mkdir(exist_ok=True)
    done = {r["home_cds"] for r in csv.DictReader(CSV.open(encoding="utf-8"))} if CSV.exists() else set()
    new = not CSV.exists()
    requests = 0
    with CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        for h, schools in plan:
            if h["cds_code"] in done:
                continue
            if requests >= MAX_REQUESTS:
                break
            requests += 1
            coords = [(h["lat"], h["lng"])] + [(s["lat"], s["lng"]) for s in schools]
            try:  # one failure stops the run: no retry, no other server
                row = travel._osrm_table(cfg.osrm_url, coords, [0], list(range(1, len(coords))))[0]
            except travel.RoutingUnavailable as e:
                print(f"stopped after {requests} requests: {e}", file=sys.stderr)
                break
            for s, secs in zip(schools, row):
                w.writerow({"home_cds": h["cds_code"], "school_cds": s["cds_code"], "home_locale": h["g"],
                            "school_locale": s["g"], "home_county": h["county"], "school_county": s["county"],
                            "home_name": h["school_name"], "school_name": s["school_name"],
                            "straight_miles": round(s["m"], 3), "osrm_minutes": "" if secs is None else round(secs / 60, 2)})
            f.flush()
    print(f"OSRM requests this run: {requests}")


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(p * (len(xs) - 1)))]


def stats(pairs, coef):
    """(n, median min, p90 min, median %, p90 %) of |model - osrm| using coef[group] = (a, b)."""
    e = [abs(coef[p["g"]][0] + coef[p["g"]][1] * p["mi"] - p["min"]) for p in pairs]
    r = [x / p["min"] for x, p in zip(e, pairs)]
    return len(e), statistics.median(e), pct(e, 0.9), 100 * statistics.median(r), 100 * pct(r, 0.9)


def fit(pairs):
    out = {}
    for g in GROUPS:
        if len(ps := [p for p in pairs if p["g"] == g]) > 2:
            b, a = statistics.linear_regression([p["mi"] for p in ps], [p["min"] for p in ps])  # slope first
            out[g] = (a, b)
    return out


def report():
    rows = [r for r in csv.DictReader(CSV.open(encoding="utf-8")) if r["osrm_minutes"]]
    allp = [{**r, "mi": float(r["straight_miles"]), "min": float(r["osrm_minutes"]), "g": r["school_locale"]}
            for r in rows if float(r["osrm_minutes"]) > 0]
    homes = sorted({p["home_cds"] for p in allp})
    random.Random(SEED).shuffle(homes)
    test_h = set(homes[:len(homes) // 5])  # split by home: held-out pairs come from homes the fit never saw
    train = [p for p in allp if p["home_cds"] not in test_h]
    test = [p for p in allp if p["home_cds"] in test_h]
    new = fit(train)
    byhome = fit([{**p, "g": p["home_locale"]} for p in train])
    print(f"{len(allp)} pairs from {len(homes)} homes; fit on {len(train)} pairs ({len(homes) - len(test_h)} homes), "
          f"held out {len(test)} pairs ({len(test_h)} homes). Home to school, free-flow, no rush-hour factor.\n")
    print("Pairs per destination group, all / train / held-out:")
    for g, name in GROUPS.items():
        print(f"  {name:9s} {sum(p['g'] == g for p in allp):5d} {sum(p['g'] == g for p in train):5d} {sum(p['g'] == g for p in test):5d}")
    print("\nCoefficients (a + b x miles), old guess -> fit on train:")
    for g, name in GROUPS.items():
        print(f"  {name:9s} {OLD[g][0]:.1f} + {OLD[g][1]:.2f}  ->  {new[g][0]:.2f} + {new[g][1]:.3f}")
    print("\nHeld-out error |model - OSRM|: n, median min, p90 min, median %, p90 %")
    for label, coef in (("before (guesses)", OLD), ("after (fitted)", new)):
        print(f" {label}")
        for g, name in GROUPS.items():
            print("  %-9s n=%4d  %5.1f  %5.1f  %5.0f%%  %5.0f%%" % ((name,) + stats([p for p in test if p["g"] == g], coef)))
    print("  held-out, all groups, after: n=%d  %.1f  %.1f  %.0f%%  %.0f%%" % stats(test, new))
    print("\nKeyed on the HOME's group instead (fit on train, same held-out pairs):")
    for g, name in GROUPS.items():
        ps = [{**p, "g": p["home_locale"]} for p in test if p["home_locale"] == g]
        print("  %-9s n=%4d  %5.1f  %5.1f  %5.0f%%  %5.0f%%" % ((name,) + stats(ps, byhome)))
    print("\nResidual shape, mean (model - OSRM) minutes by straight-line miles band, fitted model, ALL pairs:")
    bands = [(0, 2), (2, 5), (5, 10), (10, 15), (15, 20.1)]
    print("  " + "".join(f"{lo}-{int(hi)}mi".rjust(10) for lo, hi in bands))
    for g, name in GROUPS.items():
        cells = []
        for lo, hi in bands:
            ps = [p for p in allp if p["g"] == g and lo <= p["mi"] < hi]
            cells.append(("%+.1f(%d)" % (statistics.mean(new[g][0] + new[g][1] * p["mi"] - p["min"] for p in ps), len(ps))
                          if ps else "-").rjust(10))
        print(f"  {name:9s}" + "".join(cells))
    print("\nOSRM minutes per straight mile (median) by band, all pairs:")
    for g, name in GROUPS.items():
        print(f"  {name:9s}" + "".join(("%.2f" % statistics.median(p["min"] / p["mi"] for p in ps) if (ps := [
            p for p in allp if p["g"] == g and lo <= p["mi"] < hi]) else "-").rjust(10) for lo, hi in bands))
    print("\nThree worst held-out pairs (fitted model):")
    worst = sorted(test, key=lambda p: -abs(new[p["g"]][0] + new[p["g"]][1] * p["mi"] - p["min"]))[:3]
    for p in worst:
        m = new[p["g"]][0] + new[p["g"]][1] * p["mi"]
        print(f"  {p['home_name']} ({p['home_county']}) -> {p['school_name']} ({p['school_county']}): "
              f"{p['mi']:.1f} straight miles, OSRM {p['min']:.1f} min, model {m:.1f}")
    print("\nCOEFFS = {" + ", ".join(f'"{g}": ({a:.2f}, {b:.3f})' for g, (a, b) in new.items()) + "}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true", help="reprint the report from data/calibration.csv; no network")
    ap.add_argument("--db", help="database built with db.init_db + ingest.ingest, used only to choose the sample")
    a = ap.parse_args()
    if not a.report:
        if not a.db:
            ap.error("give --db PATH to fetch, or --report")
        fetch(db.connect(a.db), config.Config())
    report()
