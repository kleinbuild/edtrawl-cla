# EdTrawl

## 1. What it does

EdTrawl helps California teachers find teaching jobs within driving distance of home, using the state's public school list and the job postings on edjoin.org. It estimates the drive to each school, both ways, with typical rush-hour traffic added. Each day it shows you only the jobs that are new since last time, one at a time, and you keep, toss or skip each one.

## 2. What you need

You need Python 3.11 or newer (it was built and tested on 3.12). You do not need to install anything else. You do not need an account or a key.

To open a terminal:

- **Windows:** press the Windows key, type `PowerShell`, and press Enter.
- **Mac:** press Command and Space, type `Terminal`, and press Enter.
- **Linux:** open the applications menu and search for `Terminal`.

In the terminal, go to the EdTrawl folder. EdTrawl saves its files in the folder you run it from, so always run it from the same folder. Then type this one command and press Enter:

```
python edtrawl.py
```

If the terminal says `python` is not found, type `python3` instead:

```
python3 edtrawl.py
```

The first time you run it, EdTrawl asks a few questions. Every later time it goes straight to today's jobs.

## 3. The first run

The first run is setup. It asks four short questions and you can change any answer later. Here is how the recorded first run began:

```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you each new
one once, so you can keep it or toss it. Setup is four short steps, and you can change
any answer later.
9,946 schools loaded from the California Department of Education, 2025-26.
9,982 schools loaded from the California Department of Education, 2024-25.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
```

The progress bars are left out here. The school counts come from the state's school file.

**Step 1 of 4, home.** Give one of three things:

- A street address. EdTrawl sends the address once to the US Census Bureau's free geocoder to find the spot. It asks first. It never saves the address.
- A ZIP code. No internet is needed. Home is placed at the middle of that ZIP code's schools, so drive times are a little rougher.
- A map position, typed as two numbers with a comma between them, for example `36.74,-119.79`.

**Step 2 of 4, schools near you.** EdTrawl asks how far to look, in miles, as the crow flies. Press Enter for the default of 20. It then tells you how many public schools and districts are in that range, and the nearest school. In the recorded run:

```
Within 20 miles of home, as the crow flies: 472 public schools in 25 districts.
The nearest is William Land Elementary, about 0.7 miles away.
```

**Step 3 of 4, drive times.** EdTrawl asks how to work out drive times. Type `o` or `r` and press Enter.

- `o` is offline. A formula works out each drive from the straight-line distance. Nothing leaves your computer. It cannot see bays, mountains or freeways.
- `r` is roads. EdTrawl asks a free routing server for real road distances. It sends your home spot, rounded to about 100 metres, and the positions of nearby schools. Nothing else. You can switch to offline later in `config.toml`.

Both add typical rush-hour traffic. Both are estimates. The recorded run chose roads and showed this line when it finished:

```
Drive times are ready for 472 schools.
Road distances: © OpenStreetMap contributors, routed by OSRM.
```

**Step 4 of 4, one drive you know.** Type the name of a school you drive to now, or used to. Then type your real morning drive time in minutes. EdTrawl adjusts its estimates to match your roads. You can press Enter to skip this step and come back to it later with `drove`, which is described in section 5.

The first run took about 95 seconds in the recorded run. Most of that time went to two steps:

- Drive times took about 35 seconds. The road server answers one request a second, and EdTrawl asks in batches.
- Job listings, matching and reading job pages took about 57 seconds. EdTrawl asks edjoin.org for one page at a time, with two seconds between requests, so it does not overload the site.

The school files are saved in the `data` folder after the first download. If they are not there yet, the first run downloads them first. The two files are about 11 MB together.

When setup finishes, it shows the first jobs straight away.

## 4. The daily routine

Each day, run the same command:

```
python edtrawl.py
```

EdTrawl does three things. It looks for new jobs. It works out drive times for any new school. Then it shows you each new job once. Here is one real job card from the recorded run:

