"""Home, radius filter, drive-time estimates and the commute cache. Does not print; raises TravelError subclasses."""
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from datetime import date

import config as config_mod

USER_AGENT = "EdTrawl/0.1"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
CA_LAT, CA_LNG = (32.5, 42.0), (-124.5, -114.1)  # California bounding box, PLAN.md section 3 "Home"
# Coordinates per OSRM table request = 1 home + this many schools. osrm-routed's documented default
# --max-table-size is 100; the public server accepted 201 coordinates in one test (2026-11-16). 50 is PLAN.md's choice.
BATCH = 50
OSRM_PAUSE = 1.0  # public-server policy: at most one request per second

# minutes = a + b * straight_miles, by first digit of the CDE Locale (1 City, 2 Suburban, 3 Town, 4 Rural).
# Fitted 2026-11-16 by calibrate.py on 2195 home-to-school pairs from 48 stand-in homes (60 homes, 2734 pairs in all,
# schools within 20 straight miles); free-flow, before the rush factor. Median error on the 539 held-out pairs
# (12 unseen homes): 2.4 min, 13%; 90th percentile 8.8 min, 37%. Per group, see `python3 calibrate.py --report`.
# fitted against OpenStreetMap road times via OSRM; © OpenStreetMap contributors
COEFFS = {"1": (4.08, 1.653), "2": (4.50, 1.782), "3": (1.60, 2.061), "4": (4.81, 1.899)}

# FHWA Urban Congestion Report, July-September 2026, Travel Time Index (peak-period / free-flow), by metro area,
# mapped to counties as in PLAN.md section 3. Counties not listed use TTI_DEFAULT, which is a GUESS.
TTI_DEFAULT = 1.10
TTI = {}
for _tti, _counties in (
    (1.59, "Los Angeles,Orange"), (1.45, "Santa Clara,San Benito"),
    (1.37, "San Francisco,Alameda,Contra Costa,San Mateo,Marin"), (1.27, "Riverside,San Bernardino"),
    (1.25, "San Diego"), (1.17, "Sacramento,Placer,El Dorado,Yolo"), (1.07, "Fresno"),
):
    TTI.update({c: _tti for c in _counties.split(",")})

RANK = {"estimate": 0, "osrm": 1}  # decision 6: a cached row must be at least as good as the configured provider
OPEN = "COALESCE(status, '') NOT IN ('Closed', 'Merged')"  # merged schools no longer exist either


class TravelError(Exception):
    """Base class; messages never contain an address."""


class GeocoderUnavailable(TravelError): pass
class RoutingUnavailable(TravelError): pass   # OSRM unreachable or answered badly; the run stops, nothing falls back
class OutsideCalifornia(TravelError): pass
class UnknownZip(TravelError): pass
class NoHome(TravelError): pass               # cfg.home_key is unset or not in `homes`
class NoCommute(TravelError): pass            # record_drive for a school with no modelled time for this home


def _http_json(url):  # the one network function; tests replace it
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def geocode(address):
    """(lat, lng) for a street address, or None if the Census geocoder finds no match."""
    q = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "format": "json"})
    try:
        data = _http_json(f"{CENSUS_URL}?{q}")
    except Exception:  # deliberately generic and chained to nothing: the URL contains the address
        raise GeocoderUnavailable("the Census geocoder did not answer") from None
    matches = (data.get("result") or {}).get("addressMatches") or []
    if not matches:
        return None
    c = matches[0]["coordinates"]
    return c["y"], c["x"]  # x is longitude, y is latitude


def zip_centroid(conn, zip_code):
    row = conn.execute(
        f"SELECT AVG(COALESCE(lat_override, lat)), AVG(COALESCE(lng_override, lng)) FROM schools "
        f"WHERE substr(zip, 1, 5) = ? AND COALESCE(lat_override, lat) IS NOT NULL AND {OPEN}", (str(zip_code)[:5],)).fetchone()
    if row[0] is None:
        raise UnknownZip("no schools with coordinates in that ZIP code")
    return row[0], row[1]


