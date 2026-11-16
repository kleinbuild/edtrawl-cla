"""SQLite schema for EdTrawl. `python db.py` creates edtrawl.db and lists what it holds."""
import sqlite3
from typing import NamedTuple


class CdeColumn(NamedTuple):
    header: str          # exact header in the 2025-26 CDE CSV
    column: str | None   # snake_case column; None = recognized but not stored
    sql_type: str | None # TEXT | INTEGER | REAL; what ingest coerces to
    tables: tuple        # tables that receive this value; () = dropped
    constraint: str = ""


IDENTITY, SNAPSHOT, BOTH = ("schools",), ("school_years",), ("schools", "school_years")

# Every header of the 2025-26 file, in file order. Generates the DDL of `schools` and `school_years`
# and drives ingest, so the loader and the schema cannot drift. An unlisted header is unknown.
# Codes (CDS, district, ZIP, grade, charter number) are TEXT: they are labels with leading zeros, not numbers.
CDE_COLUMNS = (
    CdeColumn("OBJECTID", None, None, ()),  # row id of the publishing GIS layer, changes between releases
    CdeColumn("Academic Year", "academic_year", "TEXT", SNAPSHOT, "NOT NULL"),
    CdeColumn("Fed ID", "fed_id", "TEXT", IDENTITY),
    # TEXT, 14 chars: 870 codes start with 0, which an INTEGER would silently drop.
    CdeColumn("CDS Code", "cds_code", "TEXT", BOTH, "NOT NULL"),
    CdeColumn("District Code", "district_code", "TEXT", IDENTITY, "NOT NULL"),
    CdeColumn("School Code", "school_code", "TEXT", IDENTITY),
    CdeColumn("Region", "region", "TEXT", IDENTITY),
    CdeColumn("County Name", "county_name", "TEXT", IDENTITY),
    CdeColumn("District Name", "district_name", "TEXT", IDENTITY),
    CdeColumn("School Name", "school_name", "TEXT", IDENTITY, "NOT NULL"),
    CdeColumn("School Type", "school_type", "TEXT", IDENTITY),
    CdeColumn("Status", "status", "TEXT", IDENTITY),
    # Dates are stored ISO (YYYY-MM-DD); ingest converts the published '1/1/1938 12:00:00 AM'.
    CdeColumn("Open Date", "open_date", "TEXT", IDENTITY,
              "CHECK (open_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')"),
    CdeColumn("Closed Date", "closed_date", "TEXT", IDENTITY,
              "CHECK (closed_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')"),
    CdeColumn("School Level", "school_level", "TEXT", IDENTITY),
    CdeColumn("Grade Low", "grade_low", "TEXT", IDENTITY),
    CdeColumn("Grade High", "grade_high", "TEXT", IDENTITY),
    CdeColumn("Charter", "charter", "TEXT", IDENTITY, "CHECK (charter IN ('Y','N'))"),
    CdeColumn("Charter Num", "charter_num", "TEXT", IDENTITY),
    CdeColumn("Charter Funding Type", "charter_funding_type", "TEXT", IDENTITY),
    CdeColumn("Virtual", "virtual", "TEXT", IDENTITY),  # N/C/V/F as published; no CHECK so a new CDE code loads
    CdeColumn("Magnet", "magnet", "TEXT", IDENTITY, "CHECK (magnet IN ('Y','N'))"),
    # Title I, DASS and ESSA status are designations for one year, so they are snapshot columns.
    CdeColumn("Title I", "title_i", "TEXT", SNAPSHOT, "CHECK (title_i IN ('Y','N'))"),
    CdeColumn("DASS", "dass", "TEXT", SNAPSHOT, "CHECK (dass IN ('Y','N'))"),
    CdeColumn("Assistance Status ESSA", "essa_status", "TEXT", SNAPSHOT),
    CdeColumn("Street", "street", "TEXT", IDENTITY),
    CdeColumn("City", "city", "TEXT", IDENTITY),
    CdeColumn("Zip", "zip", "TEXT", IDENTITY),
    CdeColumn("State", None, None, ()),  # always CA
    CdeColumn("Locale", "locale", "TEXT", IDENTITY),
    CdeColumn("School Website", "website", "TEXT", IDENTITY),
    CdeColumn("Enroll Total", "enroll_total", "INTEGER", SNAPSHOT),
    CdeColumn("African American", "african_american", "INTEGER", SNAPSHOT),
    CdeColumn("African American (%)", "african_american_pct", "REAL", SNAPSHOT),
    CdeColumn("American Indian", "american_indian", "INTEGER", SNAPSHOT),
    CdeColumn("American Indian (%)", "american_indian_pct", "REAL", SNAPSHOT),
    CdeColumn("Asian", "asian", "INTEGER", SNAPSHOT),
    CdeColumn("Asian (%)", "asian_pct", "REAL", SNAPSHOT),
    CdeColumn("Filipino", "filipino", "INTEGER", SNAPSHOT),
    CdeColumn("Filipino (%)", "filipino_pct", "REAL", SNAPSHOT),
    CdeColumn("Hispanic", "hispanic", "INTEGER", SNAPSHOT),
    CdeColumn("Hispanic (%)", "hispanic_pct", "REAL", SNAPSHOT),
    CdeColumn("Pacific Islander", "pacific_islander", "INTEGER", SNAPSHOT),
    CdeColumn("Pacific Islander (%)", "pacific_islander_pct", "REAL", SNAPSHOT),
    CdeColumn("White", "white", "INTEGER", SNAPSHOT),
    CdeColumn("White (%)", "white_pct", "REAL", SNAPSHOT),
    CdeColumn("Two or More Races", "two_or_more_races", "INTEGER", SNAPSHOT),
    CdeColumn("Two or More Races (%)", "two_or_more_races_pct", "REAL", SNAPSHOT),
    CdeColumn("Not Reported", "not_reported", "INTEGER", SNAPSHOT),
    CdeColumn("Not Reported (%)", "not_reported_pct", "REAL", SNAPSHOT),
    CdeColumn("English Learner", "english_learner", "INTEGER", SNAPSHOT),
    CdeColumn("English Learner (%)", "english_learner_pct", "REAL", SNAPSHOT),
    CdeColumn("Foster", "foster", "INTEGER", SNAPSHOT),
    CdeColumn("Foster (%)", "foster_pct", "REAL", SNAPSHOT),
    CdeColumn("Homeless", "homeless", "INTEGER", SNAPSHOT),
    CdeColumn("Homeless (%)", "homeless_pct", "REAL", SNAPSHOT),
    CdeColumn("Migrant", "migrant", "INTEGER", SNAPSHOT),
    CdeColumn("Migrant (%)", "migrant_pct", "REAL", SNAPSHOT),
    CdeColumn("Socioeconomically Disadvantaged", "socioeconomically_disadvantaged", "INTEGER", SNAPSHOT),
    CdeColumn("Socioeconomically Disadvantaged (%)", "socioeconomically_disadvantaged_pct", "REAL", SNAPSHOT),
    CdeColumn("Students with Disabilities", "students_with_disabilities", "INTEGER", SNAPSHOT),
    CdeColumn("Students with Disabilities (%)", "students_with_disabilities_pct", "REAL", SNAPSHOT),
    CdeColumn("Free/Reduced Meal Eligible", "free_reduced_meal_eligible", "INTEGER", SNAPSHOT),
    CdeColumn("Free/Reduced Meal Eligible (%)", "free_reduced_meal_eligible_pct", "REAL", SNAPSHOT),
    CdeColumn("Grade TK", "grade_tk", "INTEGER", SNAPSHOT),
    CdeColumn("Grade KG", "grade_kg", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 1", "grade_1", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 2", "grade_2", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 3", "grade_3", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 4", "grade_4", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 5", "grade_5", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 6", "grade_6", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 7", "grade_7", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 8", "grade_8", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 9", "grade_9", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 10", "grade_10", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 11", "grade_11", "INTEGER", SNAPSHOT),
    CdeColumn("Grade 12", "grade_12", "INTEGER", SNAPSHOT),
    CdeColumn("Latitude", "lat", "REAL", IDENTITY),
    CdeColumn("Longitude", "lng", "REAL", IDENTITY),
    # Other geographic and legislative districts: not used by anything in this build.
    CdeColumn("Geographic County Code", None, None, ()),
    # Where the school physically is. 89 schools (mostly charters) are administered from another county,
    # so traffic and "which county's listings to fetch" use this, not county_name.
    CdeColumn("Geographic County Name", "geo_county_name", "TEXT", IDENTITY),
    CdeColumn("Geographic Elementary District Code", None, None, ()),
    CdeColumn("Geographic Elementary District Name", None, None, ()),
    CdeColumn("Geographic High District Code", None, None, ()),
    CdeColumn("Geographic High District Name", None, None, ()),
    CdeColumn("Geographic Unified District Code", None, None, ()),
    CdeColumn("Geographic Unified District Name", None, None, ()),
    CdeColumn("US Congressional District", None, None, ()),
    CdeColumn("CA State Senate District", None, None, ()),
    CdeColumn("CA State Assembly District", None, None, ()),
    # Staff counts first appear in 2025-26; older snapshots leave them NULL.
    CdeColumn("Staff Total", "staff_total", "INTEGER", SNAPSHOT),
    CdeColumn("Staff Teacher", "staff_teacher", "INTEGER", SNAPSHOT),
    CdeColumn("Staff Admin", "staff_admin", "INTEGER", SNAPSHOT),
    CdeColumn("Staff Pupil Services", "staff_pupil_services", "INTEGER", SNAPSHOT),
    CdeColumn("Staff Other", "staff_other", "INTEGER", SNAPSHOT),
    CdeColumn("x", None, None, ()),  # Web Mercator copy of Longitude
    CdeColumn("y", None, None, ()),  # Web Mercator copy of Latitude
)


def _cde_columns(table):
    return ",\n  ".join(f"{c.column} {c.sql_type} {c.constraint}".rstrip()
                        for c in CDE_COLUMNS if table in c.tables)


SCHEMA = f"""
-- Identity and yearly snapshot are separate tables: a school's name and place outlive any one year,
-- enrollment is a fact about one year, and keeping both years is what the trend line needs.
-- Every upsert into these tables uses ON CONFLICT ... DO UPDATE, never INSERT OR REPLACE:
-- REPLACE deletes the old row first, which wipes the override columns and breaks foreign keys.
CREATE TABLE IF NOT EXISTS schools (               -- identity, never deleted
  {_cde_columns("schools")},
  -- Hand corrections live in their own columns so ingest can overwrite lat/lng freely and never
  -- touch them; readers use COALESCE(lat_override, lat).
  lat_override REAL, lng_override REAL,
  first_year TEXT NOT NULL, last_year TEXT NOT NULL,
  PRIMARY KEY (cds_code),
  CHECK (length(cds_code) = 14),
  CHECK (length(district_code) = 7)
);

CREATE TABLE IF NOT EXISTS school_years (          -- snapshot per academic year
  {_cde_columns("school_years")},
  PRIMARY KEY (cds_code, academic_year),
  FOREIGN KEY (cds_code) REFERENCES schools(cds_code)
);

CREATE TABLE IF NOT EXISTS homes (
  home_key TEXT PRIMARY KEY,                       -- 'lat,lng' rounded to 3 dp (~100 m)
  label TEXT NOT NULL DEFAULT 'home',              -- never the street address
  factor_am REAL NOT NULL DEFAULT 1.0 CHECK (factor_am BETWEEN 0.5 AND 2.0),
  factor_pm REAL NOT NULL DEFAULT 1.0 CHECK (factor_pm BETWEEN 0.5 AND 2.0),
  created_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS known_drives (          -- what the user told us, kept so the factor can be recomputed
  home_key TEXT NOT NULL REFERENCES homes(home_key),
  cds_code TEXT NOT NULL REFERENCES schools(cds_code),
  direction TEXT NOT NULL CHECK (direction IN ('am','pm')),
  minutes REAL NOT NULL CHECK (minutes BETWEEN 1 AND 240),
  noted_on TEXT NOT NULL,
  PRIMARY KEY (home_key, cds_code, direction)
);

CREATE TABLE IF NOT EXISTS commutes (              -- cached computation, before the personal factor
  cds_code TEXT NOT NULL REFERENCES schools(cds_code),
  home_key TEXT NOT NULL REFERENCES homes(home_key),
  straight_miles REAL NOT NULL,
  am_minutes REAL, pm_minutes REAL,                -- arrive 07:00 / leave 15:30; NULL = no route
  provider TEXT NOT NULL CHECK (provider IN ('estimate','osrm')),
  computed_on TEXT NOT NULL,
  PRIMARY KEY (cds_code, home_key)
);

CREATE TABLE IF NOT EXISTS jobs (                  -- scraped listings
  posting_id INTEGER PRIMARY KEY,
  title TEXT NOT NULL, district_raw TEXT, edjoin_district_id INTEGER,
  city TEXT, county TEXT, category TEXT, salary_info TEXT, openings INTEGER,
  posted_on TEXT, deadline TEXT, url TEXT NOT NULL,
  location_raw TEXT,
  district_code TEXT, cds_code TEXT REFERENCES schools(cds_code),
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, raw_json TEXT
);

CREATE TABLE IF NOT EXISTS name_matches (          -- cached matching decisions
  district_raw TEXT NOT NULL, location_raw TEXT NOT NULL DEFAULT '',
  district_code TEXT, cds_code TEXT,
  method TEXT NOT NULL,                            -- 'exact' | 'fuzzy' | 'llm' | 'manual' | 'unsure'
  score REAL, model TEXT, matched_on TEXT NOT NULL,
  PRIMARY KEY (district_raw, location_raw)
);

CREATE TABLE IF NOT EXISTS job_marks (             -- the user's decisions
  posting_id INTEGER PRIMARY KEY REFERENCES jobs(posting_id),
  status TEXT NOT NULL CHECK (status IN ('kept','tossed','applied')),
  note TEXT, marked_on TEXT NOT NULL
);

-- The only join below not served by a primary key: a district-wide job's schools.
CREATE INDEX IF NOT EXISTS schools_district ON schools(district_code);

-- One row per job per home; callers filter WHERE home_key = <active home from config>,
-- because a view cannot read config. Minutes are after the personal factor, each direction its own.
-- A school-matched job fills am_minutes/pm_minutes; a district-wide job (cds_code NULL) fills the
-- district_* columns, taken over every school with a cached commute for that home, using the slower
-- direction per school.
CREATE VIEW IF NOT EXISTS job_search AS
SELECT
  j.posting_id, j.title, j.district_raw, j.location_raw, j.city AS job_city, j.county AS job_county,
  j.category, j.salary_info, j.openings, j.posted_on, j.deadline, j.url, j.first_seen, j.last_seen,
  j.cds_code,
  COALESCE(j.district_code, s.district_code) AS district_code,
  COALESCE(s.district_name,
           (SELECT district_name FROM schools WHERE district_code = j.district_code LIMIT 1)) AS district_name,
  COALESCE(s.county_name,
           (SELECT county_name FROM schools WHERE district_code = j.district_code LIMIT 1)) AS county_name,
  s.school_name, s.city, s.school_type, s.school_level, s.grade_low, s.grade_high,
  s.charter, s.virtual, s.locale, s.website,
  COALESCE(s.lat_override, s.lat) AS lat, COALESCE(s.lng_override, s.lng) AS lng,
  h.home_key,
  COALESCE(c.provider, d.provider) AS provider,
  c.am_minutes * h.factor_am AS am_minutes,
  c.pm_minutes * h.factor_pm AS pm_minutes,
  d.min_minutes AS district_min_minutes,
  d.max_minutes AS district_max_minutes,
  d.schools_in_range AS district_schools_in_range,
  cur.academic_year, cur.enroll_total, cur.staff_teacher, cur.title_i,
  prev.academic_year AS prev_academic_year, prev.enroll_total AS prev_enroll_total,
  m.status AS mark_status, m.marked_on
FROM jobs j
CROSS JOIN homes h
LEFT JOIN schools s ON s.cds_code = j.cds_code
LEFT JOIN school_years cur ON cur.cds_code = s.cds_code
  AND cur.academic_year = (SELECT MAX(academic_year) FROM school_years WHERE cds_code = s.cds_code)
LEFT JOIN school_years prev ON prev.cds_code = s.cds_code
  AND prev.academic_year = (SELECT MAX(academic_year) FROM school_years
                            WHERE cds_code = s.cds_code AND academic_year < cur.academic_year)
LEFT JOIN commutes c ON c.cds_code = s.cds_code AND c.home_key = h.home_key
LEFT JOIN (
  SELECT ds.district_code, dc.home_key,
    MIN(dc.provider) AS provider,                  -- 'estimate' sorts before 'osrm': the weakest source wins
    MIN(MAX(dc.am_minutes * dh.factor_am, dc.pm_minutes * dh.factor_pm)) AS min_minutes,
    MAX(MAX(dc.am_minutes * dh.factor_am, dc.pm_minutes * dh.factor_pm)) AS max_minutes,
    COUNT(MAX(dc.am_minutes, dc.pm_minutes)) AS schools_in_range  -- schools with a route both ways
  FROM commutes dc
  JOIN schools ds ON ds.cds_code = dc.cds_code
  JOIN homes dh ON dh.home_key = dc.home_key
  GROUP BY ds.district_code, dc.home_key
) d ON j.cds_code IS NULL AND d.district_code = j.district_code AND d.home_key = h.home_key
LEFT JOIN job_marks m ON m.posting_id = j.posting_id;
"""


def connect(path="edtrawl.db"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # per connection in SQLite; off by default
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)  # every statement is IF NOT EXISTS, so running it twice is a no-op


if __name__ == "__main__":
    conn = connect()
    init_db(conn)
    for row in conn.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY type, name"):
        print(f"{row['type']:5}  {row['name']}")
    conn.close()
