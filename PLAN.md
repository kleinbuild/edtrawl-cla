# EdTrawl (parallel build) — Plan, Architecture, Experience Design, Agent Briefs

Source: `04_claude_code_parallel_build.md`. This is the Claude-side build that gets compared against the hand-built one. The design comes from the spec, from the owner's later instructions, and from facts checked on 2026-11-16. Revision 3.

## 0. Isolation rule (protects the experiment)

No agent may read `../EdTrawl/`, `../claudeddb.py`, or anything else outside this directory. Nothing outside this directory was read while writing this plan.

## 1. Decisions I made, and the evidence

| Decision | Why |
|---|---|
| **No TomTom, and no other commercial traffic API, anywhere in this build.** | I read TomTom's portal terms in full (docs.tomtom.com/legal/terms-and-conditions, rendered in a browser). Free access is licensed "for Evaluation Use only", defined as "internal evaluation and testing" (cl. 2.2). Storing results is prohibited except as the response's cache headers allow (cl. 11.4), which rules out the spec's 90-day travel cache. Using results "to create any derivative work" or a "derived database" is prohibited (11.6.1), as is any algorithm whose output would make the product "redundant" (11.6.3), which is exactly what fitting an estimator to their results is. Comparing against a competitor's product needs written approval (11.6.10). A paid licence covers only an app with "Asset Management Functionality" and requires passing an end-user licence down. This is my reading as an engineer, not legal advice, but every part of my earlier travel plan collides with one of these clauses. |
| **Travel time is built on open data instead:** OpenStreetMap road routing (OSRM) for real road time, multiplied by a rush-hour factor from the federal Urban Congestion Report, corrected by one drive the user already knows. | OSM data is under the ODbL, which allows caching and deriving. Both free OSRM servers answered a test table request in half a second. The FHWA report is current (July–September 2026) and lists seven California metro areas. The user's own known drive is the only ground truth nobody licenses. |
| **OSRM is built now, not later.** | With TomTom gone it is the only source of real road distance, and it is what handles a bay or a mountain range. The offline formula is fitted against it. |
| **Home address → coordinates through the US Census geocoder.** | Free, no key, tested live (0.5 s). One request per setup. The address is never written to disk. ZIP code and typed coordinates work offline. |
| **LLM matching is an optional upgrade, not a requirement.** | The owner has no Anthropic key and will not pay for APIs. Exact and coded fuzzy matching run with nothing installed; a local model through Ollama is the free LLM tier; DeepSeek works through the same code path. |
| **The friendly face is a guided terminal flow plus one self-contained HTML page.** | The spec says CLI, and the audience is teachers, not programmers. One command to remember, a guided first run, and a page they can just open. |

## 2. Verified facts

| Fact | Status |
|---|---|
| 2025-26 CSV: 9,946 rows, 98 columns, UTF-8 with BOM. CDS codes all 14 chars, 870 with a leading zero, unique; first 7 chars = district code (1,009 districts) | verified by download |
| 2024-25 file is item `586424d4a1964277a2e0b73191da51bb`, same URL pattern; 18 column names differ; no `Staff *` columns; 2 schools with blank coordinates; ZIP+4 zips | verified by download |
| No suppression marker (`*`) in either file's numeric columns today | verified; coercion still maps blank/`*`/non-numeric → NULL |
| `Virtual` is `N/C/V/F`. `Charter`, `Magnet`, `Title I`, `DASS` are Y/N | verified |
| edjoin `robots.txt` is `Allow: /`; the search page's JS calls `/Home/LoadJobs` for visitors not signed in, with 19 query params; listing rows have district, city, county, title, deadline, salary text, **no school name**; login has a CAPTCHA | read from the site's files; live call not yet confirmed (Agent B) |
| OSRM table service on `router.project-osrm.org` and on `routing.openstreetmap.de/routed-car` returns durations (seconds) and distances (metres); coordinates are `lng,lat` | verified by one live request each |
| OSRM server rules: at most 1 request/second, "reasonable, non-commercial use", a User-Agent identifying the app, attribution to OpenStreetMap (ODbL) and OSRM, no uptime guarantee | read from the project wiki and the FOSSGIS about page |
| Census geocoder `…/geocoder/locations/onelineaddress?benchmark=Public_AR_Current&format=json` returns `result.addressMatches[0].coordinates` as `x`=lng, `y`=lat | verified live. I have not read a usage policy for it |
| FHWA Urban Congestion Report, July–September 2026, Travel Time Index (peak-period ÷ free-flow travel time; AM peak 6–9, PM peak 4–7, weekdays): Los Angeles 1.59, San Jose 1.45, San Francisco 1.37, Riverside–San Bernardino 1.27, San Diego 1.25, Sacramento 1.17, Fresno 1.07; national 1.27 | read from the report PDF. It is a US federal agency publication; the page carries no licence statement |
| Local machine: Python 3.12.3, SQLite 3.45.1, Chrome and `playwright-cli` present | verified |

Not verified, each assigned to an agent: OSRM's maximum coordinates per table request; DeepSeek's and Ollama's current request details; how well a small local model matches names.

## 3. Architecture

```
 address / ZIP / lat,lng ─► home (rounded to ~100 m, address not stored)
 data.ca.gov CSV ─► ingest.py ─► schools (identity) + school_years (snapshot)
                                              │
 travel.py: straight-line filter ─► [osrm road time | offline formula] × rush-hour factor ─► commutes (cache)
                                              │                     × personal factor from a drive you know
 edjoin ─► edjoin.py ─► jobs ─► match.py: exact ─► coded fuzzy ─► LLM if configured ─► review list
                                              │
            job_search view (joins everything) ─► query.py ─► ui.py ─► terminal flows, HTML chart
```

Plain Python owns every step and loop. The optional LLM is called from one function, returns one answer that is checked against a list, and decides nothing else.

### Runs with nothing but Python

| Need | Offline | Free, network, no key | Optional |
|---|---|---|---|
| Home | ZIP code, or typed `lat,lng` | street address via Census geocoder | — |
| School data | CSV placed in `data/` by hand | download from data.ca.gov | — |
| Commute | fitted formula on straight-line miles | OSRM road time | self-hosted OSRM via `osrm_url` |
| Rush hour | built-in FHWA table by county | — | one known drive (`drove`) |
| Matching | exact + coded fuzzy + review list | — | local model (Ollama) or DeepSeek |
| Jobs | `fetch --from-file` | edjoin | — |

Gate for the whole build: with an untouched config, the full pipeline completes and shows jobs.