def set_home(conn, cfg, lat, lng, path="config.toml"):
    """Round to 3 dp (~100 m), check California, upsert `homes`, make it the active home. Returns home_key."""
    lat, lng = round(lat, 3), round(lng, 3)
    if not (CA_LAT[0] <= lat <= CA_LAT[1] and CA_LNG[0] <= lng <= CA_LNG[1]):
        raise OutsideCalifornia("those coordinates are outside California")
    key = f"{lat},{lng}"
    conn.execute("INSERT INTO homes (home_key, created_on) VALUES (?, ?) ON CONFLICT(home_key) DO NOTHING",
                 (key, date.today().isoformat()))
    conn.commit()
    config_mod.set("home_key", key, path)
    cfg.home_key = key
    return key


def haversine_miles(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))  # 3958.8 = mean Earth radius in miles


def _home(conn, cfg):
    if not cfg.home_key or not conn.execute("SELECT 1 FROM homes WHERE home_key = ?", (cfg.home_key,)).fetchone():
        raise NoHome("no home is set")
    return tuple(float(x) for x in cfg.home_key.split(","))


def schools_in_radius(conn, cfg):
    """Open schools with coordinates within cfg.radius_miles, nearest first: dicts with miles."""
    hlat, hlng = _home(conn, cfg)
    out = []
    for r in conn.execute(
            f"SELECT cds_code, COALESCE(geo_county_name, county_name) AS county_name, locale, COALESCE(lat_override, lat) AS lat, COALESCE(lng_override, lng) AS lng "
            f"FROM schools WHERE COALESCE(lat_override, lat) IS NOT NULL AND COALESCE(lng_override, lng) IS NOT NULL AND {OPEN}"):
        miles = haversine_miles(hlat, hlng, r["lat"], r["lng"])
        if miles <= cfg.radius_miles:
            out.append({**dict(r), "miles": miles})
    return sorted(out, key=lambda s: s["miles"])


def estimate(straight_miles, locale):
    """Offline drive minutes without rush hour. Unknown locale uses Suburban (a guess)."""
    a, b = COEFFS.get(str(locale or "")[:1], COEFFS["2"])
    return a + b * straight_miles


def rush(county, direction, cfg):
    scale = cfg.rush_scale_am if direction == "am" else cfg.rush_scale_pm
    return 1 + scale * (TTI.get(county, TTI_DEFAULT) - 1)


def _osrm_table(base_url, coords, sources, destinations):  # one request; tests replace it. coords are (lat, lng).
    time.sleep(OSRM_PAUSE)  # crude but sufficient: every request is preceded by a 1 s pause
    path = ";".join(f"{lng},{lat}" for lat, lng in coords)  # OSRM wants longitude first
    q = f"sources={';'.join(map(str, sources))}&destinations={';'.join(map(str, destinations))}&annotations=duration"
    try:
        data = _http_json(f"{base_url.rstrip('/')}/table/v1/driving/{path}?{q}")
    except Exception as e:
        raise RoutingUnavailable(f"the OSRM server did not answer ({type(e).__name__})") from None
    if data.get("code") != "Ok":
        raise RoutingUnavailable(f"the OSRM server refused the request ({data.get('code')})")
    return data["durations"]


def osrm(home, schools, cfg):
    """Free-flow road minutes [(home->school, school->home), ...] for schools (dicts with lat, lng); None = no route.
    Two requests per batch of BATCH schools. `home` is the rounded (lat, lng)."""
    out = []
    for i in range(0, len(schools), BATCH):
        part = schools[i:i + BATCH]
        coords = [home] + [(s["lat"], s["lng"]) for s in part]
        idx = list(range(1, len(coords)))
        to = _osrm_table(cfg.osrm_url, coords, [0], idx)[0]
        back = _osrm_table(cfg.osrm_url, coords, idx, [0])
        out += [(None if a is None else a / 60, None if b[0] is None else b[0] / 60) for a, b in zip(to, back)]
    return out


