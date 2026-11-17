"""Fetches public teaching listings from edjoin.org (anonymous, polite) and saves them to `jobs`."""
import html
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

USER_AGENT = "EdTrawl/0.1 (personal job-search tool)"
DELAY = 2.0          # seconds between requests, never fewer
MAX_PAGES = 20       # hard cap per county; 50 rows a page is 1000 listings
ROWS = 50
TEACHER_TYPES = "1,2,3,4,48,5,46,6,7,8,9,10,11,55,56,63,64"  # RECON.md section 2
LISTING = "https://www.edjoin.org/Home/LoadJobs"
POSTING = "https://www.edjoin.org/Home/JobPosting/"
_POSTING_URL = re.compile(r"https://www\.edjoin\.org/Home/JobPosting/[0-9]+")
_LA = ZoneInfo("America/Los_Angeles")

# RECON.md section 2 (LoadRegions); keys match CDE `County Name`.
COUNTY_IDS = {n: i for i, n in enumerate((
    "Alameda", "Alpine", "Amador", "Butte", "Calaveras", "Colusa", "Contra Costa", "Del Norte", "El Dorado",
    "Fresno", "Glenn", "Humboldt", "Imperial", "Inyo", "Kern", "Kings", "Lake", "Lassen", "Los Angeles",
    "Madera", "Marin", "Mariposa", "Mendocino", "Merced", "Modoc", "Mono", "Monterey", "Napa", "Nevada",
    "Orange", "Placer", "Plumas", "Riverside", "Sacramento", "San Benito", "San Bernardino", "San Diego",
    "San Francisco", "San Joaquin", "San Luis Obispo", "San Mateo", "Santa Barbara", "Santa Clara",
    "Santa Cruz", "Shasta", "Sierra", "Siskiyou", "Solano", "Sonoma", "Stanislaus", "Statewide Ed. Orgs.",
    "Sutter", "Tehama", "Trinity", "Tulare", "Tuolumne", "Ventura", "Yolo", "Yuba"), 1)}


class EdjoinError(Exception):
    """Base of everything this module raises on purpose."""


class EdjoinRefused(EdjoinError):
    """HTTP 403 or 429: the site said stop. `.status` says which, so the UI can word them differently."""
    def __init__(self, status):
        super().__init__(f"edjoin answered HTTP {status}")
        self.status = status


class EdjoinServerError(EdjoinError):
    """HTTP 5xx, or any other unexpected status."""


class EdjoinBadResponse(EdjoinError):
    """200, but not the JSON shape we expect."""


# ---- HTTP (one small function so tests replace it) ----