### Files (one owner each)

| File | Purpose |
|---|---|
| `db.py` | `connect()`, schema, `CDE_COLUMNS`, `init_db()`; `python db.py` creates everything |
| `config.py` | loads and updates gitignored `config.toml` |
| `ingest.py` | download + load CDE CSV |
| `travel.py` | geocode, radius filter, `estimate`, `osrm`, rush-hour factors, commute cache |
| `calibrate.py` | developer-only: fits the offline formula against OSRM, prints the error |
| `edjoin.py` | fetch listings and posting details |
| `match.py` | exact, coded, LLM matching; match cache |
| `query.py` | search function + SQL |
| `ui.py` | every user-facing string and all rendering: cards, tables, progress, prompts, colour and emoji gating |
| `flows.py` | guided flows: `setup`, `go`, triage deck, school card, keepers, logbook, `drove` |
| `chart.py` | writes the self-contained HTML page |
| `edtrawl.py` | argparse entry point |
| `test_edtrawl.py`, `tests/fixtures/` | one stdlib `unittest` file, offline |
| `README.md`, `.gitignore`, `config.example.toml` | — |

Dependencies: standard library only, including HTTP (`urllib`). The probe showed edjoin needs no session, so there is no browser automation.

**Modules do not print.** `ingest`, `travel`, `edjoin`, `match`, `query` return data and accept an optional `on_progress(done, total, label)` callback. Only `ui.py` writes to the terminal. That keeps the voice in one place and the logic testable.