```
 ── 2 of 58 ─────────────────────────────────────────────── closes Thu (3 days)
 Teacher, Special Education, Preschool SDC MMLE @ Washington ELEM-113
 Washington Elementary · Sacramento City Unified
 Drive   ~4 min there · ~5 home if you leave by 3:30   (about 50 min a week)
 School  362 students, shrinking (-4% in a year) · 19 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
```

What each line means:

- **`2 of 58`** is the card number, out of the new jobs for today.
- **`closes Thu (3 days)`** is the application deadline. A card with no deadline has no closing text.
- **The job title** comes from the posting. The school name is in it when the employer wrote one.
- **The school and district** are the place the job is at.
- **`Drive`** is the drive time to the school, to work and back home. The `~` sign means the time is an estimate. EdTrawl puts `~` on every drive time it works out. It never presents one as a measured time.
- **`if you leave by 3:30`** is the assumption behind the drive home. The afternoon drive is worked out for leaving at 3:30. Leaving later is usually slower.
- **`about 50 min a week`** is the drive time each week for five working days, morning and afternoon together.
- **`School`** is the enrollment this year, and whether it is growing, steady or shrinking compared with a year before. Then the staff count and any special program the state lists, such as Title I.
- **`Pay`** is the pay text from the posting. `not listed` means the posting does not say.

The keys at the bottom work like this. Type the letter and press Enter.

- `k` keeps the job. It waits in your keepers list until you apply or toss it.
- `t` tosses it. It will not come back.
- `s` skips it for now. It comes up again next time.
- `o` opens the posting in your web browser.
- `m` shows facts about the school, such as grades, enrollment, staff and student groups.
- `q` stops here. The jobs you have not seen stay for next time.

When you have seen every new job, EdTrawl says so and stops. The session ends there. You can close the terminal.

## 5. The other commands

Run each command from the EdTrawl folder. Replace the example with your own value.

**`keepers`** shows the jobs you kept, soonest deadline first. Use it to see what is still open.

```
python edtrawl.py keepers
```

```
Keepers: 1 job, soonest deadline first
 Number   Drive    Closes   Job
 2293501  ~4-24    Nov 29   Augmentative and Alternative Communication Speci...
When you apply for one, note it by its number:
    python edtrawl.py applied 2293501
```

**`applied`** notes that you applied. Use the number from `keepers`. The job then leaves your keepers list and goes to the logbook, and `search --status applied` shows it. If it was your last keeper, `keepers` says there are none. The first time you do this, EdTrawl says so.

```
python edtrawl.py applied 2293501
```

```
Marked as applied: Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1.
First one in the logbook. That's the hard part done.
```

**`logbook`** shows what you have looked at, kept and applied for. Use it to see your own progress.

```
python edtrawl.py logbook
```

```
Logbook
This week: looked at 2, kept 1, applied to 0.
Since Nov 16: looked at 2, kept 1, applied to 0.
Nov 16  kept     Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1 · Sacramento City Unified School District
```

The output is shortened here. The logbook shows the last ten marks.

**`school`** shows the facts about one school: grades, enrollment, staff, student groups, ethnicity figures, drive times and website. Use it before you apply. Type part of the name. If more than one school matches, EdTrawl lists them. Then use the school's 14-digit code, which the program also accepts. This example uses a code from the recorded data:

```
python edtrawl.py school 34674390133777
```

```
 ── Washington Elementary ─────────────────────────────────────────────────────
 Sacramento City Unified · Sacramento · Sacramento County
 Grades    K–6 · Elementary · Title I
 Students  362, shrinking (-4% in a year)
 Staff     19 teachers · 33 staff in all
 Drive     ~4 min there · ~5 home if you leave by 3:30   (about 50 min a week)
 Website   http://washington.scusd.edu/
 Drive times assume arriving by 7:00 and leaving at 3:30 on a weekday. Later
 in the afternoon is usually slower.
 School figures: California Department of Education, 2025-26.
```