def _http_get(url):
    """Returns (status, body bytes). Nothing is kept between calls: no cookie jar, no auth."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(5_000_000)
    except urllib.error.HTTPError as e:
        return e.code, b""


_sleep = time.sleep  # tests replace this
_last = [None]       # time of the previous request, so the delay covers fetch_detail too


def _get(url):
    # Only our own two URL shapes ever leave this module.
    if not (url.startswith(LISTING + "?") or _POSTING_URL.fullmatch(url)):
        raise ValueError("not an edjoin listing or posting URL")
    if _last[0] is not None:
        wait = DELAY - (time.monotonic() - _last[0])
        if wait > 0:
            _sleep(wait)
    status, body = _http_get(url)
    _last[0] = time.monotonic()
    if status in (403, 429):
        raise EdjoinRefused(status)
    if status != 200:
        raise EdjoinServerError(f"edjoin answered HTTP {status}")
    return body


# ---- listing ----

def _query(county_id, days, page):
    # All 19 parameters, in the site's order: a partial set got HTTP 500 in the probe.
    params = [("rows", ROWS), ("page", page), ("sort", "postingDate"), ("sortVal", 0), ("order", "desc"),
              ("keywords", ""), ("location", ""), ("searchType", "all"), ("regions", county_id),
              ("jobTypes", TEACHER_TYPES), ("days", days), ("empType", ""), ("catID", 0), ("onlineApps", ""),
              ("recruitmentCenterID", 0), ("stateID", 24), ("regionID", 0), ("districtID", 0), ("searchID", 0)]
    return LISTING + "?" + urllib.parse.urlencode(params, safe=",")


def _parse_page(body):
    try:
        d = json.loads(body)
        rows, pages = d["data"], d["totalPages"]
        ok = (isinstance(rows, list) and isinstance(pages, int) and isinstance(d["totalRecords"], int)
              and all(isinstance(r, dict) and type(r.get("postingID")) is int
                      and isinstance(r.get("positionTitle"), str) for r in rows))
    except (ValueError, KeyError, TypeError):  # JSONDecodeError and bad UTF-8 are ValueErrors
        ok = False
    if not ok:
        raise EdjoinBadResponse("edjoin did not return the expected listing JSON")
    return rows, pages, d["totalRecords"]


def fetch_listings(county_ids, days=31, limit=None, on_progress=None):
    """Rows (dicts as served) for these edjoin county ids, one request at a time."""
    out, expected = [], 0  # expected: listings the counties visited so far say they hold, so progress is one running count
    for cid in county_ids:
        for page in range(1, MAX_PAGES + 1):
            rows, pages, total = _parse_page(_get(_query(cid, days, page)))
            out += rows
            expected += total if page == 1 else 0
            if limit is not None and len(out) >= limit:
                out = out[:limit]
                if on_progress:
                    on_progress(len(out), limit, f"county {cid}")
                return out
            if on_progress:
                # the total is only known once the last county has answered; until then report a bare count
                on_progress(len(out), expected if cid == county_ids[-1] else 0, f"county {cid}")
            if page >= pages or not rows:
                break
    return out


def county_ids_in_range(conn, cfg):
    """Edjoin county ids for counties holding a school with a cached commute from the home."""
    names = [r[0] for r in conn.execute(
        "SELECT DISTINCT COALESCE(s.geo_county_name, s.county_name) FROM commutes c JOIN schools s ON s.cds_code = c.cds_code "
        "WHERE c.home_key = ?", (cfg.home_key,))]
    return sorted({COUNTY_IDS[n] for n in names if n in COUNTY_IDS})


# ---- converting a row ----

def _ms(value):
    """'/Date(ms)/' -> aware UTC datetime; None for anything else, including the year-1 'unset' value."""
    m = re.fullmatch(r"/Date\((-?[0-9]+)\)/", value) if isinstance(value, str) else None
    if not m or int(m[1]) < -2_000_000_000_000:  # before 1906: edjoin's placeholder, not a date
        return None
    return datetime.fromtimestamp(int(m[1]) / 1000, timezone.utc)


_SCHOOLWORD = r"(?:Elementary|Middle|High|Primary|Intermediate|Junior High|Preschool|Academy|School|Charter)"


def site_from_title(title):
    """The school named by a listing title, or None. Conservative: the matcher also searches the whole title."""
    t = re.sub(r"\s+", " ", title or "").strip()
    site = None
    if " @ " in t:  # "Teacher @ Theodore Judah ELEM-114", "... @ Higher Learning Academy (HLA)"
        site = t.rsplit(" @ ", 1)[1]
        if "DEPT-" in site:
            return None  # "@ Special Education - DEPT-62.1" is a department code, not a school
        site = re.sub(r"\s*\([^()]*\)\s*$", "", site)                  # trailing "(HLA)"
        site = re.sub(r"\s+[A-Z]{2,5}-[0-9]+(?:\.[0-9]+)?$", "", site)  # edjoin site code "ELEM-114"
    elif (m := re.search(r"\(([^()]*\b" + _SCHOOLWORD + r"\b[^()]*)\)$", t)) and not re.search(
            r"School Year|Department|Dept", m[1]):
        site = m[1]                                                    # "(Carroll Elementary School)"
    elif m := re.search(r" - ([^-()]*\b(?:Elementary|Middle School|High School|Academy|Preschool))$", t):
        site = m[1]                                                    # "- Folsom High School"
    elif m := re.search(r"\bat ([A-Z][^()]*?)\s*(?:\([^()]*\))?$", t):
        site = m[1]                                                    # "Education at Marvin Marshall (PC #...)"
    site = (site or "").strip(" -,")
    if not site or len(site) > 80 or re.search(r"\b(?:DEPT|Department|Program|Online)\b|[0-9]{4}|Schools$", site):
        return None  # a department, program, year or plural 'Schools' (a district) is not a site
    return site


def _row(r, today):
    posted, until = _ms(r.get("postingDate")), _ms(r.get("displayUntil"))
    # displayUntil is a real instant only for 'By Date'; Pacific local date is what the district means.
    deadline = until.astimezone(_LA).date().isoformat() if until and r.get("displayFlag") == "By Date" else None
    n = r.get("numberOpenings")
    return {
        "posting_id": r["postingID"], "title": r["positionTitle"], "district_raw": r.get("districtName"),
        "edjoin_district_id": None,  # the listing row carries no district id
        "city": r.get("city"), "county": r.get("countyName"), "category": r.get("jobType"),
        "salary_info": r.get("salaryInfo"), "openings": n if type(n) is int else None,
        "posted_on": posted.date().isoformat() if posted else None, "deadline": deadline,
        "url": POSTING + str(r["postingID"]),  # built here, never taken from the row
        "location_raw": site_from_title(r["positionTitle"]),
        "today": today, "raw_json": json.dumps(r, sort_keys=True),
    }


def save_listings(conn, rows, today=None):
    """Upserts rows; returns (new, updated). Never touches district_code, cds_code or first_seen."""
    today = today or datetime.now(_LA).date().isoformat()
    new = updated = 0
    for r in rows:
        v = _row(r, today)
        exists = conn.execute("SELECT 1 FROM jobs WHERE posting_id = ?", (v["posting_id"],)).fetchone()
        conn.execute(
            """INSERT INTO jobs (posting_id, title, district_raw, edjoin_district_id, city, county, category,
                 salary_info, openings, posted_on, deadline, url, location_raw, first_seen, last_seen, raw_json)
               VALUES (:posting_id, :title, :district_raw, :edjoin_district_id, :city, :county, :category,
                 :salary_info, :openings, :posted_on, :deadline, :url, :location_raw, :today, :today, :raw_json)
               ON CONFLICT(posting_id) DO UPDATE SET
                 title = excluded.title, district_raw = excluded.district_raw,
                 edjoin_district_id = excluded.edjoin_district_id, city = excluded.city,
                 county = excluded.county, category = excluded.category, salary_info = excluded.salary_info,
                 openings = excluded.openings, posted_on = excluded.posted_on, deadline = excluded.deadline,
                 url = excluded.url, last_seen = excluded.last_seen, raw_json = excluded.raw_json,
                 location_raw = COALESCE(NULLIF(excluded.location_raw, ''), jobs.location_raw)""", v)
        updated += bool(exists)
        new += not exists
    conn.commit()
    return new, updated


def load_file(conn, path, today=None):
    """Saves a stored LoadJobs response; returns (new, updated)."""
    with open(path, "rb") as f:
        rows, _, _ = _parse_page(f.read())
    return save_listings(conn, rows, today)


# ---- detail page ----

def fetch_detail(posting_id):
    """The `Location(s):` text of one posting, or None."""
    if type(posting_id) is not int or posting_id <= 0:
        raise ValueError("posting_id must be a positive integer")
    return parse_detail(_get(POSTING + str(posting_id)).decode("utf-8", "replace"))


def parse_detail(html_text):
    """Text of the optional `Location(s):` block, or None. The JSON-LD address is the district office: unused."""
    m = re.search(r"Location\(s\):\s*</h[1-6]>\s*<div[^>]*>(.*?)</div>", html_text, re.S)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", m[1]))).strip() if m else ""
    return text or None


def fetch_sites(conn, posting_ids, on_progress=None):
    """Read the posting page of each job and store its `Location(s):` text. Returns how many named a site.
    location_raw: NULL = not looked yet, '' = looked and the posting names no site (so it is not fetched again)."""
    found = 0
    for i, pid in enumerate(posting_ids, 1):
        site = fetch_detail(pid) or ""
        conn.execute("UPDATE jobs SET location_raw = ? WHERE posting_id = ? AND location_raw IS NULL", (site, pid))
        conn.commit()  # per posting: a refusal partway keeps what was already read
        found += bool(site)
        if on_progress:
            on_progress(i, len(posting_ids), "details")
    return found