### Schema

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schools (               -- identity, never deleted
  cds_code       TEXT PRIMARY KEY CHECK (length(cds_code) = 14),
  district_code  TEXT NOT NULL CHECK (length(district_code) = 7),
  county_name TEXT, district_name TEXT, school_name TEXT NOT NULL,
  school_type TEXT, school_level TEXT, grade_low TEXT, grade_high TEXT,
  status TEXT, open_date TEXT, closed_date TEXT,
  charter TEXT CHECK (charter IN ('Y','N')), charter_num TEXT, charter_funding_type TEXT,
  magnet  TEXT CHECK (magnet  IN ('Y','N')),
  virtual TEXT,                                    -- N/C/V/F as published
  street TEXT, city TEXT, zip TEXT, locale TEXT, website TEXT,
  lat REAL, lng REAL,                              -- from CDE, overwritten by ingest
  lat_override REAL, lng_override REAL,            -- hand corrections, ingest never writes these
  first_year TEXT NOT NULL, last_year TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS school_years (          -- snapshot per academic year
  cds_code TEXT NOT NULL REFERENCES schools(cds_code),
  academic_year TEXT NOT NULL,
  enroll_total INTEGER,
  -- <group> INTEGER nullable + <group>_pct REAL, grade_tk…grade_12, staff_* : generated from CDE_COLUMNS
  title_i TEXT CHECK (title_i IN ('Y','N')), dass TEXT CHECK (dass IN ('Y','N')), essa_status TEXT,
  PRIMARY KEY (cds_code, academic_year)
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
```

Design decisions and why:

1. **`CDE_COLUMNS` defines the ~95 CDE columns once.** A list of `(csv_header, column, sql_type, table)` in `db.py` generates the DDL and drives ingest, so schema and loader cannot drift.
2. **Hand-corrected coordinates live in `lat_override`/`lng_override`.** Ingest never writes them; readers use `COALESCE(lat_override, lat)`. A `COALESCE` inside the upsert only protects against a NULL incoming value; a wrong-but-present CDE coordinate would still overwrite a correction.
3. **Identity upsert is guarded by year.** `ON CONFLICT(cds_code) DO UPDATE … WHERE excluded.last_year >= schools.last_year`; `first_year`/`last_year` widen with `MIN`/`MAX` regardless. Loading an older file later cannot roll a name back.
4. **Snapshot upsert replaces every column** on `(cds_code, academic_year)`. `INSERT OR REPLACE` is never used: it deletes the row, wiping override columns and tripping foreign keys.
5. **`commutes` is keyed by home.** A new home simply has no rows yet; an old home's rows are never served for it.
6. **A cached commute is fresh only if it is young enough and from a provider at least as good as the configured one** (`estimate < osrm`). Turning OSRM on upgrades the cache on the next run.
7. **The personal factor is applied at read time,** in the view, from `homes.factor_am` and `homes.factor_pm`. Cached rows stay as the model produced them, so correcting a factor needs no recomputation.
8. **Jobs link to a school or to a district.** For a district-wide job the view gives the shortest and longest cached commute among that district's in-range schools, and the card shows the range.
9. **No districts table.** `SELECT DISTINCT district_code, district_name, county_name FROM schools` is the list.
10. **No vendor SDK.** One function posts to an OpenAI-compatible `/chat/completions` URL from config; DeepSeek, Ollama and LM Studio all accept that format.

### Pipeline details

**Home.** `home "123 Main St, Fresno CA"` geocodes through the Census service; `home --zip 93721` uses the mean position of that ZIP's schools; `home 36.74,-119.79` takes coordinates. All three round to 3 decimals, check the California bounding box (lat 32.5–42.0, lng −124.5 to −114.1), insert a `homes` row and set it active in config. The address string is used for the one request and then discarded. If the geocoder finds nothing or is unreachable, the message offers the ZIP form.

**Ingest.** `--year 2025-26` (default), several years, or `--file`. Rename headers through a per-year alias map onto 2025-26 names; per row coerce (`''`, `*`, non-numeric → NULL; dates → ISO; strip whitespace), upsert identity, then snapshot (identity first because of the foreign key); one transaction per file. An unrecognized header raises, naming it. Dropped: `OBJECTID`, `x`, `y`, `State`, geographic and legislative district columns, the 2024-25 `*2`/`Locale Four` duplicates.

**Commute.** Straight-line miles in Python; keep schools within `radius_miles` (default 20); for those without a fresh row, nearest first:

- `osrm`: table requests in batches of 50 schools, one for home→schools and one for schools→home, at most one request per second, User-Agent `EdTrawl/<version>`. Result is free-flow road minutes.
- `estimate`: `minutes = a + b × straight_miles` per locale group (City, Suburban, Town, Rural, from the first digit of CDE `Locale`). Eight numbers at the top of `travel.py`, fitted by `calibrate.py` against OSRM. Until that has run they are my guesses and say so in a comment: City 4 + 2.0/mi, Suburban 4 + 1.8/mi, Town 3 + 1.6/mi, Rural 3 + 1.4/mi.
- Both are then multiplied by `rush(county, direction) = 1 + rush_scale[direction] × (TTI[county] − 1)`. `TTI` is the FHWA table in §2, mapped to counties (Los Angeles, Orange → 1.59; Santa Clara, San Benito → 1.45; San Francisco, Alameda, Contra Costa, San Mateo, Marin → 1.37; Riverside, San Bernardino → 1.27; San Diego → 1.25; Sacramento, Placer, El Dorado, Yolo → 1.17; Fresno → 1.07; every other county 1.10, which is a guess). `rush_scale` converts the published peak-period index into a teacher's actual hours and also absorbs how optimistic OSRM is on signalled streets. Values `am = 0.75`, `pm = 1.2`, in config, fitted to the owner's five observed drives below; before that data they were guesses of 0.6 and 0.8, and both were too low.

If the configured provider is unreachable the run stops and says so; it never writes an estimate under the OSRM label.

**The only traffic ground truth this build has** (owner's remembered drives from one Los Angeles County home to two schools, checked 2026-11-16 against both public OSRM servers, which agreed):

| Drive | Observed | OSRM free-flow | Observed ÷ OSRM | Model at 0.75 / 1.2 |
|---|---|---|---|---|
| School 1, morning, leaving about 7:00 | 29–31 min | 21.0 | 1.43 | 30 |
| School 2, morning, leaving 6:00–6:30 | 36 min | 24.8 | 1.45 | 36 |
| School 1, home at 3:00 pm | 36 min | 21.4 | 1.68 | 37 |
| School 2, home at 1:00–2:00 pm | 45 min | 25.8 | 1.74 | 44 |
| School 2, home at 4:15–4:45 pm | 56–59 min | 25.8 | 2.2 | 44 |
| School 2, home at 5:00 pm | 68+ min | 25.8 | 2.6 | 44 |

What this shows: the two mornings agree closely (1.43, 1.45). The afternoon is worse than the morning even at 1–3 pm, and on one route it grows by half between 2 pm and 5 pm. So the two directions need separate corrections, and one afternoon number cannot describe a route whose time depends this much on when you leave. The model is fitted on the same six numbers it is compared with here, from one home in one metro; treat it as tuned for Los Angeles and unproven elsewhere. The schools and the address are not recorded in this repository.

**Personal correction.** `drove "Roosevelt Middle" 34` (optionally `--pm`) records a drive the user knows at school-commute time. `homes.factor_am` and `homes.factor_pm` each become the median of known ÷ modelled minutes across that home's drives in that direction, clamped to 0.5–2.0. A direction with no known drive borrows the other direction's factor. Setup asks for one such drive and can be skipped.

**Calibration (developer step, no key).** Use schools as stand-in homes: 60 of them spread over the four locale groups and regions, each paired with about 10 schools within 20 miles. About 120 OSRM table requests. Fit each `(a, b)` with `statistics.linear_regression` on four-fifths of the pairs and report median and 90th-percentile error on the rest, per group, plus the three worst pairs. That report states how far the offline formula is from real road time. Neither tier has been measured against real traffic; the README says so, and says the personal correction is the remedy.

**Fetch.** Confirmed by the probe (2026-11-16, `RECON.md`): the listing endpoint and the detail page both answer anonymously, with no cookie and no special header. So there is no login, no browser automation and no stored session in this build. Per county in range: `regions=<county id>&jobTypes=<17 teacher ids>&days=<1|7|31>&rows=50&stateID=24`, all 19 parameters always sent, one request every 2 seconds, one at a time, hard page cap, stop on 403/429/5xx with no retry loop, upsert on `posting_id`. Dates arrive as `/Date(ms)/`; `displayUntil` is ignored unless `displayFlag` is `By Date`. Detail pages are fetched only for jobs whose matched district has a school in range and whose title did not already name a school. `--from-file` loads a saved response.

The listing has no school field. The site name comes from, in order: the title (`… @ Theodore Judah ELEM-114`, `… at Marvin Marshall`, `… (Carroll Elementary School)`), then the detail page's optional `Location(s):` block. The address in the detail page's JSON-LD is the district office in the saved example (it is the same street as the HR contacts), so it is not used for matching.

**Match.** Same three steps for the district string (candidates: districts and charter schools in the listing's county) and then the site (candidates: the matched district's schools). For the site, step 0 runs first: look for any of the district's normalized school names inside the normalized title and `Location(s)` text; exactly one hit, or one hit that contains all the others, is `exact`. A charter whose own name is the edjoin district name matches as a school directly. Then:
1. Exact after shared normalization → `exact`.
2. `difflib` score on normalized, token-sorted strings; accept the top candidate as `fuzzy` only if score ≥ `match_accept` (0.90) and lead over the runner-up ≥ `match_margin` (0.05).
3. If `[llm]` is configured and step 2 did not accept: send the raw string and the top 15 candidates; the answer must be one of those codes or null.
4. Otherwise `unsure`, with the top three kept for `match --review`.

**Search.** `job_search` joins `jobs` → `schools` (directly or via district) → latest `school_years` (and the year before, for the trend) → `commutes` and `homes` for the active home → `job_marks`. `query.search(...)` adds bound-parameter filters.

## 4. Experience design

This section is the brief for every agent that touches what the user sees. It is the part of the build most likely to be done badly by default, so it is specific.

### Who is using this and what they need

A teacher who needs a new job. They may be anxious, are probably doing this in the evening after work, are comfortable with email and spreadsheets and uncomfortable in a terminal. Job boards make this worse: endless lists, no sense of progress, no end. The tool's job is to make a hard task feel finite, clear and a little lighter. Treat them as the competent professional they are.

### The core loop

Every good game has a short loop the player repeats: act, get feedback, get something, see the next step. Ours:

```
cast (fetch what's new)  →  catch (look at each new job, one at a time)  →  keep or toss  →  done for today
```

The most important design decision in the whole product is the last step: **the session ends.** Job boards scroll forever, which reads as "you are never finished". Here the user reviews only what is new since last time, one card at a time with a count ("3 of 7"), and then sees "That's everything new." Finishing is the reward. They can close the laptop.

### Theme

The name gives it: a small trawler. Home port (home), casting the net (fetching), the catch (new jobs), keepers (shortlist), toss back (dismiss), logbook (history), chart (the map page). The metaphor carries labels and small moments. It never carries instructions or errors, which are plain. One themed touch per screen at most. Command names stay plain verbs.

### Principles, each with what it means here

1. **One thing to remember.** `python edtrawl.py` does the right thing: first time it runs setup, afterwards it runs the daily loop. Everything else is optional depth.
2. **Fast first reward.** Setup shows something true and encouraging before any job appears: "412 public schools in 37 districts are within 20 miles of you." Then the first catch. Measure the time from first command to first job card and report it; aim for under three minutes on the offline tier.
3. **Lead with what exists.** The headline is always the count of real options: "12 jobs within 30 minutes."
4. **No dead ends.** An empty result computes the nearest adjustment and its payoff from real data: "Nothing under 20 minutes today. 5 jobs open up at 25 minutes." Every error says what happened and what to type next.
5. **One decision at a time.** The triage deck shows a single card and asks keep, toss, skip, open, more, quit. A long table is available (`search`) but is not the default.
6. **Information is the reward.** The card answers what a teacher actually weighs: drive each way, hours per week, school size and whether enrollment is growing or shrinking, staff count, pay text, deadline.
7. **Translate numbers into life.** "~22 min there, ~26 home" also says "about 4 hours a week". Enrollment is "steady (+1% in a year)", not a bare number.
8. **Honest signals.** `~` on every modelled time. Real deadlines shown plainly ("closes Friday, 3 days"). No invented urgency, no scores.
9. **Progress without pressure.** The logbook shows what they have done ("this week: looked at 23, kept 5, applied to 2"). No streaks, no "you missed a day". After two weeks away: "Welcome back. 31 new since Oct 30."
10. **Their input visibly improves it.** Telling the tool one drive they know changes every estimate, and the tool shows the before and after once. People value what they have shaped.
11. **Small delight, rarely.** A one-line boat that moves while fetching (terminal only). A single warm line the first time they keep a job and the first time they mark one applied. Then it stays quiet; repeated praise turns into noise.

### Voice

A warm colleague in the staff room. Short sentences. Plain words. At most one exclamation mark per session.

| Situation | Write | Not |
|---|---|---|
| Starting a fetch | `Casting the net across 37 districts…` | `Initializing scrape job` / `Let's go fishing!!! 🎣🎣` |
| Nothing new | `Nothing new since yesterday. Your 3 keepers are still open.` | `0 results` |
| End of triage | `That's all 7. Kept 2, tossed 4, skipped 1. Net's empty until tomorrow.` | `Great job! You're crushing it!` |
| First application marked | `First one in the logbook. That's the hard part done.` | `🎉 ACHIEVEMENT UNLOCKED` |
| Geocoder found nothing | `I couldn't place that address. Try just the ZIP: python edtrawl.py home --zip 93721` | `Geocoding error: no addressMatches` |
| Routing server down | `The road-distance server isn't answering. Your saved commutes still work; I'll use them.` | `HTTPError 503` |
| Deadline tomorrow | `closes tomorrow` | `HURRY! Only 1 day left!` |

### What a card looks like (80 columns)

```
 ── 2 of 7 ───────────────────────────────────────────── closes Fri (3 days)
 Math Teacher, Grades 7–8
 Roosevelt Middle · Fresno Unified
 Drive   ~22 min there · ~26 home if you leave at 3:30   (about 4 hrs a week)
 School  612 students, steady (+1% in a year) · 24 teachers · Title I
 Pay     $58,400–$104,200
 [k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
```

The afternoon figure always names its departure time. `[m]ore` adds one line when the rush-hour factor is above 1.3: "Afternoon traffic here builds fast; leaving after 4 can add a third or more."

District-wide job: `Site not listed · Fresno Unified` and `Drive   ~12 to ~41 min across the district's 14 schools in range`.

### Things this product will not do

- **No judgement of schools.** Demographic figures are shown as facts on the "more" card and never combined into a score, a rank, a colour or an adjective. Sorting and filtering by demographics is not offered.
- **No manufactured urgency, guilt, streaks, nags or countdown language.**
- **No praise for nothing.** Encouragement is tied to something the user did, and is rare.
- **No baby talk.** The audience is professionals.
- **No hidden network use.** Setup says which services will be contacted and what they receive, and offers the offline path.

### Accessibility and robustness

Colour is never the only carrier of meaning. Honour `NO_COLOR` and `--plain`; turn colour and animation off when output is not a terminal; turn emoji off when the encoding is not UTF-8 and with `--no-emoji`; every icon has a word next to it. Fit 80 columns and degrade to 60. Cards are "label: value" lines, which a screen reader handles better than a wide table. Never wait for input when stdin is not a terminal: print the list instead. Prompts take a letter and Enter.

### The chart page

`python edtrawl.py chart` writes one HTML file and opens it. Self-contained: no CDN, no map tiles, no outside request, so opening it tells nobody anything. An inline SVG shows home in the centre, distance rings, every school in range as a dot, hiring schools emphasized and marked by commute band using shape and label as well as colour. Job cards below with filter chips and a keepers view. Light and dark. Keyboard reachable. It is read-only; keeping and tossing stay in the terminal.

### How we check it is actually pleasant

Game teams playtest. So do we (agents P1 and P2), against these gates:

- A first-time user needs exactly one command, and reaches a first job card; the time is measured and reported.
- Every empty state and every error names a next step.
- Every session reaches a "done" line.
- The friction log has no entry of the kind "I did not know what to do next".
- No message reads as cold, cute, or condescending to the playtester.

## 5. Build order

| Wave | Agents (parallel within a wave) | Gate |
|---|---|---|
| 0 | Lead: `git init`, `.gitignore`, `config.example.toml` | ignores cover `config.toml`, `.auth/`, `data/`, `*.db`, `*.html` output before anything else exists |
| 1 | **A** schema (Opus) ∥ **B** edjoin recon (Sonnet) ∥ **H1** fixtures (Haiku) | `python db.py` twice clean; recon says auth yes/no |
| 2 | **C** ingest (Sonnet) ∥ **D** travel (Sonnet) ∥ **E** edjoin fetch (Sonnet) ∥ **U1** voice and `ui.py` (Opus) | real load = 9,946 schools, idempotent; module tests pass offline |
| 3 | **F** matcher (Opus) ∥ **G** query + CLI plumbing (Sonnet) ∥ **D2** calibration (Sonnet) | untouched config: `ingest → commute → fetch → match → search` shows jobs |
| 4 | **U2** flows (Sonnet) | `python edtrawl.py` on an empty directory reaches a job card; time reported |
| 5 | **U3** chart (Sonnet) ∥ **H2** README (Haiku) | page opens with no network requests |
| 6 | **P1** cold playtest (Haiku) ∥ **P2** edge-state playtest (Sonnet), then fixes by the owning agents, then **R** review (Opus) | §4 gates met; review findings fixed or explicitly declined |

Lead session: Opus 5.5. It launches agents, runs every gate command itself, and is the only one to edit a file outside its owner's lane.

## 6. Rules for every agent

Paste these with each brief.

- Work only inside this directory. Do not read `../EdTrawl/` or `../claudeddb.py`.
- Read `PLAN.md` §1–§4 first. The schema is the contract; if it blocks you, stop and report, do not edit `db.py`.
- Edit only the files under "Owns".
- Standard library only unless the brief says otherwise. No abstraction for a single use.
- Logic modules do not print; they return data and call `on_progress` if given. All wording goes through `ui.py`.
- Text from edjoin and from any model is untrusted: bound parameters in SQL, `html.escape` in HTML, control characters stripped before the terminal, a delimited data block in any prompt.
- No key, cookie, token, street address or exact home coordinate in a tracked file, a log line, a test, or an exception message. Tests use the California State Capitol (38.577, −121.495) as home.
- No call to any commercial map or traffic API. §1 explains why.
- Where a choice was not obvious, leave a one-line comment saying why.
- Tests go in `test_<your module>.py` at the top level (one file per module, so parallel agents never edit the same file) and pass offline with `python -m unittest`.
- Final message: what you built, the exact commands you ran with their real output, what you could not verify, and any deviation from the plan.

## 7. Agent briefs

### A — Schema and contracts · Opus 5.5 · effort high

**Owns:** `db.py`, `config.py`, `config.example.toml`.

Build `db.py`: `connect(path="edtrawl.db")` (foreign keys on, `sqlite3.Row`), `CDE_COLUMNS`, `init_db(conn)`, and a `__main__` that initializes and prints table names. Complete the column lists from the real 2025-26 header. snake_case, `_pct` for percentages, counts INTEGER nullable, percentages REAL. Generate the two CDE tables from `CDE_COLUMNS`. Add the `job_search` view from §3 "Search" (it must expose the provider, the factor-adjusted AM and PM minutes, the min and max for district-wide jobs, enrollment this year and last, and the mark status) and indexes only for the joins that view makes.

`config.py`: `load()` returns a dataclass: `home_key=None`, `radius_miles=20`, `max_age_days=90`, `routing="estimate"` (`estimate|osrm`), `osrm_url="https://router.project-osrm.org"`, `rush_scale_am=0.75`, `rush_scale_pm=1.2`, `llm_base_url=None`, `llm_model=None`, `llm_key=None`, `match_accept=0.90`, `match_margin=0.05`. `set(key, value)` rewrites one line and leaves the rest of the file alone. A missing file is created from the example; nothing is required except a home, and the missing-home error is a `ui` message key, not a string here.

**Done when:** `python db.py` runs twice cleanly; tests assert all eight tables and the view exist, a 13-char `cds_code` fails, a snapshot for an unknown school fails, a `factor_am` of 3.0 fails, and a `job_marks.status` of `'maybe'` fails.

### B — edjoin recon · Sonnet 5.5 · effort medium

**Owns:** `tests/fixtures/edjoin_*`, `RECON.md` (short). The owner has approved this probe.
**Budget: at most 10 requests to edjoin.org, 2 seconds apart. No login, no form submission, no credentials.**

Answer with evidence:
1. Does `GET /Home/LoadJobs` with the full 19-parameter query string (defaults `rows=10, page=1, sort=postingDate, sortVal=0, order=desc, searchType=all, days=0, catID=0`, ids `0`, strings empty) return JSON without a session? Record status, content type, top-level keys.
2. Which parameters restrict to California teaching jobs, to a county or region, to a job type, and to "posted within N days"? Job-type ids are in the search page's inline JS.
3. Does `/Home/JobPosting/<id>` load without a session, and where is the school or site text? Give the markup.
4. Date formats of `postingDate` and `displayUntil`.

Save one listing response and one detail page as fixtures. If any step needs a session, stop and say which; do not try to get one.

### H1 — Data and fixtures · Haiku 5.5 · effort low

**Owns:** `data/` (gitignored), `tests/fixtures/cde_*.csv`.

1. Download the 2025-26 and 2024-25 CSVs to `data/schools_<year>.csv`.
2. Write `tests/fixtures/cde_2025-26.csv` and `cde_2024-25.csv`: the original header line byte for byte (keep the BOM), then about 20 real rows each including: a CDS code starting with `0`; a charter; a `Status=Closed` row; one row per `Virtual` code; from 2024-25 both blank-coordinate rows and a ZIP+4 row; at least 5 schools present in both files and 2 present in only one; at least 3 schools sharing one ZIP; at least 4 schools in Sacramento County within 10 miles of the Capitol.
3. Append one synthetic row to the 2025-26 fixture (name `SYNTHETIC SUPPRESSED`, CDS `99999999999999`) with `*` in two demographic count cells and blanks in their percentage cells.

**Done when:** you report the row counts of all four files and the CDS codes chosen for each case.

### C — CDE ingest · Sonnet 5.5 · effort medium

**Owns:** `ingest.py`.

`ingest(conn, csv_path, academic_year=None, on_progress=None)` and `download(year)` per §3 "Ingest" and decisions 2–4. Year comes from the file's `Academic Year` column. `HEADER_ALIASES` maps 2024-25 names to 2025-26 names. One `coerce(value, sql_type)` helper.

**Tests:** same file twice leaves identical rows; synthetic `*` cells are NULL; a leading-zero code round-trips at 14 chars; 2025-26 then 2024-25 keeps the 2025-26 name with `first_year='2024-25'`, `last_year='2025-26'`; `lat_override` survives re-ingest; 2024-25 rows have NULL staff columns; an unknown header raises and names it.

**Done when:** tests pass and the real 2025-26 file loads 9,946 schools and 9,946 snapshots, twice, with the same counts.

### D — Travel · Sonnet 5.5 · effort medium

**Owns:** `travel.py`.

Implement §3 "Home", "Commute" and "Personal correction":

- `geocode(address) -> (lat, lng) | None` against the Census endpoint in §2. `zip_centroid(conn, zip)`. `set_home(conn, cfg, lat, lng)` rounds, checks the bounding box, upserts `homes`, updates config.
- `haversine_miles`, `schools_in_radius(conn, cfg)`.
- `estimate(straight_miles, locale)` with the `COEFFS` table, guesses marked as unfitted.
- `osrm(home, schools, cfg)`: read the OSRM table-service documentation first; find the server's coordinate limit by reading or by one test and batch safely under it; one request per second; an honest User-Agent; `sources`/`destinations` so each batch costs two requests.
- `rush(county, direction, cfg)` with the `TTI` table from §3, the source and report period in a comment.
- `update_commutes(conn, cfg, on_progress=None)` with the freshness rule in decision 6.
- `record_drive(conn, cfg, cds_code, minutes, direction)` updating `known_drives` and `homes.factor_am` / `factor_pm`.

Each network call sits in one small function so tests replace it. A provider that fails stops the run with a typed exception the UI can word; it never falls through to a different provider silently. Coordinates sent to OSRM are the rounded home.

**Tests (no network):** haversine on a known pair; a school just outside the radius is excluded; estimate grows with distance and City exceeds Rural at equal distance; `rush` for Los Angeles AM is 1 + 0.75 × 0.59 and an unlisted county uses 1.10; fresh rows are skipped, stale rows recomputed; an `estimate` row is recomputed when routing is `osrm` and an `osrm` row is kept when routing is `estimate`; a new home recomputes; NULL coordinates are skipped and `lat_override` is used; `zip_centroid` returns the mean and an unknown ZIP raises; coordinates outside California are rejected; one known drive of 30 against a modelled 20 gives `factor_am` 1.5 and, with no afternoon drive, `factor_pm` 1.5 too; adding an afternoon drive changes only `factor_pm`; a ratio of 5 is clamped to 2.0; `geocode` parses the saved Capitol response and returns None for an empty match list.

**Done when:** tests pass; `commute` with default config fills the cache for the Capitol home with no network; one live OSRM run for the Capitol home succeeds and you report the count of schools, requests made and elapsed time.

### D2 — Calibration · Sonnet 5.5 · effort medium

**Owns:** `calibrate.py`, and the `COEFFS` table inside `travel.py` only.

Implement §3 "Calibration". Seeded sampling; raw pairs written to `data/calibration.csv` as they arrive so an interrupted run resumes; at most 150 OSRM requests, counted, one per second. Fit on four-fifths, report on the held-out fifth.

**Done when:** `COEFFS` holds fitted values with a comment giving date, sample size and "fitted against OpenStreetMap road times via OSRM; © OpenStreetMap contributors"; you report per locale group the median and 90th-percentile error in minutes and percent, the three worst pairs with a likely cause, and a plain statement of whether any group is too inaccurate to be useful.

### E — edjoin fetch · Sonnet 5.5 · effort medium

**Owns:** `edjoin.py`. Start after B.

Read `RECON.md` first; it has the exact query string, the county id table, the teacher job-type ids, the date formats and the paging rule. No login exists in this build.

`fetch_listings(county_ids, days=31, limit=None, on_progress=None)` pages `/Home/LoadJobs` with urllib, all 19 parameters, one request every 2 seconds, a hard page cap, and stops (typed exception, no retry loop) on 403, 429, 5xx or a non-JSON body. `save_listings(conn, rows)` upserts on `posting_id` and stores a `location_raw` guess taken from the title. `fetch_detail(posting_id)` and `parse_detail(html)` return the `Location(s):` text or None. `load_file(path)` feeds a saved response through `save_listings`. `county_ids_in_range(conn, cfg)` maps the counties of schools that have a commute row to edjoin county ids. Reject any posting URL that is not `https://www.edjoin.org/…`.

**Tests:** the listing fixture parses to the expected count and fields; saving twice leaves one row per posting, `first_seen` unchanged, `last_seen` updated; `parse_detail` returns the expected text; a malformed response raises; a non-edjoin URL is rejected.

**Done when:** tests pass and one live run with `--limit 20` loads 20 jobs.

### U1 — Voice and `ui.py` · Opus 5.5 · effort high

**Owns:** `ui.py`.
**Why Opus:** this is taste and restraint, and every other screen inherits it.

Build the presentation layer from §4. Read §4 twice; the "will not do" list is binding.

- Capability detection once: terminal or not, colour allowed (`NO_COLOR`, `--plain`), UTF-8, width. One accent colour.
- `COPY`: every user-facing sentence as a named template in one dict at the top of the file, grouped by screen. Other modules refer to keys. Write the full set now for: setup steps, the schools-in-range reveal, fetch/commute/match progress, triage prompts and end line, every empty state, every error named in the briefs, logbook lines, the two one-time warm lines, the welcome-back line, the network-use notice.
- Formatters (pure functions): `minutes(m, provider)` with `~`, `drive_line(am, pm)` including hours per week for 5 days, `range_line(min, max, n)`, `trend(now, before)` giving growing/steady/shrinking with the percentage and nothing when a year is missing, `deadline(date, today)`, `count(n, noun)`.
- Renderers: `job_card(row, i, n)`, `school_card(row)` (facts only, no adjectives about demographics), `table(rows)`, `progress(done, total, label)` with the boat only on a terminal, `ask(key, choices)` that returns a default without blocking when stdin is not a terminal.
- `clean(text)` strips control characters from untrusted text; every renderer uses it.

Before finishing, print every `COPY` entry and read them as a tired teacher at 9 pm would. Cut anything cute twice in a row, anything that explains the metaphor, anything a professional would find patronizing.

**Tests:** each formatter on normal, missing and edge values (0 minutes, NULL, a deadline today, a deadline passed); `job_card` fits 80 columns for a 120-character title and degrades at 60; plain mode output contains no escape sequences and no emoji; `clean` removes an embedded `\x1b[2J`; `ask` returns the default with stdin not a terminal.

### F — Matcher · Opus 5.5 · effort high

**Owns:** `match.py`.

Implement §3 "Match":

- `normalize(text)` and `rank(raw, candidates)` with `difflib`. Build the abbreviation list from real data: print the 50 most common tokens in CDE names and in real listing strings first.
- `decide(ranked, accept, margin)`.
- `pick(raw_text, candidates, cfg) -> code | None`, the only function that talks to a model: one `urllib` POST to `{llm_base_url}/chat/completions` asking for `{"code": …}`. Read Ollama's and DeepSeek's current documentation for the OpenAI-compatible request and JSON-output option and keep everything vendor-specific in config. Listing text goes in a delimited data block; the answer is accepted only if it is in the candidate list. Timeout, non-200 or unparseable JSON means no answer and nothing cached.
- `match_jobs(conn, cfg, limit=None, on_progress=None)` returns counts; consults `name_matches` first; `manual` always wins; `unsure` is retried once an LLM is configured. `review(conn)` returns unsure strings with their top three.

Tune `accept` and `margin` on 100 real listing strings so that what the coded tier accepts is right; prefer unsure over a wrong school; report the share accepted.

**Tests (`pick` replaced):** exact match makes no further call; "Lincoln Elem" matches "Lincoln Elementary" in the coded tier; "Lincoln School" against "Lincoln Elementary"/"Lincoln Middle" is unsure with no LLM; with an LLM it calls `pick` with at most 15 candidates; an answer outside the list is stored unsure; cached pairs make no call; `manual` is not overwritten; a failed call is not cached.
**Live checks:** the coded tier on 100 real listings, always. The LLM tier only if a local model or a key is present in config; otherwise say it was not exercised. Report as tables and as "N of M looked right to me".

### G — Query and CLI plumbing · Sonnet 5.5 · effort medium

**Owns:** `query.py`, `edtrawl.py` (handed to U2 after wave 3).

`query.search(conn, cfg, *, max_commute=None, posted_within=None, level=None, charter=None, min_enrollment=None, title_i=None, status=None, new_only=False, limit=50)` over the view with bound parameters; `max_commute` uses the larger of AM and PM after the personal factor; jobs with no commute are excluded when `max_commute` is given. `nearly(conn, cfg, **same_filters)` returns the smallest relaxation of `max_commute` that adds jobs and how many, for the empty state. `edtrawl.py`: subcommands `home`, `ingest`, `commute`, `fetch`, `match` (`--review`), `search`, each a thin call that passes results to `ui`, plus `--db`, `--plain`, `--no-emoji`.

**Tests:** a hand-built database (2 schools, 2 snapshot years each, commutes, a home with `factor_am` 1.2 and `factor_pm` 1.5, jobs: school-matched, district-only, unmatched, one kept, one tossed) and assertions that each filter includes and excludes correctly, the latest year is joined and the prior year is available, each factor is applied to its own direction, a district-only job reports min and max, `new_only` hides marked jobs, and `nearly` returns the right step.

### U2 — Flows · Sonnet 5.5 · effort medium

**Owns:** `flows.py`, `edtrawl.py` (from G). Reads `ui.py`; requests new `COPY` keys from the lead instead of writing strings inline.

- `setup`: numbered steps with "step 2 of 4". Home (address, ZIP or coordinates, with the network-use notice before the geocoder is called) → load schools → the schools-in-range reveal → choose road distances (OSRM, saying what is sent) or stay offline → optional known drive → first cast. Re-runnable; each step skips itself if done.
- `go`: fetch → match → commute for anything new → triage. Bare `python edtrawl.py` runs `setup` if there is no home, else `go`.
- Triage deck: new unmarked jobs in range, nearest first, jobs closing within three days flagged. Keys: keep, toss, skip, open (stdlib `webbrowser`), more (school card), quit. Ends with the summary line. With stdin not a terminal, print the list and exit.
- `school <name or CDS>`, `keepers` (with deadlines, soonest first), `applied <posting>`, `logbook`, `drove <school> <minutes> [--pm]` showing one before-and-after line.
- The two one-time warm lines fire once each, tracked by whether a kept or applied mark already exists.

**Tests:** scripted stdin through setup with the geocoder and network replaced; `go` on a prepared database marks keep and toss correctly and prints the end line; quitting midway leaves the rest unmarked; a non-terminal stdin never blocks; the empty state prints the `nearly` suggestion; the first-keep line appears once across two sessions.

**Done when:** tests pass, and on an empty directory `python edtrawl.py` driven by scripted answers reaches a job card. Report the wall-clock time for that run.

### U3 — Chart page · Sonnet 5.5 · effort medium

**Owns:** `chart.py`. Load the `frontend-design` skill before designing.

`write_chart(conn, cfg, path="edtrawl-chart.html")` per §4 "The chart page". One file, inline CSS and JS, no external URL of any kind except links to edjoin postings and school websites. Projection: plain equirectangular around home with longitude scaled by `cos(latitude)`. Every string from the database goes through `html.escape`; data for the script is embedded with `json.dumps` and `</` escaped; links are emitted only for `https://` URLs. Attribution line for OpenStreetMap when commutes came from OSRM.

**Tests:** a job title containing `<script>alert(1)</script>` appears escaped; the output contains no `http://` or `https://` reference other than edjoin and school links; the file is produced with zero jobs and shows the empty state.
**Done when:** tests pass and you have opened the page in a browser with network disabled, at desktop and phone widths, in light and dark, and attached two screenshots.

### H2 — README · Haiku 5.5 · effort low

**Owns:** `README.md`.

Write for a teacher who is not a programmer, from the code as it exists. Order: what it does in three sentences; install Python and run the one command; what each setup question means; the daily routine; the other commands with one example each; what `~` means and how accurate it is (use D2's figures; say plainly it has not been measured against live traffic and that `drove` is the fix); who is contacted over the network and what they receive, and how to stay offline; how to add a local model; how to correct a school's location or a wrong match; credits (California Department of Education, OpenStreetMap contributors and OSRM, US Census Bureau, FHWA); limits from §9. Run every command you document and paste nothing you did not run.

### P1 — Cold playtest · Haiku 5.5 · effort low

**Owns:** `PLAYTEST.md` (your section).
**Why Haiku:** a reader who follows instructions literally finds unclear instructions.

You are a middle-school science teacher who has used a terminal only by copy and paste. You may read `README.md` and what the program prints. You may not read source code or `PLAN.md`. In a fresh copy of the project, follow the README from the top using the Capitol address `1315 10th St, Sacramento, CA 95814`. Write a friction log as you go: every moment you were unsure what to do, every word you did not understand, every message that felt cold, cute or talked down to you, how long each step took, and where you would have given up. End with the three changes that would have helped most. Do not fix anything.

### P2 — Edge-state playtest · Sonnet 5.5 · effort medium

**Owns:** `PLAYTEST.md` (your section).

Try to find the unkind moments. Run each of these and record exactly what the user sees and whether it names a next step: network unplugged at each setup step; a rural home with no jobs in range; a home outside California; a mistyped address; an unknown ZIP; `go` twice in a row; returning after the database is two weeks old; a 60-column terminal; `NO_COLOR=1`; output piped to a file; a listing whose title contains terminal escape codes; `drove` with 0 and with 500 minutes; quitting triage on the first card. Then check §4's "will not do" list against every string in `ui.COPY` and report violations with the key name.

### R — Review · Opus 5.5 · effort high

**Owns:** nothing; reports findings.

Check each line of the 04 spec's requirements, constraints and deliverables: met, partly met, not met, or deliberately changed (§8), with `file:line`. Then look for: any path where re-ingest changes a hand correction; SQL built by string formatting; a secret, address or exact coordinate that can reach git, a log or an exception; any place a model's answer steers control flow beyond a checked lookup; untrusted text reaching HTML or the terminal unescaped; request loops without a cap and a delay; any call to a commercial map API; a failed provider writing under another provider's label; an estimate shown without `~`; code that exists for a need neither the spec nor this plan states. Run the tests and say what they do not cover.

## 8. Deliberate departures from the 04 spec

| Spec says | This build does | Reason |
|---|---|---|
| Traffic-aware drive time from a provider with departure/arrival time | Open road routing × a public rush-hour index × a personal correction | §1: the terms of the free commercial option forbid the cache the spec also requires |
| An LLM call fuzzy-matches each listing | Exact and coded matching first; LLM only for the leftovers and only if configured | owner's instruction that it must work without an API |
| edjoin "requires user authentication to search"; handle it | No authentication at all | the probe (`RECON.md`) found the site's own search endpoint and the posting pages answer anonymous requests; the simplest handling of a login is not needing one |
| Arrive 7:00, leave 3:30 as inputs to the provider | They are labels on a fixed rush-hour factor per county and direction | no open data source takes a departure time; the card says "if you leave at 3:30" so the assumption is visible |
| Criteria-based filtering of results (location, position type) | Fetch is filtered by county and a fixed list of 17 teacher job types; search filters by commute, posting age, level, charter, enrollment, Title I and mark. There is no user filter by position type | the listing's job type is stored (`jobs.category`) but nothing filters on it yet |
| An LLM call for the leftovers | Leftovers scoring under 0.75 never reach the model; they are recorded as `none` | an employer with nothing close in the state file (a prison, a private school) is not a fuzzy-matching question |
| Four tables | Eight | homes, known drives, match cache and the user's marks each hold a different kind of fact |
| Query interface | Kept as `search`, plus a guided daily flow and an HTML page | owner's request for a cheerful, engaging experience |

Kept exactly: CDS as 14-char TEXT; nullable INTEGER counts and REAL percentages; Y/N as TEXT; gitignored credentials; LLM as a tool, never the orchestrator; 90-day configurable cache; `python db.py`; idempotent multi-year ingest.

## 9. Known limits

- Commute times are modelled, not observed traffic. The rush-hour table has seven metro figures and a guessed default for every other county, and the two `rush_scale` values are fitted to six observations from one Los Angeles County home. The afternoon figure describes leaving at about 3:30; the owner's data shows the same route taking 45 minutes at 2 pm and 68 at 5 pm, so the card says "leaving 3:30" and that later is slower. A known drive corrects the level for a home and direction; it cannot correct a single unusually bad corridor.
- The offline formula cannot see water or mountains. OSRM can.
- A ZIP-code home is off by up to a couple of miles.
- A district-wide job's commute is a range, because the site is unknown.
- A small local model will pick wrong more often than a hosted one. The list check stops invented answers, not wrong ones.
- The free OSRM servers promise nothing about uptime. Cached commutes keep working; `osrm_url` can point at a self-hosted server.
- The chart page is read-only.
- 2023-24 is not mapped; trends use two years.

## 10. Proposals not in this build

Each is real value but not needed for the first version; say the word and I will plan it.

1. **A local interactive page** (keep and toss with a click) served from `127.0.0.1`. The biggest step toward teachers who will never open a terminal.
2. **Deadlines to calendar:** `keepers --ics` writes a file any calendar app imports.
3. **Self-hosted routing in one command** (OSRM in Docker with the California extract) for heavy use or full privacy.
4. **Hourly rush-hour profile from Caltrans PeMS** (free account) to replace the two `rush_scale` values, fitted on one home, with measured ones.
5. **Credential and subject matching** from the posting text, so the deck shows only jobs the teacher is authorized for.
6. **A double-click launcher** so nobody has to type `python`.

## 11. What I need from the owner

Nothing blocks waves 0–5.

1. ~~The test address.~~ Received 2026-11-16. The Census geocoder matched it on the first try. It is in the session only, not in this repository.
2. ~~Known drives.~~ Received 2026-11-16: six observations to two schools, used in §3 Commute. The lead enters them with `drove` in the local (gitignored) database for the final check.
3. Optional: Ollama installed with any small model, to exercise the LLM tier for free. Without it that tier ships tested only against a stand-in.
4. Allow Agent B's requests to edjoin when the permission prompt appears.

## 12. As built: where the code differs from the sections above

Written after the final review (2026-11-16). The sections above are the plan as it stood before each wave; the code, `README.md` and `RECON.md` are current.

- **§2:** the anonymous edjoin call is confirmed (`RECON.md`).
- **§3 files:** tests are one `test_<module>.py` per module, not one file. `flows.py` and `chart.py` exist as planned; `playtest/` holds the two playtest logs.
- **§3 schema:** `schools` gained `geo_county_name` (89 schools are administered from a county they do not sit in). `name_matches.method` gained `none`. `homes.factor` became `factor_am` and `factor_pm`.
- **§3 commute:** `COEFFS` are fitted (`calibrate.py --report`). The personal factors are refitted whenever modelled minutes change, not only when a drive is recorded. A failed switch to road routing restores an all-offline cache.
- **§3 fetch:** counties are the physical county of every school in range plus the administrative county of non-charter schools. Rows downloaded before a failure are saved. If edjoin refuses partway, the session still deals the saved jobs.
- **§3 match:** before ranking, the district's school names are searched for inside the title and site text (not cached, because it costs nothing). Schools named by surname match when the level word agrees and only one school in the district fits. Names with a grade span match without it. A charter network is never matched to one of its schools unless the title names it in full. Scores under 0.75 are `none`.
- **§4 deck:** dealt ten cards at a time with a stop after each hand; a `[b]ack` key; only a single letter or the whole word is accepted; end of input stops honestly. Zero exclamation marks, not one.
- **§4 card:** the afternoon figure reads "if you leave at 3:30".
- **§7 commands added:** `keep`, `toss`, `radius`, `routing`. `setup` on a finished home does not fetch.
- **§9 additions:** there is no command to write a coordinate correction (the columns exist and survive re-ingest). Dates use the machine's local day, so a computer not on Pacific time can show a deadline as closed a few hours early. The model tier has never run against a real model.
- **§11:** the owner's drives were compared with the real code in a scratch database (§3 Commute table). They are not stored anywhere in this repository.