The output is shortened here. The student group and ethnicity lines are also shown.

**`drove`** tells EdTrawl a drive you know, so it can adjust its estimates. Give the school and your door-to-door minutes. Add `--pm` for the drive home in the afternoon. It shows one before-and-after line.

The examples below use the school code from the `school` example above. The output is from a scratch copy of the recorded data.

```
python edtrawl.py drove 34674390133777 6
```

```
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~23 to ~32 min.
```

```
python edtrawl.py drove 34674390133777 9 --pm
```

```
Thanks. I've scaled every afternoon estimate to match: the typical school near
you went from ~35 to ~43 min.
```

Use `drove` whenever an estimate looks wrong. One real drive fixes every estimate for that direction.

**`search`** lists jobs in a table, nearest first. Use filters to narrow it. These examples use two or three filters each.

```
python edtrawl.py search --max-commute 15 --level elementary
```

```
2 jobs, nearest drive first.
 Number   Drive    Closes   Job
 2295139  ~5       Nov 19   Teacher, Special Education, Preschool SDC MMLE @...
 2295141  ~11      Nov 19   Teacher, Elementary, 3rd Grade @ Theodore Judah...
```

```
python edtrawl.py search --posted-within 7 --charter no --title-i yes --new
```

```
5 jobs, nearest drive first.
 Number   Drive    Closes   Job
 2294284  ~15      Nov 17   Teacher, Elementary, 6th Grade @ Nicholas ELEM-2...
 2295164  ~17      Nov 19   Teacher, Resource, Special Education @ Will C. W...
```

The output is shortened here. The list shows two of the five jobs.

The useful filters are `--max-commute` (minutes, the slower direction), `--posted-within` (days), `--level` (elementary, middle or high), `--charter` (yes or no), `--min-enrollment`, `--title-i` (yes or no), `--status` (kept, tossed or applied), `--new` (only jobs you have not marked) and `--limit`. Run `python edtrawl.py search --help` to see them all.

**`match --review`** lists the job postings EdTrawl could not place at a school or district with confidence. It shows the closest names it found, with a score where 1.00 is an exact match. On a terminal, it lets you pick the right name. Use it when a job is missing from your list.

```
python edtrawl.py match --review
```

```
3 listings set aside. Under each are the closest names I found; 1.00 would be
identical.
OPTIONS FOR YOUTH  (2 jobs)
    34674473430691  Options for Youth-San Juan  0.79
    34103480136275  Fortune  0.42
    34765056033336  Smythe Academy of Arts and Sciences  0.38
```

The output is shortened here.

**`home`** sets or changes home. Use a ZIP code if you do not want to send an address anywhere:

```
python edtrawl.py home --zip 93721
```

To use a street address instead, put it in quotes:

```
python edtrawl.py home "123 Main St, Fresno"
```

**`setup`** runs the setup steps again. It skips any step that is already done, so on a home that is set up it does little. To change the home, use `home`. To switch between roads and offline, or change the search radius, edit `routing` or `radius_miles` in `config.toml`.

```
python edtrawl.py setup
```

**`chart`** writes one web page file, `edtrawl-chart.html`, next to your database and opens it in your browser. It shows a map with home in the centre, distance rings, every school in range as a small dot, and the schools that are hiring marked by drive time. Your jobs are listed beside it, and you can filter them by drive time, by kept jobs, or by jobs closing soon. The page is one file with nothing loaded from the internet, so opening it contacts no website. It only shows; keeping and tossing still happen in the terminal. It shows where home is relative to nearby schools, so keep the file to yourself.

```
python edtrawl.py chart
```

## 6. How accurate the drive times are

Every drive time is an estimate. None of them is live traffic. EdTrawl has two ways to estimate:

