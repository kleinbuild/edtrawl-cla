"""Load California Department of Education school CSVs into `schools` (identity) and `school_years` (snapshot)."""
import csv
import math
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import db

URLS = {  # ArcGIS Hub download items on gis.data.ca.gov
    "2025-26": "https://gis.data.ca.gov/api/download/v1/items/0cab44bcfd9a44eb88197147e4d37e8b/csv?layers=0",
    "2024-25": "https://gis.data.ca.gov/api/download/v1/items/586424d4a1964277a2e0b73191da51bb/csv?layers=0",
}

# 2024-25 header -> 2025-26 header (the 18 names that differ; the other 5 old-only headers are in IGNORE).
HEADER_ALIASES = {
    "Funding Type": "Charter Funding Type", "American Indian Pct": "American Indian (%)",
    "CountyCodeGeo": "Geographic County Code", "CountyNameGeo": "Geographic County Name",
    "DistrictElemCodeGeo": "Geographic Elementary District Code", "DistrictElemNameGeo": "Geographic Elementary District Name",
    "DistrictHighCodeGeo": "Geographic High District Code", "DistrictHighNameGeo": "Geographic High District Name",
    "DistrictUnifiedCodeGeo": "Geographic Unified District Code", "DistrictUnifiedNameGeo": "Geographic Unified District Name",
    "CongUSGeo": "US Congressional District", "SenateCAGeo": "CA State Senate District",
    "AssemblyCAGeo": "CA State Assembly District",
}
# Duplicate columns only the 2024-25 file has. Listed by name so a genuinely new header still raises.
IGNORE = {"Locale Four", "Virtual2", "Charter2", "Magnet2", "DASS2"}

COLS = [c for c in db.CDE_COLUMNS if c.column]                       # the one list; everything below derives from it
IDENTITY = [c.column for c in COLS if "schools" in c.tables]
SNAPSHOT = [c.column for c in COLS if "school_years" in c.tables]
FLAGS = {"charter", "magnet", "title_i", "dass"}                     # the columns with a Y/N CHECK


def coerce(value, sql_type, column=""):
    """One place for every cell: blank, '*' or unparseable -> None, otherwise the typed value."""
    v = (value or "").strip()
    if not v:
        return None
    if sql_type in ("INTEGER", "REAL"):
        try:
            f = float(v)                                             # '*' and other suppression markers fail here
        except ValueError:
            return None
        if not math.isfinite(f):
            return None
        return (int(f) if f.is_integer() else None) if sql_type == "INTEGER" else f
    if column.endswith("_date"):                                     # published as '1/1/1938 12:00:00 AM'; CHECK wants ISO
        try:
            return datetime.strptime(v, "%m/%d/%Y %I:%M:%S %p").date().isoformat()
        except ValueError:
            return None
    if column in FLAGS:                                              # anything but Y/N would fail the CHECK; store NULL
        return v.upper() if v.upper() in ("Y", "N") else None
    if column == "zip":                                              # PLAN.md is silent on ZIP+4: keep the 5-digit ZIP
        return v[:5]
    return v


def _upsert_sql():
    ident = ", ".join(IDENTITY + ["first_year", "last_year"])
    marks = ", ".join("?" * (len(IDENTITY) + 2))
    # Per column, not one WHERE on the whole DO UPDATE: a WHERE would also stop first_year/last_year widening
    # when an older file is loaded after a newer one. Newest year wins identity; ties (re-ingest) overwrite.
    sets = [f"{c}=CASE WHEN excluded.last_year >= schools.last_year THEN excluded.{c} ELSE schools.{c} END"
            for c in IDENTITY if c != "cds_code"]
    sets += ["first_year=MIN(schools.first_year, excluded.first_year)", "last_year=MAX(schools.last_year, excluded.last_year)"]
    # lat_override/lng_override are never named here, so a hand-corrected coordinate survives; lat/lng follow CDE.
    schools = f"INSERT INTO schools ({ident}) VALUES ({marks}) ON CONFLICT(cds_code) DO UPDATE SET {', '.join(sets)}"
    snap_sets = ", ".join(f"{c}=excluded.{c}" for c in SNAPSHOT if c not in ("cds_code", "academic_year"))
    snaps = (f"INSERT INTO school_years ({', '.join(SNAPSHOT)}) VALUES ({', '.join('?' * len(SNAPSHOT))}) "
             f"ON CONFLICT(cds_code, academic_year) DO UPDATE SET {snap_sets}")  # never INSERT OR REPLACE: it deletes the row
    return schools, snaps


def ingest(conn, csv_path, academic_year=None, on_progress=None):
    """Load one CDE file in one transaction. Returns {'academic_year', 'schools', 'snapshots'}."""
    with open(csv_path, encoding="utf-8-sig", newline="") as f:      # the files carry a BOM and CRLF
        reader = csv.DictReader(f)
        known = {c.header for c in db.CDE_COLUMNS}
        for h in reader.fieldnames:
            if HEADER_ALIASES.get(h, h) not in known and h not in IGNORE:
                raise ValueError(f"Unrecognized CSV header: {h!r}")
        rows = [{HEADER_ALIASES.get(k, k): v for k, v in r.items()} for r in reader]
    sql_schools, sql_snaps = _upsert_sql()
    year = None
    with conn:  # commits on success, rolls the whole file back on any error
        for i, r in enumerate(rows, 1):
            vals = {c.column: coerce(r.get(c.header), c.sql_type, c.column) for c in COLS}
            # 2024-25 publishes District Code as 5 digits (no county); the first 7 CDS chars are the 7-digit code in both files.
            vals["district_code"] = (vals["cds_code"] or "")[:7]
            year = academic_year or vals["academic_year"]
            vals["academic_year"], vals["first_year"], vals["last_year"] = year, year, year
            # Identity first: the snapshot's foreign key points at it.
            conn.execute(sql_schools, [vals[c] for c in IDENTITY + ["first_year", "last_year"]])
            conn.execute(sql_snaps, [vals[c] for c in SNAPSHOT])
            if on_progress and (i % 500 == 0 or i == len(rows)):
                on_progress(i, len(rows), f"CDE {year}")
    return {"academic_year": year, "schools": len(rows), "snapshots": len(rows)}


def download(year, dest_dir=Path(__file__).with_name("data")):
    """Fetch the CDE CSV for `year` to <dest_dir>/schools_<year>.csv and return the path."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"schools_{year}.csv"
    req = urllib.request.Request(URLS[year], headers={"User-Agent": "EdTrawl"})
    # The hub builds the file on demand: the first request can answer 202 + a short JSON note, and a
    # repeat a few seconds later gets the CSV. Ask again for up to a minute before giving up.
    for attempt in range(12):
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            if resp.status == 200 and not data.lstrip(b"\xef\xbb\xbf").startswith(b"{"):
                break
        time.sleep(5)
    else:
        raise RuntimeError(f"CDE file for {year} is not ready yet; try again in a minute")
    tmp = path.with_suffix(".part")                                  # write then rename so a failed download leaves no half file
    tmp.write_bytes(data)
    tmp.replace(path)
    return path
