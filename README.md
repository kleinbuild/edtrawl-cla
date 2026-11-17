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

- A street address. EdTrawl sends the address once to the US Census Bureau's free geocoder to find the spot. It asks first, and only sends it if you type `y`. It never saves the address.
- A ZIP code. No internet is needed. Home is placed at the middle of that ZIP code's schools, so drive times are a little rougher.
- A map position, typed as two numbers with a comma between them, for example `36.74,-119.79`.

**Step 2 of 4, schools near you.** EdTrawl asks how far to look, in miles, as the crow flies, from 1 to 100. Press Enter for the default of 20. It then tells you how many public schools and districts are in that range, and the nearest school. If there are none, it says so and asks again, and it names the `home` command in case home is in the wrong place. In the recorded run:

```
Within 20 miles of home, as the crow flies: 472 public schools in 25 districts.
The nearest is William Land Elementary, about 0.7 miles away.
```

**Step 3 of 4, drive times.** EdTrawl asks how to work out drive times. Type `o` or `r` and press Enter.

- `o` is offline. A formula works out each drive from the straight-line distance. Nothing leaves your computer. It cannot see bays, mountains or freeways.
- `r` is roads. EdTrawl asks a free routing server for real road distances. It sends your home spot, rounded to about 100 metres, and the positions of nearby schools. Nothing else.

Pressing Enter means offline. Both add typical rush-hour traffic. Both are estimates. If the road server does not answer, EdTrawl says so and asks again, so you can choose offline. When the drive times are worked out, one line says how many schools have them, how they were worked out, and the command to switch. From a test run on a small sample of schools:

```
Drive times are ready for 4 schools, worked out offline. To use road distances
instead:
    python edtrawl.py routing roads
```

You can switch at any time with `python edtrawl.py routing roads` or `python edtrawl.py routing offline`. You never need to edit a settings file.

**Step 4 of 4, one drive you know.** Type the name of a school you drive to now, or used to. Then type your real morning drive time in minutes. EdTrawl adjusts its estimates to match your roads. You can press Enter to skip this step and come back to it later with `drove`, which is described in section 5.

If you stop setup part way, for example by closing the terminal, the next run picks up where you stopped: it asks again how far to look and how to work out drive times if those were not answered. The one exception is the last step, the drive you know. It is optional, so it is not asked again on its own; use `drove` (section 5) or run `setup` again.

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

EdTrawl does three things. It looks for new jobs. It works out drive times for any new school. Then it shows you each job you have not yet kept or tossed, ten at a time. A job you skip comes back next time. If this computer is not online, EdTrawl says it could not check for new jobs and shows the ones it already saved. Here is one real job card from the recorded run. Only its key line, at the bottom, has changed since:

```
 ── 2 of 58 ─────────────────────────────────────────────── closes Thu (3 days)
 Teacher, Special Education, Preschool SDC MMLE @ Washington ELEM-113
 Washington Elementary · Sacramento City Unified
 Drive   ~4 min there · ~5 home if you leave at 3:30   (about 50 min a week)
 School  362 students, shrinking (-4% in a year) · 19 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [b]ack   [o]pen   [m]ore about the school   [q]uit
```

What each line means:

- **`2 of 58`** is the card number, out of the new jobs for today.
- **`closes Thu (3 days)`** is the application deadline. A card with no deadline has no closing text.
- **The job title** comes from the posting. The school name is in it when the employer wrote one.
- **The school and district** are the place the job is at. A card that says `Site not listed` is a real job. The posting names the district but not a school, so the drive is shown as a range across the district's schools in range. These cards do not offer `[m]ore about the school`, because there is no one school to tell you about.
- **`Drive`** is the drive time to the school, to work and back home. The `~` sign means the time is an estimate. EdTrawl puts `~` on every drive time it works out. It never presents one as a measured time.
- **`if you leave at 3:30`** is the assumption behind the drive home. The afternoon drive is worked out for leaving at 3:30. Leaving later is usually slower.
- **`about 50 min a week`** (or `about 4 hrs a week`) is the drive time for five working days, there and back, added together.
- **`School`** is the enrollment this year, and whether it is growing, steady or shrinking compared with a year before. Then the staff count and any special program the state lists, such as Title I.
- **`Pay`** is the pay text from the posting. `not listed` means the posting does not say.