- **Offline.** A formula takes the straight-line distance to each school and turns it into minutes. The formula depends on the kind of area the school is in: city, suburban, town or rural. The formula was fitted to road times, using the free OpenStreetMap road data and the OSRM routing software. It cannot see bays, mountains or freeways.
- **Roads.** EdTrawl asks the free OSRM routing server for the time along a real road route, with no traffic in it. The server uses OpenStreetMap road data.

Then EdTrawl adds rush-hour traffic. It uses the Urban Congestion Report from the US Federal Highway Administration, July to September 2026. That report gives a travel-time index for seven California metro areas. Counties outside those areas get a default value. The index is the peak-period time divided by the free-flow time. For example, Los Angeles and Orange counties have an index of 1.59, and Fresno has 1.07. Other counties use a default of 1.10, which is a guess. The rush-hour factor is worked out from the index. Two settings scale it, one for mornings and one for afternoons. The morning setting is 0.75 and the afternoon setting is 1.2. These two settings were fitted to a small set of drives. See below.

How close is the offline formula to road time? The table below comes from `python3 calibrate.py --report`. It compares the formula with the free-flow road time. The rush-hour factor is not in this comparison. It uses 539 pairs of schools that were not used to fit the formula.

| Kind of area | Typical error (median) | Error that 9 in 10 are within (90th percentile) |
|---|---|---|
| City | 1.2 min (10%) | 5.1 min (28%) |
| Suburban | 2.3 min (10%) | 6.8 min (26%) |
| Town | 6.8 min (20%) | 14.0 min (42%) |
| Rural | 3.6 min (15%) | 15.2 min (47%) |
| All areas together | 2.4 min (13%) | 8.8 min (37%) |

The error is the size of the difference between the formula and the road time, in minutes and as a share of the road time. Town and rural areas are the least accurate. In mountain country the formula can be badly wrong. For example, one pair of schools in Tuolumne County is 15.6 straight miles apart. The road time was 79.5 minutes and the formula said 34.5.

Some things are not known:

- Neither the formula nor the road times have been checked against live traffic.
- The two rush-hour settings were fitted to six drives that one person remembered. Those drives went from one home in Los Angeles County to two schools. The same road server was used to check them. The rush-hour values may not fit other areas.
- The afternoon time assumes you leave at about 3:30. Later in the afternoon the same drive takes longer. In that person's remembered drives, one route took 45 minutes at 2 pm and 68 minutes at 5 pm.
- The free road servers make no promise about uptime.

The remedy is `drove`. One drive you know, typed in, fits the estimates for your home and your direction. It is the best way to make the numbers match your own roads.

## 7. Privacy and the network

EdTrawl contacts only the services below, and only for the reasons listed. Nothing else leaves your computer.

- **data.ca.gov** (the California state data site). EdTrawl downloads the school files, once. It sends a plain file request and no information about you. It only does this when the file is not already in the `data` folder.
- **The US Census Bureau geocoder.** Only if you give a street address. It receives that address once, and nothing else. It asks first.
- **The OSRM routing server** (`router.project-osrm.org`, which uses OpenStreetMap road data). Only if you choose roads. It receives your home spot, rounded to about 100 metres, and the positions of schools near you. It receives nothing else.
- **edjoin.org** (the job board). EdTrawl asks for teaching jobs by county and job type, a few seconds apart. It also reads a job's own page, for up to 40 jobs each time, when the school name is not in the title. Your home is not sent. The job numbers are sent as part of the web address.
- **An AI model.** Only if you set one up. See section 8. For a job it cannot match by name, it receives a short piece of the job's employer text and up to 15 school names as candidates. If the model runs on your own computer, that text stays there.

Stored on your computer:

- `edtrawl.db` holds the schools, the drive times, the job postings, your keep, toss and applied marks, and your home spot.
- `config.toml` holds your settings and your home spot. If you add a key for an AI model, it goes here too.
- The `data` folder holds the school files from the state.
- `edtrawl-error.log` is written only when something unexpected goes wrong. It records the kind of error and where it happened. It does not record addresses.