def update_commutes(conn, cfg, on_progress=None, today=None):
    """Fill/refresh `commutes` for the active home. Returns counts: in_range, computed, skipped, removed."""
    today = today or date.today()
    home = _home(conn, cfg)
    schools = schools_in_radius(conn, cfg)
    # job_search treats "has a commutes row for this home" as "in range", so rows for schools now outside
    # the radius (the user may have shrunk it) must go.
    keep = {s["cds_code"] for s in schools}
    gone = [r[0] for r in conn.execute("SELECT cds_code FROM commutes WHERE home_key = ?", (cfg.home_key,)) if r[0] not in keep]
    conn.executemany("DELETE FROM commutes WHERE home_key = ? AND cds_code = ?", [(cfg.home_key, c) for c in gone])
    have = {r["cds_code"]: r for r in conn.execute("SELECT * FROM commutes WHERE home_key = ?", (cfg.home_key,))}

    def fresh(code):
        r = have.get(code)
        return (r is not None and RANK[r["provider"]] >= RANK[cfg.routing]
                and (today - date.fromisoformat(r["computed_on"])).days <= cfg.max_age_days)
    todo = [s for s in schools if not fresh(s["cds_code"])]
    done = 0
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        if cfg.routing == "osrm":
            times = osrm(home, part, cfg)  # raises RoutingUnavailable; earlier batches are already committed
        else:
            times = [(estimate(s["miles"], s["locale"]),) * 2 for s in part]
        for s, (am, pm) in zip(part, times):
            am = None if am is None else am * rush(s["county_name"], "am", cfg)
            pm = None if pm is None else pm * rush(s["county_name"], "pm", cfg)
            conn.execute(
                "INSERT INTO commutes (cds_code, home_key, straight_miles, am_minutes, pm_minutes, provider, computed_on) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(cds_code, home_key) DO UPDATE SET "
                "straight_miles=excluded.straight_miles, am_minutes=excluded.am_minutes, pm_minutes=excluded.pm_minutes, "
                "provider=excluded.provider, computed_on=excluded.computed_on",
                (s["cds_code"], cfg.home_key, s["miles"], am, pm, cfg.routing, today.isoformat()))
        conn.commit()
        done += len(part)
        if on_progress:
            on_progress(done, len(todo), "commutes")
    return {"in_range": len(schools), "computed": len(todo), "skipped": len(schools) - len(todo), "removed": len(gone)}


def record_drive(conn, cfg, cds_code, minutes, direction):
    """Store a known drive and recompute both of this home's personal factors. Returns (factor_am, factor_pm)."""
    _home(conn, cfg)
    row = conn.execute(f"SELECT {direction}_minutes AS m FROM commutes WHERE home_key = ? AND cds_code = ?",
                       (cfg.home_key, cds_code)).fetchone() if direction in ("am", "pm") else None
    if row is None or row["m"] is None:
        raise NoCommute("that school has no modelled drive time for this home yet")
    conn.execute(
        "INSERT INTO known_drives (home_key, cds_code, direction, minutes, noted_on) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(home_key, cds_code, direction) DO UPDATE SET minutes=excluded.minutes, noted_on=excluded.noted_on",
        (cfg.home_key, cds_code, direction, minutes, date.today().isoformat()))
    f = {}
    for d in ("am", "pm"):
        ratios = [r[0] for r in conn.execute(
            f"SELECT k.minutes / c.{d}_minutes FROM known_drives k JOIN commutes c "
            f"ON c.home_key = k.home_key AND c.cds_code = k.cds_code "
            f"WHERE k.home_key = ? AND k.direction = ? AND c.{d}_minutes > 0", (cfg.home_key, d))]
        f[d] = min(2.0, max(0.5, statistics.median(ratios))) if ratios else None
    f["am"], f["pm"] = (f["am"] or f["pm"] or 1.0, f["pm"] or f["am"] or 1.0)  # a direction without data borrows the other's
    conn.execute("UPDATE homes SET factor_am = ?, factor_pm = ? WHERE home_key = ?", (f["am"], f["pm"], cfg.home_key))
    conn.commit()
    return f["am"], f["pm"]