The keys at the bottom work like this. Type the letter, or the whole word (`keep`, `toss`, `skip`, `back`, `open`, `more`, `quit`), and press Enter. Pressing Enter alone skips the card. Anything else, such as `ok` or `thanks`, is not understood, and EdTrawl asks again.

- `k` keeps the job. It waits in your keepers list until you apply or toss it.
- `t` tosses it. It will not come back.
- `s` skips it for now. It comes up again next time.
- `b` goes back to the previous card and undoes what you chose on it.
- `o` opens the posting in your web browser.
- `m` shows facts about the school, such as grades, enrollment, staff and student groups.
- `q` stops here. The jobs you have not seen stay for next time. If the terminal closes or you press Ctrl-C, EdTrawl stops the same way, and everything you chose so far is saved.

Cards come in hands of ten. After each ten, EdTrawl shows how many you have done and what you chose, and asks whether to go on with the next hand. Type `y` to go on. Pressing Enter stops there, which is a fine place to stop: the rest are waiting next time.

When you have seen every new job, EdTrawl says so and stops. The session ends there. You can close the terminal.

If you chose something by mistake after the session, `keep` and `toss` fix it by number (section 5).

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

**`applied`** notes that you applied. Use the number from `keepers`. The job then leaves your keepers list and goes to the logbook, and `search --status applied` shows it. If it was your last keeper, `keepers` says there are none. The first time you do this, EdTrawl says so. If you already marked that job as applied, EdTrawl says that instead of repeating itself.

```
python edtrawl.py applied 2293501
```

```
Marked as applied: Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1.
First one in the logbook. That's the hard part done.
```

**`logbook`** shows what you have decided on (kept or tossed), kept and applied for. Skipped jobs are not counted. Use it to see your own progress.

```
python edtrawl.py logbook
```

```
Logbook
This week: decided on 2, kept 1, applied to 0.
Since Nov 16: decided on 2, kept 1, applied to 0.
Nov 16  kept     Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1 · Sacramento City Unified School District
```

The output is shortened here. The logbook shows the last ten marks.

**`keep`** and **`toss`** set a job's mark by its number. Use them to undo a slip, for any job EdTrawl has saved. The number is the first thing on each line of `keepers` or `search`. The examples are from a test run on a small sample of schools.

```
python edtrawl.py keep 2294284
python edtrawl.py toss 2294284
```

```
Marked as kept: Teacher, Elementary, 6th Grade @ Nicholas ELEM-28.4.
Marked as tossed: Teacher, Elementary, 6th Grade @ Nicholas ELEM-28.4.
```

**`school`** shows the facts about one school: grades, enrollment, staff, student groups, ethnicity figures, drive times and website. Use it before you apply. Type part of the name, or the name and city exactly as EdTrawl prints them, with a comma between. If more than one school matches, EdTrawl lists them and asks for a number. If it cannot ask, it changes nothing and tells you to add more of the name.

```
python edtrawl.py school "Washington Elementary, Sacramento"
```

```
 ── Washington Elementary ─────────────────────────────────────────────────────
 Sacramento City Unified · Sacramento · Sacramento County
 Grades    K–6 · Elementary · Title I
 Students  362, shrinking (-4% in a year)
 Staff     19 teachers · 33 staff in all
 Drive     ~5 min there · ~5 home if you leave at 3:30   (about 50 min a week)
 Website   http://washington.scusd.edu/
 Drive times assume arriving by 7:00 and leaving at 3:30 on a weekday. Later
 in the afternoon is usually slower.
 School figures: California Department of Education, 2025-26.
```

The output is shortened here. The student group and ethnicity lines are also shown.

**`drove`** tells EdTrawl a drive you know, so it can adjust its estimates. Give the school (the same way as for `school`) and your door-to-door minutes. Add `--pm` for the drive home in the afternoon. The school has to be within your search radius. The answer starts with that drive, what EdTrawl had estimated and what you said, then says every estimate in that direction was scaled by the same amount, and ends with the change for the typical school near you. This example is from a test run on a small sample of schools.

```
python edtrawl.py drove "Washington Elementary, Sacramento" 6
```