Your street address is never saved. EdTrawl keeps only the home spot, rounded to about 100 metres. Anyone who can read your files can see roughly where home is. Keep those files private.

To use the least network:

- Set up with a ZIP code, not a street address. The address question is never asked. The school file download still happens once if the file is missing.
- Choose offline for drive times. Nothing leaves your computer for drive times.
- Skip the AI model.

Job listings still come from edjoin.org. That is the only network use left.

## 8. Optional: an AI model for matching

Matching a job posting to a school works without an AI model. EdTrawl matches names exactly first, then matches close spellings. An AI model only helps with the postings that are left over. It is optional, and you do not need one.

To use a model on your own computer through Ollama, open `config.toml` in a text editor. Remove the `#` at the start of these three lines and set the values you want. The example from `config.example.toml` is:

```
llm_base_url = "http://localhost:11434/v1"
llm_model = "llama3.2"
# llm_key = ""
```

`llm_base_url` is the web address of the model service. `llm_model` is the name of the model. Leave `llm_key` out unless the service asks for a key. The model must already be installed in Ollama.

This part has been tested only against a stand-in, not a real model. A small local model will pick the wrong school more often than a hosted one. EdTrawl checks that the answer is one of the candidate schools. It cannot check that the answer is the right one. If the model does not answer, matching carries on without it, and the postings it would have helped with go to the review list.

## 9. When something looks wrong

- **A job is missing.** Run `python edtrawl.py match --review`. It lists the postings EdTrawl set aside. On a terminal, you can pick the right name for each one.
- **A drive time looks off.** Run `python edtrawl.py drove` with the school and your real minutes, as in section 5. Add `--pm` for the drive home.
- **You want to start over.** Delete `edtrawl.db` and `config.toml` from the EdTrawl folder. The next run asks the setup questions again. The `data` folder can stay.
- **Something unexpected happened.** EdTrawl says so and names a file. The details are in `edtrawl-error.log`, in the same folder as `edtrawl.db`. The file does not record addresses, so you can send it to the person who maintains EdTrawl.

## 10. Limits

- Drive times are estimates. They are not live traffic.
- The offline formula cannot see water or mountains. The road servers can see them, but they still do not show traffic.
- A home placed by ZIP code can be off by a mile or two.
- A job at a district with no named school shows a range of drive times, because the school is not known.
- The rush-hour values come from a small set of drives in one area. Other areas have a default value.
- The free road servers make no promise about uptime. Saved drive times keep working when they are down.
- The chart page is read-only.
- Trends compare the last two school years only.

## 11. Credits and data sources

- California Department of Education, for the public school data.
- OpenStreetMap contributors, for the road data. © OpenStreetMap contributors.
- The OSRM project, for the routing software and the public routing server.
- US Census Bureau, for the geocoder that finds street addresses.
- US Federal Highway Administration, for the Urban Congestion Report that gives the rush-hour index.
- edjoin.org, for the teaching job listings.

## 12. For the curious

EdTrawl is plain Python, using only the standard library, with one SQLite database file. Each module does one job:

- `edtrawl.py` reads the commands and wires the rest together.
- `flows.py` runs the guided steps: setup, the daily session, the deck of cards and the small commands.
- `ui.py` holds every sentence the program shows, and is the only module that writes to the terminal.
- `db.py` creates the database and its tables.
- `config.py` reads and writes `config.toml`.
- `ingest.py` loads the state's school files.
- `travel.py` finds home, works out drive times and stores them.
- `edjoin.py` fetches job postings politely.
- `match.py` links each posting to a school or district.
- `query.py` runs the searches.
- `chart.py` writes the chart page.
- `calibrate.py` is a developer tool. It fits the offline formula against road times and prints the report in section 6.

To run the tests, go to the EdTrawl folder and type:

```
python -m unittest
```

The tests are written to run offline.