```
For Washington Elementary you said 6 min, and I'd estimated ~4. I've scaled
every morning estimate by the same amount: half the schools near you are now
within ~32 min (it was ~23).
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

**`home`** sets or changes home. Use a ZIP code if you do not want to send an address anywhere. Put your own ZIP code in place of 93721, which is only an example:

```
python edtrawl.py home --zip 93721
```

To use a street address instead, put it in quotes:

```
python edtrawl.py home "123 Main St, Fresno"
```

**`radius`** changes how many miles from home to look, from 1 to 100, and works out drive times for the new range. If no school is within that many miles, it changes nothing and says so.

```
python edtrawl.py radius 10
```

**`routing`** switches drive times between roads and offline, and works out the drive times again. If the road server does not answer, it keeps your current setting and says so.

```
python edtrawl.py routing roads
python edtrawl.py routing offline
```

**`setup`** runs the setup steps again. It skips any step that is already done. On a home that is fully set up it only offers the optional drive-you-know step again if you skipped it, and it does not fetch jobs. To change the home, use `home`.

```
python edtrawl.py setup
```

**`chart`** writes one web page file, `edtrawl-chart.html`, next to your database and opens it in your browser. It shows a map with home in the centre, distance rings, every school in range as a small dot, and the schools that are hiring marked by drive time. Your jobs are listed beside it, and you can filter them by drive time, by kept jobs, or by jobs closing within seven days. The page is one file with nothing loaded from the internet, so opening it contacts no website. It only shows; keeping and tossing still happen in the terminal. It shows where home is relative to nearby schools, so keep the file to yourself.

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

- **gis.data.ca.gov** (the California state data site). EdTrawl downloads the two school files. The site sometimes needs a moment to prepare a file, so EdTrawl may ask again every few seconds for up to a minute. It sends a plain file request and no information about you. It only does this when the file is not already in the `data` folder.
- **The US Census Bureau geocoder.** Only if you give a street address. It receives that address once, and nothing else. It asks first.
- **The OSRM routing server** (`router.project-osrm.org`, which uses OpenStreetMap road data). Only if you choose roads. It receives your home spot, rounded to about 100 metres, and the positions of schools near you. It receives nothing else.
- **edjoin.org** (the job board). EdTrawl asks for teaching jobs by county and job type, a few seconds apart. It also reads a job's own page, for up to 40 jobs each time, when the school name is not in the title. Your home is not sent. The job numbers are sent as part of the web address.
- **An AI model.** Only if you set one up. See section 8. For a job it cannot match by name, it receives a short piece of the job's employer text and up to 15 school names as candidates. If the model runs on your own computer, that text stays there.

Stored on your computer:

- `edtrawl.db` holds the schools, the drive times, the job postings, your keep, toss and applied marks, and your home spot.
- `config.toml` holds your settings and your home spot. If you add a key for an AI model, it goes here too. If you delete it, your other settings go back to their defaults. EdTrawl takes the home spot from the database and writes the file again, as long as you have only ever set one home; if you have set more than one, it asks you to set home again.
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

- **A job is missing.** Run `python edtrawl.py match --review`. It lists the postings EdTrawl set aside because they did not clearly match a school or district. They are not lost, and EdTrawl does not guess. On a terminal, you can pick the right name for each one.
- **A drive time looks off.** Run `python edtrawl.py drove` with the school and your real minutes, as in section 5. Add `--pm` for the drive home.
- **EdTrawl says it can't read `config.toml`.** It names the file and, when it can, the setting or line. Fix that line in a text editor, or delete the file. Your jobs and marks stay in the database; your settings go back to their defaults.
- **EdTrawl says it can't read `edtrawl.db`.** Move that file somewhere else and run the command again. The school files in the `data` folder stay.
- **EdTrawl says another window is busy.** Another copy of EdTrawl is using the database. Try again in a minute.
- **EdTrawl says there are no schools near home.** Use `radius` with a bigger number, or `home` if home is in the wrong place.
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

There is no command to correct a school's position. If the state's coordinates for a school are wrong, the `schools` table has two columns for a hand correction, `lat_override` and `lng_override`. Reloading the state's file never overwrites them, and everything that reads a position uses the correction when one is set. A drive time already saved for that school is not worked out again until it is 90 days old; deleting that school's row from the `commutes` table makes the next run redo it.

To run the tests, go to the EdTrawl folder and type:

```
python -m unittest
```

The tests are written to run offline.
