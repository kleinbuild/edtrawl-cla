# P2 edge-state playtest: log

Working folder: .../scratchpad/p2/ (one subfolder per scenario: s1a..s16). Helpers: drive2.py (pty, adjustable width/env/Ctrl-C/Ctrl-D/raw escape view), nonet.py (urlopen replacement: blocks all hosts, lets chosen hosts through, can serve the edjoin fixture, can return HTTP errors or stall), pipe.sh (stdout to a file, stdin /dev/null).

## Network use (all runs together)
- edjoin.org: 4 requests from the program (Modoc real run: 1 listing page + 3 posting pages). Plus 1 browser page load, because typing `ok` on a card opened a real posting URL in my browser (see finding 14). Budget 20.
- OSRM (router.project-osrm.org): 2 requests (Modoc `commute`). Budget 30. All other roads runs were blocked by the launcher (6 blocked attempts).
- Census geocoder: 2 requests (both "address" strings that were really typing slips: `12345678` and `38.58,`). Budget 6. I never sent a real street address to it.
- School-list download (gis.data.ca.gov): 0 real requests (3 blocked attempts in the no-data copy).

## Scenario results, in the order of the brief (exact screen text is in the raw transcripts below; key texts are quoted in the final report)
1. No network at each setup step (copy of the project with no data/ folder): download -> err_schools_download; `ingest --file <abs path>` for 2025-26 worked and the next bare run skipped 2025-26 and asked only for 2024-25 (recovery works). With data present: address lookup offline -> err_geocoder_unreachable_setup, re-asked; routing `r` offline -> "Drive times will use roads..." then err_routing_unreachable_setup, re-asked the routing question; `o` then worked; first fetch offline -> err_offline, exit 1. Re-running the bare command skipped setup and went straight to the fetch. A fetch cut after 2 of 3 pages discards the 100 listings already downloaded.
2. Modoc (41.487,-120.542): 7 schools in 2 districts at 20 miles; real fetch gave 3 district jobs, deck worked. Widened to 60 miles: 16 schools; `search --max-commute 5` -> "Nothing within 5 minutes today. 3 jobs open up at 10 minutes" + working command. Before the real fetch, with old Sacramento jobs in the database, `search` listed 50 jobs with "-" as drive time under "nearest drive first" (finding 9).
3. Las Vegas 36.17,-115.14 is inside the California bounding box: "Home is set." Ocean 34.0,-121.5: "Home is set." Both end in reveal_none dead end (finding 4). 40.7,-74 (New York) gives err_outside_california.
4. Home-question nonsense: empty, spaces, `abc` -> err_home_unreadable, re-asks. `12345678` and `38.58,` are treated as street addresses and offered to the geocoder (consent asked first). Radius `abc`/0/500/-5/1.5 -> "Type a number of miles from 1 to 100." Routing `x`, `yes`, `R` handled ('R' accepted). Known-drive minutes abc/0/500/-3 -> err_minutes.
5. ZIP: 00000 and 10001 -> err_unknown_zip; 9581, "95814 " (trailing space, via --zip), abcde -> err_home_unreadable; 93721 and 90210 worked.
6. Daily twice: identical output, the same 56 unmarked jobs come back as "new jobs" (they are unmarked, not new). Two weeks old: "Welcome back. 1 new job since Nov 2." (correct). 100 days old with routing=osrm and no network: err_routing_unreachable then err_offline; deck unreachable.
7. Kept job past deadline: `keepers` shows "closed" in the Closes column; next session says "Since you last looked, 1 keeper has closed. The keepers list marks which."; with nothing else new: "Nothing new since Nov 5, so you're done for today."
8. Widths 60 and 40: lines fit, except the progress line at 40 columns (46 columns wide). NO_COLOR, TERM=dumb, --plain, --no-emoji, non-UTF-8 (LC_ALL=C with coercion off): no escape codes where promised, no broken box characters (ASCII fallback works). Piped output with stdin from /dev/null: bare, search, keepers, match --review, chart --no-open, logbook all finish with zero escape bytes and zero carriage returns; nothing waited.
9. Hostile text: escapes, bidi override and HTML are neutralised in the card, table, keepers, logbook and chart (read the HTML: one <script>, all hostile text entity-escaped, javascript:/file: URLs not rendered as links). One cosmetic gap: an empty title leaves a blank bold line on the card and " · place" in the logbook.
10. drove / applied: see findings 6, 8, 12.
11. Quitting: q on first card, Ctrl-C at the home question, at the radius question, during drive times, during fetch, on a card: all print "Stopped"/"Stopping here" and keep earlier decisions (kept and tossed marks survived Ctrl-C). End of input mid-deck: finding 3.
12. config/db removal, bad config, read-only: findings 2, 5, 7.
13. Concurrency: 15 fetch --from-file runs against 40 rounds of keepers/search/logbook/applied: no lock errors. With another process holding the write lock for 40 s: reads fine; `applied` and `fetch --from-file` fail after 5 s with err_unexpected (finding 11).
14. Others: Enter repeatedly skips every card; `keep`, `TOSS`, `s ` accepted; `yes`, `no`, `?`, `help`, `next` get "Type one of these letters"; `ok` opens a browser; `thanks`/`tell me more` would toss.


## Findings (ranked)

### Real defects
1. Raw Python traceback on a read-only folder. `applied 2293501` or `chart --no-open` where the folder/db is not writable prints two chained tracebacks ending `PermissionError: [Errno 13] Permission denied: '.../edtrawl-error.log'`, exit 1. The error handler itself crashes because it writes the log next to the database. (Reads such as `keepers` work.)
2. Config mistakes and a damaged database give an unusable message. A misspelt key (`radious_miles`), `routing = "google"`, broken TOML, `radius_miles = "twenty"` and a corrupt edtrawl.db all print only: "Something unexpected went wrong, so I stopped. Nothing already saved is lost. The details are in <path>/edtrawl-error.log." The log holds only the exception type and file:line (`TypeError config.py:38`), never the cause, and no next step. "Nothing already saved is lost" is unverifiable for the corrupt database.
3. End of input mid-deck says something untrue. With the terminal sending EOF (Ctrl-D held, or a closed pty), every remaining card is silently skipped and it ends "That's the whole catch: kept 1, skipped 55. Nothing else is new today, so you're done." The user saw none of the 55. No data is lost (skips are not recorded) but the "done" line is false, and 55 cards scroll past.
4. Dead end for a home with no schools in range (Las Vegas, ocean, Nevada side of Tahoe, a typo'd coordinate). `home 36.17,-115.14` says "Home is set." Then the bare command prints "There are no public schools within 20 miles of that spot. Try a wider radius, like 40." and exits 1. Nothing says how to widen it (only an edit of config.toml works, and `radius_miles` is not named) or that home may be the problem. The suggestion also grows past the 100-mile maximum the setup question accepts (radius 60 -> "like 120"). Same text from `commute`.
5. Deleting config.toml while keeping edtrawl.db makes true statements false. `keepers` -> "No keepers yet. Press k on a job's card and it will wait here." (one keeper exists); `search` -> "No teaching jobs are posted within 20 miles right now." (125 jobs exist). Cause: no home_key. `applied` still works, `chart` correctly says no home. The data is intact; the wording tells a tired user it is gone.
6. `drove` with a real school that is outside the range says the school does not exist. `drove "Fresno High" 20` -> "I couldn't find a school called "Fresno High". Check the spelling, or use the school's 14-digit code." A correct 14-digit code of an out-of-range school gets the same text. The search silently requires a drive time.
7. `home` after moving house with roads chosen and the server unreachable: bare command prints "The road-distance server isn't answering. Your saved drive times still work, and I'll use them; a school without one shows no drive time..." although the new home has no saved drive times, then immediately "There are no drive times yet ... python edtrawl.py commute". The suggested `commute` fails with the first message again; the offline escape (routing = "estimate") is never offered. Meanwhile `search` and `keepers` list old jobs with "-" for drive, and `search` header says "nearest drive first".
8. `drove` with several matching schools and no terminal, or a typo at the pick prompt, exits 1 with no message. Non-tty: list + "Showing the first 9..." then nothing (the pick prompt is not shown, no instruction). Pty: typing `abc` at "Type its number, or press Enter to skip." prints a blank line and exits 1. The same silent skip happens in setup step 4 ("One drive you know").
9. `search` and `empty_none_near` assert things that were never checked. Fresh folder before setup: `search` -> "No teaching jobs are posted within 20 miles right now. To look again another day: python edtrawl.py". `school Westmore` before the school list is loaded -> "I couldn't find a school called "Westmore"". After setup whose first fetch failed, `search` says no jobs are posted when none was ever fetched. Also the Modoc case: 50 Sacramento jobs listed under "nearest drive first" with "-" drives after the home moved.
10. Setup with no network can never reach the daily deck. Bare command with saved but unmarked jobs (125 in the copy) and no network: err_offline and exit 1; the 123 already-fetched jobs cannot be triaged offline. The message lists "Your keepers and saved drive times are all still here" but names only `python edtrawl.py` (which fails again) rather than `python edtrawl.py keepers`.
11. Another EdTrawl process holding the database for more than 5 seconds makes writes fail with the generic "Something unexpected went wrong..." (`applied`, `fetch --from-file`). The decision the user just typed is not saved and the text says only "Nothing already saved is lost". Reads are fine. No raw "database is locked" text appears.
12. argparse errors are raw usage text: `applied abc`, `drove Westmore abc`, `drove` with no arguments print "usage: edtrawl.py drove [-h] ..." and "argument minutes: invalid float value: 'abc'", exit 2. These are the only places where jargon and a non-COPY message appear. (Also `home` with no target says "I couldn't read that as an address..." instead of asking.)
13. Narrow terminal: progress line wider than the terminal. At 40 columns "Matching listings to schools  ~~~~⛵  63 of 63" is 46 columns; a line that wraps cannot be redrawn with `\r`, so a real terminal will stack partial lines. 60 and 80 columns are fine.
14. One-letter matching can do the wrong thing. `ok` opened a real browser tab; `thanks`, `tell me more`, `tomorrow`, `toss-up` would TOSS (permanent per README); `stop`, `sure`, `later`... `stop` skips; `yes`/`no`/`next`/`?`/`help` get only "Type one of these letters, then Enter: k, t, s, o, m, q" with no explanation of the letters. `x` at the review prompt (`match --review`) silently skips instead of asking again.
15. A failed fetch throws away what was downloaded. Network cut after 2 of 3 pages: 100 listings dropped, only "This computer doesn't seem to be online..." (the "Nothing you've already saved is lost" wording is not even shown). Cheap to re-fetch, but silent.
16. Quit during setup leaves it half done. Ctrl-C at the radius question after home was set; the next bare run silently skips the radius, routing and known-drive questions (home exists) and works drive times with the default offline estimate. The user is never asked whether they wanted roads, and `config.toml` still says `routing = "estimate"`.

### Wording and tone
17. `err_schools_download`: tells the user to "save the file into the data folder yourself" but gives no address for the file, says data.ca.gov while the request goes to gis.data.ca.gov, and `data/...` is relative to wherever the user is, not to edtrawl.py.
18. "Try a neighboring ZIP code or your street address" for ZIP 10001 / 00000 (err_unknown_zip) does not say it must be California.
19. `home --zip 93721` appears as a copy-paste next step in `err_address_not_found`, `err_geocoder_unreachable`, `home_declined`. 93721 is a Fresno ZIP; the text does not say "use your own". A tired user may set home in Fresno. In setup, `home_declined` tells the user to run a command while the home question is being asked again (the `_setup` variants exist for the other errors, not this one).
20. `err_offline` says "Your keepers ... are all still here" on a first run when none exist.
21. `routing_saved_roads` prints "Drive times will use roads." right before err_routing_unreachable_setup says it isn't answering; it reads as a contradiction. "Offline" in the question but `routing = "estimate"` in config.toml; "switch ... in config.toml" is a programmer's step for this audience and the file's location is never named.
22. `edjoin_notice` is claimed to be once; it prints on every run until a job exists (first run, offline failures, a region with none).
23. `match_set_aside` repeats every day for the same 2 listings; with the `err_llm_unreachable` text both print together. Mild nag.
24. `empty_none_near` / chart empty state: "No teaching jobs are posted within range right now" — see 9.
25. Chart: title "Your chart: the net is empty today" (theme in an empty-state heading); "Closing soon (N)" filter chip and `deadline_soon` are factual but the chip is the only "soon" framing in the product.
26. Logbook lines wrap with no indent ("Special Education - DEPT-62.1 · ..." starts at column 0), which makes it hard to read; a blank title shows " · school".
27. Path in `chart_*` wraps mid-token at 80 columns when the folder is long ("...aabbe427-\n287d-..."), which breaks copy/paste.
28. `applied` twice for the same job repeats "Marked as applied: ..." with no hint that it was already marked; `applied` works on closed and tossed jobs without comment. `keepers_apply_hint` suggests applying to the first listed job even when it is closed.
29. `drove` twice for the same school silently replaces the first value. The `drove_adjusted` line with a single value moves every school by up to double; the clamp message is there, but "typical school ~23 to ~46" from a 20-minute answer is a big swing for one number.
30. `reveal_nearest` can print "about 0.0 miles away" (ZIP home sits on the school centroid).
31. `welcome` shows again on every retry until a home exists (including a retry caused only by the network).

## Audit A: COPY and chart.py against section 4
Violations (key -> text):
- reveal_none -> "Try a wider radius, like {wider}": names an action with no command; wider can exceed 100 (finding 4).
- err_schools_download -> "save the file into the data folder yourself and run: python edtrawl.py ingest --file data/schools_{year}.csv": the file cannot be found by the user; path is relative (17).
- err_routing_unreachable -> "Your saved drive times still work, and I'll use them": untrue when none exist (7).
- err_offline -> "Your keepers and saved drive times are all still here": untrue on a first run; no useful next step offline (10, 20).
- err_unexpected -> no next step; the detail file lacks the cause (2).
- keepers_empty, empty_none_near, chart "No teaching jobs are posted within range right now" -> untrue in states where nothing was checked (5, 9).
- triage_end -> "That's the whole catch ... you're done" is false after end of input (3).
- home_declined, err_address_not_found, err_geocoder_unreachable -> `home --zip 93721` is a placeholder presented as a command (19).
- school_not_found -> untrue for out-of-range schools in `drove` (6).
- routing_saved_roads / routing_saved_offline -> "switch ... later in config.toml": not a step for this audience; key name differs from the words ("estimate") (21).
- edjoin_notice -> treated as one-time, prints repeatedly (22).
- empty_no_new -> "Your N keepers are still open" counts keepers with no deadline as open; not verifiable.
- chart title -> "the net is empty today" (theme word in an empty state).
- Every printed command is `python edtrawl.py ...`; users who run it with `python3` (README tells them to) will get "command not found" for the suggested step. Not a COPY violation, a consistency one.
Checked and fine: no exclamation marks, no streaks, no countdown language, no score or rank, praise only on first keep and first application, every printed command and flag exists (`home --zip`, `home "..."`, `ingest --file`, `commute`, `match --review`, `search --max-commute N`, `search --limit`, `applied N`, `keepers`, `logbook`). Each command suggested by `empty_nearly`, `empty_nearly_filtered`, `keepers_apply_hint`, `keepers_all_applied`, `err_unknown_posting`, `err_no_commutes` (when routing works) ran correctly.

## Audit B: error and empty-state keys, triggered for real?
Triggered for real: err_no_home, err_home_unreadable, err_address_not_found_setup (via the real Census service), err_geocoder_unreachable, err_geocoder_unreachable_setup, err_outside_california (40.7,-74), err_unknown_zip, err_file_not_found, err_no_commutes, err_radius, err_minutes, err_schools_download, err_routing_unreachable, err_routing_unreachable_setup, err_edjoin_refused (HTTP 403, simulated), err_edjoin_busy (429, simulated), err_edjoin_down (500, simulated), err_offline, err_llm_unreachable (config pointing to a dead address), err_unknown_posting, err_open_browser (browser opener forced to fail), err_unexpected, stopped, ask_again, setup_needs_terminal, school_not_found, school_many, home_declined, reveal_none, empty_no_new, empty_no_new_no_keepers, empty_in_range, empty_nearly, empty_nearly_filtered, empty_none_near, empty_filtered, keepers_empty, keepers_all_applied, keepers_closed, logbook_empty, review_empty, chart_saved, chart_written, drove_unchanged, drove_clamped.
Not triggered: err_address_not_found (the non-setup variant; would need a real street address lookup that fails, budget), chart_done (no browser opened for the chart on purpose). attribution_osm and welcome_back were triggered.
Keys no code path uses at all: none. Eleven keys are reached only dynamically (drove_adjusted_am/pm, triage_keys_short, triage_keys_district_short, mark_kept/tossed/applied, virtual_F/V, err_address_not_found_setup, since_today/yesterday) and all but `virtual_*` were seen on screen (virtual_* not tried). `err_outside_california` is reachable only through a coordinate outside California's rectangle, never through the geocoder path in practice (the geocoder path was not forced).

## Scenarios that behaved well
Setup recovery after each network cut (re-running skips completed steps); unknown/foreign ZIP; hostile text everywhere (cards, tables, keepers, logbook, chart HTML); escape codes, carriage returns and emoji off when piped / NO_COLOR / --plain / TERM=dumb / non-UTF-8; 60-column layout; piped commands never wait on input; Ctrl-C and `q` keep decisions; welcome back after two weeks; a keeper passing its deadline; edjoin 403/429/500 messages; `search` suggestions with `--max-commute`; concurrent reads and fast writes (no raw lock error); `applied` unknown number; read-only folder reads.

## Could not test
Real street-address geocode success/failure (budget, Census 2 of 6 spent on typing slips); a real routing outage (simulated by blocking); real full-radius OSRM batches; `o` opening the posting in a browser on a machine with no default browser; Windows/macOS terminals (Windows legacy console, pasting); an actual narrow terminal wrapping (inferred from line width, not seen); a real 429/403 from edjoin (simulated); screen readers.

# Raw transcripts (exact commands and screens)
(Scenarios 1a-4b were run before the logging wrapper existed; their exact screens are quoted in findings and in the final report.)

#### 1c home address, geocoder offline (command)
pty: drive2 s1c 20 y -- home 1315 10th St, Sacramento, CA 95814
```
To find that address I'll send it once to the US Census Bureau's free geocoder
(geocoding.geo.census.gov). Nothing else goes with it, and it isn't saved. Send
it? [y/n]
 > 
y
The Census geocoder isn't answering, or this computer is offline. Nothing was
saved. Your ZIP code works without the internet:
    python edtrawl.py home --zip 93721


[exit: 1 ]
[answers sent at seconds: [(0.1, 'y')] | total 0.2 s]
```

#### 1c fetch offline on existing state
pty: drive2 s1c 20 -- fetch
```
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 1c bare go with routing=osrm, network down, drive times fresh
pty: drive2 s1c 20 --
```
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 1d fetch: network drops after 2 pages
pty: drive2 s1d 120 -- fetch
```
Job listings come from edjoin.org. I ask it for teaching jobs in the counties
around you, and read a few postings to find the school. Your home isn't sent.
 Casting the net  ~~~~~~~~~~~~~⛵···············  100                          
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 4.2 s]
```

#### 2 Modoc setup
pty: drive2 s2 60 41.487,-120.542  o  --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,946 of 9,946    
9,946 schools loaded from the California Department of Education, 2025-26.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,982 of 9,982    
9,982 schools loaded from the California Department of Education, 2024-25.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
41.487,-120.542
Home is set.
Step 2 of 4 · Schools near you
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 

Within 20 miles of home, as the crow flies: 7 public schools in 2 districts.
The nearest is Warner High, about 0.3 miles away.
Step 3 of 4 · Drive times
How should I work out drive times?
  [o]ffline: a formula on straight-line distance. Nothing leaves this computer,
    but it can't see bays, mountains or freeways.
  [r]oads: real road distances from a free OpenStreetMap routing server
    (router.project-osrm.org). It receives your home spot, rounded to about a
    city block, and the positions of schools near you. Nothing else.
Both add typical rush-hour traffic, and both are estimates. Offline or roads?
[o/r]
 > 
o
Drive times will be worked out offline. You can switch to roads later in
config.toml.
 Working out drive times  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  7 of 7               
Drive times are ready for 7 schools.
Step 4 of 4 · One drive you know
Is there a school you drive to now, or used to? Its real morning drive time
lets me fit every estimate to your roads. Type the school's name, or press
Enter to skip.
 > 

Setup is done.
Job listings come from edjoin.org. I ask it for teaching jobs in the counties
around you, and read a few postings to find the school. Your home isn't sent.
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [(4.2, '41.487,-120.'), (4.2, ''), (4.3, 'o'), (4.3, '')] | total 4.4 s]
```

#### 2 fetch fixture
pty: drive2 s2 60 -- fetch --from-file /home/james/Claudorable/EdTrawl-Cla/tests/fixtures/edjoin_listing.json
```
50 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  50 of 50        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review


[exit: 0 ]
[answers sent at seconds: [] | total 0.4 s]
```

#### 2 search default (offline fixture jobs are Sacramento)
pty: drive2 s2 30 -- search
```
50 jobs, nearest drive first.
 Number   Drive    Closes   Job
 2039477  -        -        2026-27 School Year Intermediate Grades (3rd-5th...
 2171001  -        -        Education Specialist - Moderate/Severe ($6000 Hi...
 2171347  -        -        Art Teacher - Aspire Public Schools, Sacramento...
 2171393  -        -        Education Specialist - Mild/Moderate ($6000 Hiri...
 2171402  -        -        Elementary Teacher - Aspire Public Schools, Sacr...
 2225372  -        -        Special Education Teacher in Sacramento, CA · SI...
 2252277  -        -        Special Education Teacher **Sign on Bonus $16K**...
 2252280  -        -        Special Education Teacher **Sign on Bonus $16K**...
 2270705  -        Nov 29   ECE Content Specialist - Education at Marvin Mar...
 2278124  -        -        3rd Grade Teacher · American River Collegiate Ac...
 2291732  -        Nov 17   ELEMENTARY 1ST GRADE TEACHER (Carroll Elementary...
 2291850  -        -        High School Elective (Art, Dance, Drama, or Thea...
 2291935  -        Dec 3    Middle School Math Teacher | Our Lady of the Ass...
 2292437  -        -        Teacher (3rd Grade) @ Higher Learning Academy ·...
 2292438  -        -        Teacher (Transitional Kindergarten) @ Higher Lea...
 2292450  -        -        RSP Teacher *High Demand Bonus $4000* (Specialis...
 2292453  -        -        RSP Teacher *High Demand Bonus $4000* (Specialis...
 2292457  -        -        RSP Teacher *High Demand Bonus $4000*(Specialist...
 2292477  -        -        RSP Teacher *High Demand Bonus $4000* (Specialis...
 2292504  -        -        RSP Teacher *High Demand Bonus $4000*(Specialist...
 2292513  -        -        Teacher (4th Grade) @ Higher Learning Academy ·...
 2292515  -        -        Teacher (TK-5th Grade, ELD) @ COA Elementary · G...
 2292516  -        -        Teacher (TK-5th Grade, Russian) @ Gateway Intern...
 2292518  -        -        Teacher (TK-5th Grade, Russian) @ Empowering Pos...
 2292519  -        -        Teacher (TK-5th Grade, Spanish) @ COA Elementary...
 2292521  -        -        Teacher (TK-5th Grade, Spanish) @ Higher Learnin...
 2292522  -        -        Teacher (Transitional Kindergarten) @ Empowering...
 2292523  -        -        Teacher (TK-5th Grade, Spanish) @ Gateway Intern...
 2293222  -        Nov 27   California State Prison, Solano JC-537086 - TEAC...
 2293501  -        Nov 29   Augmentative and Alternative Communication Speci...
 2293601  -        Dec 1    Online Middle School Teacher (Intervention Speci...
 2293699  -        Nov 23   ELEMENTARY 6TH GRADE TEACHER (Marion Mix Element...
 2293788  -        -        Special Education Moderate/Severe Teacher (1.0 F...
 2294045  -        -        Teacher - ELA - (1.0 FTE) · Twin Rivers Unified
 2294190  -        Nov 18   Math Teacher (0.20 FTE) *TEMPORARY / INTERNAL ON...
 2294247  -        -        Special Education Moderate Teacher (1.0 FTE) 202...
 2294284  -        Nov 17   Teacher, Elementary, 6th Grade @ Nicholas ELEM-2...
 2294285  -        -        English Language Development Teacher - Online Pr...
 2294286  -        -        Independent Study Teacher - Online Program (Nort...
 2294525  -        -        RESOURCE TEACHER - SPECIAL EDUCATION - MILD/ MOD...
 2294541  -        -        RESOURCE TEACHER - SPECIAL EDUCATION - MILD/ MOD...
 2294542  -        -        RESOURCE TEACHER, SPECIAL EDUCATION - MODERATE/S...
 2294547  -        -        RESOURCE TEACHER - SPECIAL EDUCATION - MILD/ MOD...
 2294552  -        -        RESOURCE TEACHER - SPECIAL EDUCATION - MODERATE/...
 2294771  -        Jan 31   Learning Recovery Emgercy Block Grant Elementary...
 2294848  -        -        Teacher - 7th/8th Science DLI Teacher · Twin Riv...
 2295137  -        Nov 19   Teacher, Special Education, Preschool @ Elder Cr...
 2295139  -        Nov 19   Teacher, Special Education, Preschool SDC MMLE @...
 2295141  -        Nov 19   Teacher, Elementary, 3rd Grade @ Theodore Judah...
 2295164  -        Nov 19   Teacher, Resource, Special Education @ Will C. W...


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 2 search --max-commute 10
pty: drive2 s2 30 -- search --max-commute 10
```
Nothing within 10 minutes today.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 2 bare go, edjoin served by fixture-like empty reply
pty: drive2 s2 30 -- keepers
```
No keepers yet. Press k on a job's card and it will wait here.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 2 logbook
pty: drive2 s2 30 -- logbook
```
Logbook
Nothing in the logbook yet. It fills in as you keep, toss and apply.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 2 Modoc real bare go (real edjoin)
pty: drive2 s2 120 q --
```
Job listings come from edjoin.org. I ask it for teaching jobs in the counties
around you, and read a few postings to find the school. Your home isn't sent.
 Casting the net  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  3 of 3                       
3 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  3 of 3          
 Reading postings for school names  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  3 of 3     
3 new jobs within range, nearest first.
 ── 1 of 3 ────────────────────────────────────────────────────────────────────
 Education Specialist Teacher/Intern -Year for Year Experience Credit
 Site not listed · Modoc Joint Unified
 Drive   ~6 to ~7 min across the district's 5 schools in range
 Pay     $2,000 / year for a Masters + $5,000 / year Ed Specialist Stipend
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 3 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(7.6, 'q')] | total 7.6 s]
```

#### 2 widened radius 60: commute
pty: drive2 s2 60 -- commute
```
 Working out drive times  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9 of 9               
Drive times are ready for 16 schools.


[exit: 0 ]
[answers sent at seconds: [] | total 0.3 s]
```

#### 2 search after widening (3 jobs)
pty: drive2 s2 30 -- search
```
3 jobs, nearest drive first.
 Number   Drive    Closes   Job
 2288422  ~6-7     -        Education Specialist Teacher/Intern -Year for Ye...
 2290417  ~6-7     -        Multiple Subject Teacher/Intern - Year for Year...
 2293900  ~6-7     -        World Language Teacher / Intern- Year for year e...


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 2 search --max-commute 5
pty: drive2 s2 30 -- search --max-commute 5
```
Nothing within 5 minutes today.
3 jobs open up at 10 minutes:
    python edtrawl.py search --max-commute 10


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 2 search --max-commute 5 --level high
pty: drive2 s2 30 -- search --max-commute 5 --level high
```
Nothing within 5 minutes today.
No jobs fit those filters. Try dropping one.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 2 search --charter yes
pty: drive2 s2 30 -- search --charter yes
```
No jobs fit those filters. Try dropping one.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 home Las Vegas (command)
pty: drive2 s3 30 -- home 36.17,-115.14
```
Home is set.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 home ocean (command)
pty: drive2 s3 30 -- home 34.0,-121.5
```
Home is set.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 ocean in setup: radius 20 then Enter default re-offer
pty: drive2 s3 60 34.0,-121.5  50 o  --
```
There are no public schools within 60 miles of that spot. Try a wider radius,
like 120.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 ocean fresh setup interactive: radius answers 20, 90, 100, 150(stuck?)
pty: drive2 s3b 60 34.0,-121.5  90 100 o  --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,946 of 9,946    
9,946 schools loaded from the California Department of Education, 2025-26.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,982 of 9,982    
9,982 schools loaded from the California Department of Education, 2024-25.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
34.0,-121.5
Home is set.
Step 2 of 4 · Schools near you
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 

There are no public schools within 20 miles of that spot. Try a wider radius,
like 40.
How many miles from home should I look, as the crow flies? Press Enter for 40.
 > 
90
Within 90 miles of home, as the crow flies: 60 public schools in 13 districts.
The nearest is Miguelito Elementary, about 73.0 miles away.
Step 3 of 4 · Drive times
How should I work out drive times?
  [o]ffline: a formula on straight-line distance. Nothing leaves this computer,
    but it can't see bays, mountains or freeways.
  [r]oads: real road distances from a free OpenStreetMap routing server
    (router.project-osrm.org). It receives your home spot, rounded to about a
    city block, and the positions of schools near you. Nothing else.
Both add typical rush-hour traffic, and both are estimates. Offline or roads?
[o/r]
 > 
100
Type one of these letters, then Enter: o, r.
 > 
o
Drive times will be worked out offline. You can switch to roads later in
config.toml.
 Working out drive times  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  60 of 60             
Drive times are ready for 60 schools.
Step 4 of 4 · One drive you know
Is there a school you drive to now, or used to? Its real morning drive time
lets me fit every estimate to your roads. Type the school's name, or press
Enter to skip.
 > 

Setup is done.
Job listings come from edjoin.org. I ask it for teaching jobs in the counties
around you, and read a few postings to find the school. Your home isn't sent.
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [(4.2, '34.0,-121.5'), (4.2, ''), (4.2, '90'), (4.3, '100'), (4.3, 'o'), (4.4, '')] | total 4.4 s]
```

#### 3 bare go afterwards
pty: drive2 s3b 30 --
```
Job listings come from edjoin.org. I ask it for teaching jobs in the counties
around you, and read a few postings to find the school. Your home isn't sent.
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 commute afterwards
pty: drive2 s3b 30 -- commute
```
Drive times are ready for 60 schools.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 search afterwards
pty: drive2 s3b 30 -- search
```
No teaching jobs are posted within 90 miles right now. To look again another
day:
    python edtrawl.py


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 chart
pty: drive2 s3b 30 -- chart --no-open
```
Chart written to /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-
287d-4927-86ce-4355720f397b/scratchpad/p2/s3b/edtrawl-chart.html. It shows
where home is, so keep the file to yourself.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 4 home question nonsense, invented address (real Census), n at consent, then lat,lng typos
pty: drive2 s4 90      abc 12345678 99999 Nowhere Blvd, Zzyzx Springs, CA y 99999 Nowhere Blvd, Zzyzx Springs, CA n 38.58,  91,200 0000 38.577,-121.495 abc 0 500 -5 1.5 20  x yes   --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,946 of 9,946    
9,946 schools loaded from the California Department of Education, 2025-26.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,982 of 9,982    
9,982 schools loaded from the California Department of Education, 2024-25.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 

I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
   
I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
abc
I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
12345678
To find that address I'll send it once to the US Census Bureau's free geocoder
(geocoding.geo.census.gov). Nothing else goes with it, and it isn't saved. Send
it? [y/n]
 > 
99999 Nowhere Blvd, Zzyzx Springs, CA
Type one of these letters, then Enter: y, n.
 > 
y
I couldn't place that address, so nothing was saved. Try just your ZIP code;
that needs no internet.
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
99999 Nowhere Blvd, Zzyzx Springs, CA
To find that address I'll send it once to the US Census Bureau's free geocoder
(geocoding.geo.census.gov). Nothing else goes with it, and it isn't saved. Send
it? [y/n]
 > 
n
Nothing was sent. A ZIP code or a map position needs no geocoder:
    python edtrawl.py home --zip 93721
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
38.58, 
To find that address I'll send it once to the US Census Bureau's free geocoder
(geocoding.geo.census.gov). Nothing else goes with it, and it isn't saved. Send
it? [y/n]
 > 
91,200
Type one of these letters, then Enter: y, n.
 > 
0000
Type one of these letters, then Enter: y, n.
 > 
38.577,-121.495
Type one of these letters, then Enter: y, n.
 > 
abc
Type one of these letters, then Enter: y, n.
 > 
0
Type one of these letters, then Enter: y, n.
 > 
500
Type one of these letters, then Enter: y, n.
 > 
-5
Type one of these letters, then Enter: y, n.
 > 
1.5
Type one of these letters, then Enter: y, n.
 > 
20 
Type one of these letters, then Enter: y, n.
 > 
x
Type one of these letters, then Enter: y, n.
 > 
yes
I couldn't place that address, so nothing was saved. Try just your ZIP code;
that needs no internet.
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 

I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 

I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 

[exit: still running (killed) ]
[answers sent at seconds: [(4.5, ''), (4.5, '   '), (4.5, 'abc'), (4.5, '12345678'), (4.5, '99999 Nowher'), (4.5, 'y'), (5.0, '99999 Nowher'), (5.0, 'n'), (5.0, '38.58, '), (5.0, '91,200'), (5.0, '0000'), (5.0, '38.577,-121.'), (5.0, 'abc'), (5.0, '0'), (5.0, '500'), (5.0, '-5'), (5.0, '1.5'), (5.0, '20 '), (5.0, 'x'), (5.0, 'yes'), (5.4, ''), (5.4, '')] | total 5.4 s]
```

#### 4b radius/routing/known-drive nonsense
pty: drive2 s4b 90 38.577,-121.495 abc 0 500 -5 1.5 20  x R yes o washington 1 abc 0 500 -3 25 --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,946 of 9,946    
9,946 schools loaded from the California Department of Education, 2025-26.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,982 of 9,982    
9,982 schools loaded from the California Department of Education, 2024-25.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
38.577,-121.495
Home is set.
Step 2 of 4 · Schools near you
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 
abc
Type a number of miles from 1 to 100.
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 
0
Type a number of miles from 1 to 100.
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 
500
Type a number of miles from 1 to 100.
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 
-5
Type a number of miles from 1 to 100.
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 
1.5
Type a number of miles from 1 to 100.
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 
20 
Within 20 miles of home, as the crow flies: 472 public schools in 25 districts.
The nearest is William Land Elementary, about 0.7 miles away.
Step 3 of 4 · Drive times
How should I work out drive times?
  [o]ffline: a formula on straight-line distance. Nothing leaves this computer,
    but it can't see bays, mountains or freeways.
  [r]oads: real road distances from a free OpenStreetMap routing server
    (router.project-osrm.org). It receives your home spot, rounded to about a
    city block, and the positions of schools near you. Nothing else.
Both add typical rush-hour traffic, and both are estimates. Offline or roads?
[o/r]
 > 
x
Type one of these letters, then Enter: o, r.
 > 
R
Drive times will use roads. You can switch to offline later in config.toml.
The road-distance server isn't answering right now. Nothing is lost. Choose
offline for now; you can switch to roads later in config.toml.
How should I work out drive times?
  [o]ffline: a formula on straight-line distance. Nothing leaves this computer,
    but it can't see bays, mountains or freeways.
  [r]oads: real road distances from a free OpenStreetMap routing server
    (router.project-osrm.org). It receives your home spot, rounded to about a
    city block, and the positions of schools near you. Nothing else.
Both add typical rush-hour traffic, and both are estimates. Offline or roads?
[o/r]
 > 
yes
Type one of these letters, then Enter: o, r.
 > 
o
Drive times will be worked out offline. You can switch to roads later in
config.toml.
 Working out drive times  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  472 of 472           
Drive times are ready for 472 schools.
Step 4 of 4 · One drive you know
Is there a school you drive to now, or used to? Its real morning drive time
lets me fit every estimate to your roads. Type the school's name, or press
Enter to skip.
 > 
washington
More than one school matches "washington". Which one?
  [1] George Washington Carver School of Arts and Science, Sacramento
  [2] Washington Elementary, Sacramento
  [3] Washington Middle College High, West Sacramento
  [4] Washington Unified Virtual Academy, West Sacramento
Type its number, or press Enter to skip.
 > 
1
About how many minutes is the morning drive to George Washington Carver School
of Arts and Science, door to door?
 > 
abc
Type the minutes as a number from 1 to 240.
About how many minutes is the morning drive to George Washington Carver School
of Arts and Science, door to door?
 > 
0
Type the minutes as a number from 1 to 240.
About how many minutes is the morning drive to George Washington Carver School
of Arts and Science, door to door?
 > 
500
Type the minutes as a number from 1 to 240.
About how many minutes is the morning drive to George Washington Carver School
of Arts and Science, door to door?
 > 
-3
Type the minutes as a number from 1 to 240.
About how many minutes is the morning drive to George Washington Carver School
of Arts and Science, door to door?
 > 
25
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~25 to ~28 min.
Setup is done.
Job listings come from edjoin.org. I ask it for teaching jobs in the counties
around you, and read a few postings to find the school. Your home isn't sent.
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [(4.1, '38.577,-121.'), (4.1, 'abc'), (4.1, '0'), (4.1, '500'), (4.1, '-5'), (4.1, '1.5'), (4.1, '20 '), (4.2, 'x'), (4.2, 'R'), (5.2, 'yes'), (5.2, 'o'), (5.4, 'washington'), (5.4, '1'), (5.4, 'abc'), (5.4, '0'), (5.4, '500'), (5.4, '-3'), (5.4, '25')] | total 5.4 s]
```

#### 5 home --zip '00000'
pty: drive2 s5 20 -- home --zip 00000
```
I couldn't find any schools in ZIP 00000, and I place a ZIP by its schools.
Nothing was saved. Try a neighboring ZIP code or your street address.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 home --zip '10001'
pty: drive2 s5 20 -- home --zip 10001
```
I couldn't find any schools in ZIP 10001, and I place a ZIP by its schools.
Nothing was saved. Try a neighboring ZIP code or your street address.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 home --zip '93721'
pty: drive2 s5 20 -- home --zip 93721
```
Home is set.
A ZIP code puts home at the middle of that ZIP's schools, which can be a mile
or two off, so drive times will be a little rougher. To give an address later:
    python edtrawl.py home "your street address"


[exit: 0 ]
[answers sent at seconds: [] | total 0.3 s]
```

#### 5 home --zip '9581'
pty: drive2 s5 20 -- home --zip 9581
```
I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 home --zip '95814 '
pty: drive2 s5 20 -- home --zip 95814 
```
I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 home --zip 'abcde'
pty: drive2 s5 20 -- home --zip abcde
```
I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 home 00000 as target
pty: drive2 s5 20 -- home 00000
```
I couldn't find any schools in ZIP 00000, and I place a ZIP by its schools.
Nothing was saved. Try a neighboring ZIP code or your street address.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 home 10001 as target
pty: drive2 s5 20 -- home 10001
```
I couldn't find any schools in ZIP 10001, and I place a ZIP by its schools.
Nothing was saved. Try a neighboring ZIP code or your street address.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 home (no arg)
pty: drive2 s5 20 -- home
```
I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 home --zip 90210 then search
pty: drive2 s5 20 -- home 90210
```
Home is set.
A ZIP code puts home at the middle of that ZIP's schools, which can be a mile
or two off, so drive times will be a little rougher. To give an address later:
    python edtrawl.py home "your street address"


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 5 bare go after moving home (commutes stale?)
pty: drive2 s5 20 q --
```
The road-distance server isn't answering. Your saved drive times still work,
and I'll use them; a school without one shows no drive time until the server is
back. To try again later:
    python edtrawl.py
There are no drive times yet, so I don't know which counties to look in. This
works them out:
    python edtrawl.py commute


[exit: 1 ]
[answers sent at seconds: [] | total 1.2 s]
```

#### 5 commute after home moved, routing down
pty: drive2 s5 20 -- commute
```
The road-distance server isn't answering. Your saved drive times still work,
and I'll use them; a school without one shows no drive time until the server is
back. To try again later:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 1.2 s]
```

#### 5 search after home moved
pty: drive2 s5 20 -- search
```
The nearest 50 jobs. There are more: add --limit and a bigger number to see
them.
 Number   Drive    Closes   Job
 2039477  -        -        2026-27 School Year Intermediate Grades (3rd-5th...
 2055181  -        Dec 31   Preschool Substitute Teacher · Adventure Christi...
 2055214  -        Dec 31   Preschool Substitute Teacher's Aide · Adventure...
 2055262  -        Mar 31   Substitute Teacher's Aide · Adventure Christian...
 2168616  -        -        Education Specialist (Intern Sponsorship Program...
 2171001  -        -        Education Specialist - Moderate/Severe ($6000 Hi...
 2171347  -        -        Art Teacher - Aspire Public Schools, Sacramento...
 2171393  -        -        Education Specialist - Mild/Moderate ($6000 Hiri...
 2171398  -        -        Transitional Kindergarten Teacher - Aspire Publi...
 2171402  -        -        Elementary Teacher - Aspire Public Schools, Sacr...
 2181576  -        -        Feather River Charter School - Homeschool Teache...
 2209257  -        -        Teacher, Visually Impaired Program (Certificated...
 2225372  -        -        Special Education Teacher in Sacramento, CA · SI...
 2243803  -        -        SPED MOD/SEVERE K/12TH TEACHER [1.0 FTE] at Barr...
 2252277  -        -        Special Education Teacher **Sign on Bonus $16K**...
 2252280  -        -        Special Education Teacher **Sign on Bonus $16K**...
 2270705  -        Nov 29   ECE Content Specialist - Education at Marvin Mar...
 2273604  -        -        Academic Enrichment Teachers- ELOP (CDU Program)...
 2278124  -        -        3rd Grade Teacher · American River Collegiate Ac...
 2278127  -        -        3rd Grade Teacher- American River Collegiate Aca...
 2281141  -        -        SDC Teacher- Mild/Moderate Bridgeway Island Elem...
 2286744  -        -        Science Teacher (Spanish Bilingual Authorization...
 2286813  -        -        Special Education Teacher - Extensive Supports N...
 2286960  -        -        Early Childhood Development - Site Supervisor (H...
 2287140  -        -        PE Teacher 6/7/8 [1.0 FTE] at Will Rogers Middle...
 2287267  -        -        High School English Teacher · St. HOPE Public Sc...
 2287693  -        -        RSP Teacher *High Demand Bonus $4000* (Specialis...
 2287720  -        -        Education Specialist- Mild/Moderate 2026-2027 (T...
 2287770  -        -        7th/8th Grade (MATH) Teacher -Fortune Middle Sch...
 2287777  -        -        2027-2028 Single Subject Teacher (Grades 6-12 Po...
 2287805  -        -        2027-2028 Multiple Subjects Teacher (Grades TK-5...
 2287904  -        -        Teacher - 5th Grade, Multiple Subject Job #2627-...
 2288018  -        -        Special Education Teacher - TAP GR 1-3 @ Suisun...
 2288428  -        -        Homeschool Educational Consultant - Homeschool K...
 2288724  -        -        2026-27 School Year - Special Education Teacher...
 2288918  -        -        Special Education Moderate/Severe Teacher (1.0 F...
 2289020  -        -        Special Education Teacher - Redding, CA · Spectr...
 2289463  -        Mar 26   Teacher - CTE Computers-AI @ Fairfield-Suisun Ad...
 2289588  -        Nov 30   6th Grade Middle School Teacher-Golden West Midd...
 2289761  -        -        Education Specialist (Elementary) - 0.5 FTE, POS...
 2289889  -        -        Secondary Teacher Math Intervention and Reading...
 2289949  -        -        SPED Mod/Severe Teacher [1.0 FTE] at Bella Vista...
 2289971  -        -        Spanish Teacher - Cooley Middle School - 2026/20...
 2290379  -        Nov 20   50% FTE - K-8 Education Specialist Mild/Mod, 202...
 2290384  -        Nov 20   50% FTE - K-8 Education Specialist Extensive Sup...
 2290391  -        -        Lead 1st - 2nd Grade Teacher · Legacy Academy
 2290458  -        -        Physical Education Teacher (1.0 FTE) *TEMPORARY*...
 2290869  -        Nov 30   Special Education Teacher · Travis Unified
 2291339  -        Dec 4    Special Education Teacher (Learning Resource) In...
 2291530  -        -        TK/Kindergarten Combo- Alan Rowe College Prep (E...


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]

#### 5 bare go after home moved but jobs exist
pty: drive2 s5 20 -- keepers
```
Keepers: 1 job, soonest deadline first
 Number   Drive    Closes   Job
 2293501  -        Nov 29   Augmentative and Alternative Communication Speci...
When you apply for one, note it by its number:
    python edtrawl.py applied 2293501


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 6 daily run 1 (gate4 state, fake edjoin=fixture)
pty: drive2 s6 60 q --
```
 Casting the net  ~~~~~~~~~~~~~~~~~~~⛵·········  250 of 375                   
0 new listings saved, and 250 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 56 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.5, 'q')] | total 8.5 s]
```

#### 6 daily run 2 immediately
pty: drive2 s6 60 q --
```
 Casting the net  ~~~~~~~~~~~~~~~~~~~⛵·········  250 of 375                   
0 new listings saved, and 250 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  63 of 63        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 56 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'q')] | total 8.5 s]
```

#### 6 two weeks old; edjoin returns nothing new (fixture emptied)
pty: drive2 s6b 60 q --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 56 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'q')] | total 8.4 s]
```

#### 6 two weeks old: 5 listings new again
pty: drive2 s6b 60 q --
```
 Casting the net  ~~~~~~~~~~~~~~~~~~~⛵·········  250 of 375                   
1 new listing saved, and 249 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  62 of 62        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
Welcome back. 1 new job since Nov 2.
54 new jobs within range, nearest first.
 ── 1 of 54 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 54 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'q')] | total 8.5 s]
```

#### 6 drive times 100 days old, osrm down, no fake edjoin
pty: drive2 s6b 60 q --
```
The road-distance server isn't answering. Your saved drive times still work,
and I'll use them; a school without one shows no drive time until the server is
back. To try again later:
    python edtrawl.py
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 1.2 s]
```

#### 7 keepers with passed deadline
pty: drive2 s7 30 -- keepers
```
Keepers: 1 job, soonest deadline first
 Number   Drive    Closes   Job
 2293501  ~4-24    closed   Augmentative and Alternative Communication Speci...
When you apply for one, note it by its number:
    python edtrawl.py applied 2293501


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 7 next session (1 keeper closed, 123 unseen)
pty: drive2 s7 60 q --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
Since you last looked, 1 keeper has closed. The keepers list marks which.
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 56 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'q')] | total 8.4 s]
```

#### 7 applied to the closed keeper
pty: drive2 s7 30 -- applied 2293501
```
Marked as applied: Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1.
First one in the logbook. That's the hard part done.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 7 session: nothing new, only closed keeper
pty: drive2 s7 60 q --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  63 of 63        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 56 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'q')] | total 8.4 s]
```

#### 7 chart with closed keeper (no open)
pty: drive2 s7 30 -- chart --no-open
```
Chart written to /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-
287d-4927-86ce-4355720f397b/scratchpad/p2/s7/edtrawl-chart.html. It shows where
home is, so keep the file to yourself.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 7 nothing new, one closed keeper
pty: drive2 s7 60 --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  63 of 63        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
Since you last looked, 1 keeper has closed. The keepers list marks which.
Nothing new since Nov 5, so you're done for today.


[exit: 0 ]
[answers sent at seconds: [] | total 8.4 s]
```

#### 7 nothing new, no keepers
pty: drive2 s7 60 --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  63 of 63        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
Nothing new since Nov 5, so you're done for today.


[exit: 0 ]
[answers sent at seconds: [] | total 8.4 s]
```

#### 7 keepers all applied
pty: drive2 s7 30 -- keepers
```
No keepers waiting. You've applied to 1 job, listed in the logbook:
    python edtrawl.py logbook


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 7 logbook
pty: drive2 s7 30 -- logbook
```
Logbook
This week: looked at 125, kept 1, applied to 1.
Since Nov 15: looked at 125, kept 1, applied to 1.
Nov 16  applied  Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1 · Sacramento City Unified School District
Nov 16  tossed   Teacher, Special Education, Preschool SDC MMLE @ Washington
ELEM-113 · Washington Elementary
Nov 15  tossed   2026-27 School Year Intermediate Grades (3rd-5th) Teacher at
Growth Public Schools · Growth Public Schools
Nov 15  tossed   Preschool Substitute Teacher · Adventure Christian School
Nov 15  tossed   Preschool Substitute Teacher's Aide · Adventure Christian
School
Nov 15  tossed   Substitute Teacher's Aide · Adventure Christian School
Nov 15  tossed   Education Specialist (Intern Sponsorship Program) · Aspire
Public Schools - Sacramento County
Nov 15  tossed   Education Specialist - Moderate/Severe ($6000 Hiring Bonus) ·
Aspire Public Schools - Sacramento County
Nov 15  tossed   Art Teacher - Aspire Public Schools, Sacramento · Aspire
Public Schools - Sacramento County
Nov 15  tossed   Education Specialist - Mild/Moderate ($6000 Hiring Bonus) ·
Aspire Public Schools - Sacramento County


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 8 60 cols: bare go, k then m then q
pty: drive2 s8 60 m  q --
```
RAW: esc codes: 38 | max visible line width: 59 | non-ascii: ·─⛵ | replacement chars: 0 | '?' runs: 0
 Casting the net  <ESC>[36m⛵<ESC>[0m····························  0        
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~<ESC>[36m⛵<ESC>[0m  70 of 70 
Set aside: 2 listings I couldn't place at a school or
district with confidence. To check by hand:
<ESC>[36m    python edtrawl.py match --review<ESC>[0m
56 new jobs within range, nearest first.
<ESC>[36m ── 1 of 56 ───────────────────────────────────────────────<ESC>[0m
<ESC>[1m Education Specialist- Mild/Moderate 2026-2027 (Temporary<ESC>[0m
<ESC>[1m Contract)<ESC>[0m
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in
         range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295
         annual stipend+ $1,295 for doctorate/ BCLAD-...
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
m
Type one of these letters, then Enter: k, t, s, o, q.
 > 

Skipped. It'll come up again next time.
<ESC>[36m ── 2 of 56 ───────────────────────────────── closes Nov 25<ESC>[0m
<ESC>[1m 2026-2027 Intervention Specialist- Westmore Oaks<ESC>[0m
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30
         (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers
         Title I
 Pay     M.A./M.S- $1,250 annual stipend+ $1,250 for
         doctorate/ BCLAD- $1,250 annual stipend. Year f...
[<ESC>[36mk<ESC>[0m]eep [<ESC>[36mt<ESC>[0m]oss [<ESC>[36ms<ESC>[0m]kip [<ESC>[36mo<ESC>[0m]pen [<ESC>[36mm<ESC>[0m]ore [<ESC>[36mq<ESC>[0m]uit
 > 
q
Stopping here: skipped 1. The other 55 jobs will be here
next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'm'), (8.4, ''), (8.4, 'q')] | total 8.5 s]
```

#### 8 40 cols
pty: drive2 s8 60 m k m  q --
```
RAW: esc codes: 76 | max visible line width: 46 | non-ascii: ·–─⛵ | replacement chars: 0 | '?' runs: 0
 Casting the net  <ESC>[36m⛵<ESC>[0m···············  0 
0 new listings saved, and 0 I'd seen
before.
 Matching listings to schools  ~~~~<ESC>[36m⛵<ESC>[0m  63 of 63
Set aside: 2 listings I couldn't place
at a school or district with
confidence. To check by hand:
<ESC>[36m    python edtrawl.py match --review<ESC>[0m
56 new jobs within range, nearest
first.
<ESC>[36m ── 1 of 56 ───────────────────────────<ESC>[0m
<ESC>[1m Education Specialist- Mild/Moderate<ESC>[0m
<ESC>[1m 2026-2027 (Temporary Contract)<ESC>[0m
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the
         district's 13 schools in range
 Pay     SPED- $1,495 annual stipend,
         M.A./M.S- $1,295 annual...
[<ESC>[36mk<ESC>[0m]eep [<ESC>[36mt<ESC>[0m]oss [<ESC>[36ms<ESC>[0m]kip [<ESC>[36mo<ESC>[0m]pen [<ESC>[36mq<ESC>[0m]uit
 > 
m
Type one of these letters, then Enter:
k, t, s, o, q.
 > 
k
Kept.
<ESC>[36m ── 2 of 56 ───────────── closes Nov 25<ESC>[0m
<ESC>[1m 2026-2027 Intervention Specialist-<ESC>[0m
<ESC>[1m Westmore Oaks<ESC>[0m
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there
         ~9 home if you leave by 3:30
         (about 1.5 hrs a week)
 School  527 students, steady (-1% in a
         year)
         30 teachers · Title I
 Pay     M.A./M.S- $1,250 annual
         stipend+ $1,250 for doctora...
[<ESC>[36mk<ESC>[0m]eep [<ESC>[36mt<ESC>[0m]oss [<ESC>[36ms<ESC>[0m]kip [<ESC>[36mo<ESC>[0m]pen [<ESC>[36mm<ESC>[0m]ore
[<ESC>[36mq<ESC>[0m]uit
 > 
m
<ESC>[36m ── Westmore Oaks K-8 ─────────────────<ESC>[0m
 Washington Unified · West Sacramento
 Yolo County
 Grades    K–8 · Elementary · Title I
 Students  527, steady (-1% in a year)
 Staff     30 teachers
           37 staff in all
 Groups    English learners 26%
           socioeconomically
           disadvantaged 69%
           students with disabilitie...
 Ethnicity African American 5%
           American Indian 0%
           Asian 19% · Filipino 0%
           Hispanic 44%...
 Drive     ~8 min there
           ~9 home if you leave by 3:30
           (about 1.5 hrs a week)
 Drive times assume arriving by 7:00
 and leaving at 3:30 on a weekday.
 Later in the afternoon is usually
 slower.
 School figures: California Department
 of Education, 2025-26.
<ESC>[36m ── 2 of 56 ───────────── closes Nov 25<ESC>[0m
<ESC>[1m 2026-2027 Intervention Specialist-<ESC>[0m
<ESC>[1m Westmore Oaks<ESC>[0m
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there
         ~9 home if you leave by 3:30
         (about 1.5 hrs a week)
 School  527 students, steady (-1% in a
         year)
         30 teachers · Title I
 Pay     M.A./M.S- $1,250 annual
         stipend+ $1,250 for doctora...
[<ESC>[36mk<ESC>[0m]eep [<ESC>[36mt<ESC>[0m]oss [<ESC>[36ms<ESC>[0m]kip [<ESC>[36mo<ESC>[0m]pen [<ESC>[36mm<ESC>[0m]ore
[<ESC>[36mq<ESC>[0m]uit
 > 

Skipped. It'll come up again next time.
<ESC>[36m ── 3 of 56 ───────────────────────────<ESC>[0m
<ESC>[1m Early Childhood Development - Site<ESC>[0m
<ESC>[1m Supervisor (Head Start)<ESC>[0m
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the
         district's 52 schools in range
 Pay     + $1,800 Stipend + $2,000
         Master's Degree Stipend,...
[<ESC>[36mk<ESC>[0m]eep [<ESC>[36mt<ESC>[0m]oss [<ESC>[36ms<ESC>[0m]kip [<ESC>[36mo<ESC>[0m]pen [<ESC>[36mq<ESC>[0m]uit
 > 
q
Stopping here: kept 1, skipped 1. The
other 54 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'm'), (8.4, 'k'), (8.4, 'm'), (8.4, ''), (8.4, 'q')] | total 8.4 s]

#### 8 NO_COLOR=1
pty: drive2 s8 60 s q --
```
RAW: esc codes: 0 | max visible line width: 79 | non-ascii: ·─⛵ | replacement chars: 0 | '?' runs: 0
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  63 of 63        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
53 new jobs within range, nearest first.
 ── 1 of 53 ───────────────────────────────────────────────────────────────────
 RSP Teacher - 2026/2027 School Year
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
s
Skipped. It'll come up again next time.
 ── 2 of 53 ───────────────────────────────────────────────────────────────────
 Teacher - ELA - (1.0 FTE)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Final placement determined upon receipt of official sealed transcripts
         and verification of prior contracted teaching experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: skipped 1. The other 52 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 's'), (8.4, 'q')] | total 8.4 s]

#### 8 TERM=dumb
pty: drive2 s8 60 s q --
```
RAW: esc codes: 0 | max visible line width: 79 | non-ascii: ·─⛵ | replacement chars: 0 | '?' runs: 0
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  63 of 63        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
53 new jobs within range, nearest first.
 ── 1 of 53 ───────────────────────────────────────────────────────────────────
 RSP Teacher - 2026/2027 School Year
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
s
Skipped. It'll come up again next time.
 ── 2 of 53 ───────────────────────────────────────────────────────────────────
 Teacher - ELA - (1.0 FTE)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Final placement determined upon receipt of official sealed transcripts
         and verification of prior contracted teaching experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: skipped 1. The other 52 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 's'), (8.4, 'q')] | total 8.4 s]

#### 8 LC_ALL=C
pty: drive2 s8 60 s q --
```
RAW: esc codes: 34 | max visible line width: 79 | non-ascii: ·─⛵ | replacement chars: 0 | '?' runs: 0
 Casting the net  <ESC>[36m⛵<ESC>[0m····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~<ESC>[36m⛵<ESC>[0m  63 of 63        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
<ESC>[36m    python edtrawl.py match --review<ESC>[0m
53 new jobs within range, nearest first.
<ESC>[36m ── 1 of 53 ───────────────────────────────────────────────────────────────────<ESC>[0m
<ESC>[1m RSP Teacher - 2026/2027 School Year<ESC>[0m
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 2 of 53 ───────────────────────────────────────────────────────────────────<ESC>[0m
<ESC>[1m Teacher - ELA - (1.0 FTE)<ESC>[0m
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Final placement determined upon receipt of official sealed transcripts
         and verification of prior contracted teaching experience.
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
q
Stopping here: skipped 1. The other 52 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 's'), (8.4, 'q')] | total 8.4 s]

#### 8 --plain
pty: drive2 s8 60 s q -- --plain
```
RAW: esc codes: 0 | max visible line width: 79 | non-ascii: ·─ | replacement chars: 0 | '?' runs: 0
 Casting the net  \_/····························  0                           
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~\_/  63 of 63       
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
53 new jobs within range, nearest first.
 ── 1 of 53 ───────────────────────────────────────────────────────────────────
 RSP Teacher - 2026/2027 School Year
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
s
Skipped. It'll come up again next time.
 ── 2 of 53 ───────────────────────────────────────────────────────────────────
 Teacher - ELA - (1.0 FTE)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Final placement determined upon receipt of official sealed transcripts
         and verification of prior contracted teaching experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: skipped 1. The other 52 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 's'), (8.4, 'q')] | total 8.4 s]

#### 8 --no-emoji
pty: drive2 s8 60 s q -- --no-emoji
```
RAW: esc codes: 34 | max visible line width: 79 | non-ascii: ·─ | replacement chars: 0 | '?' runs: 0
 Casting the net  <ESC>[36m\_/<ESC>[0m····························  0                           
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~<ESC>[36m\_/<ESC>[0m  63 of 63       
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
<ESC>[36m    python edtrawl.py match --review<ESC>[0m
53 new jobs within range, nearest first.
<ESC>[36m ── 1 of 53 ───────────────────────────────────────────────────────────────────<ESC>[0m
<ESC>[1m RSP Teacher - 2026/2027 School Year<ESC>[0m
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 2 of 53 ───────────────────────────────────────────────────────────────────<ESC>[0m
<ESC>[1m Teacher - ELA - (1.0 FTE)<ESC>[0m
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Final placement determined upon receipt of official sealed transcripts
         and verification of prior contracted teaching experience.
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
q
Stopping here: skipped 1. The other 52 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 's'), (8.4, 'q')] | total 8.4 s]

#### 8 true non-UTF8 (LC_ALL=C, no coercion; ascii stdout)
pty: drive2 s8 60 m s m q --
```
RAW: esc codes: 0 | max visible line width: 79 | non-ascii:  | replacement chars: 0 | '?' runs: 0
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s8/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 8 PYTHONIOENCODING=ascii (strict)
pty: drive2 s8 60 q --
```
RAW: esc codes: 0 | max visible line width: 79 | non-ascii:  | replacement chars: 0 | '?' runs: 0
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s8/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]

#### 8 true non-UTF8 (LC_ALL=C, no coercion)
pty: drive2 s8 60 m s m q --
```
RAW: esc codes: 34 | max visible line width: 79 | non-ascii:  | replacement chars: 0 | '?' runs: 0
 Casting the net  <ESC>[36m\_/<ESC>[0m............................  0                           
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~<ESC>[36m\_/<ESC>[0m  63 of 63       
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
<ESC>[36m    python edtrawl.py match --review<ESC>[0m
53 new jobs within range, nearest first.
<ESC>[36m -- 1 of 53 -------------------------------------------------------------------<ESC>[0m
<ESC>[1m RSP Teacher - 2026/2027 School Year<ESC>[0m
 Site not listed - Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
m
Type one of these letters, then Enter: k, t, s, o, q.
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m -- 2 of 53 -------------------------------------------------------------------<ESC>[0m
<ESC>[1m Teacher - ELA - (1.0 FTE)<ESC>[0m
 Site not listed - Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Final placement determined upon receipt of official sealed transcripts
         and verification of prior contracted teaching experience.
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
m
Type one of these letters, then Enter: k, t, s, o, q.
 > 
q
Stopping here: skipped 1. The other 52 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'm'), (8.4, 's'), (8.4, 'm'), (8.4, 'q')] | total 8.4 s]
```

#### 8 bare (piped, stdin=/dev/null)
args:   | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 80
```
0 new listings saved, and 0 I'd seen before.
Matching listings to schools: 63 of 63.
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
53 new jobs within range, nearest first.
 Number   Drive    Closes   Job
 2291651  ~10-28   -        RSP Teacher - 2026/2027 School Year · Twin River...
 2294045  ~10-28   -        Teacher - ELA - (1.0 FTE) · Twin Rivers Unified
 2294848  ~10-28   -        Teacher - 7th/8th Science DLI Teacher · Twin Riv...
 2295141  ~11      Nov 19   Teacher, Elementary, 3rd Grade @ Theodore Judah...
 2291780  ~14-37   Nov 18   Teacher, Itinerant - Deaf & Hard of Hearing, Spe...
 2270705  ~14-41   Nov 29   ECE Content Specialist - Education at Marvin Mar...
 2289889  ~14-41   -        Secondary Teacher Math Intervention and Reading...
 2252277  ~15      -        Special Education Teacher **Sign on Bonus $16K**...
 2252280  ~15      -        Special Education Teacher **Sign on Bonus $16K**...
 2294284  ~15      Nov 17   Teacher, Elementary, 6th Grade @ Nicholas ELEM-2...
 2294771  ~16      Jan 31   Learning Recovery Emgercy Block Grant Elementary...
 2281141  ~17      -        SDC Teacher- Mild/Moderate Bridgeway Island Elem...
 2295164  ~17      Nov 19   Teacher, Resource, Special Education @ Will C. W...
 2294541  ~17-45   -        RESOURCE TEACHER - SPECIAL EDUCATION - MILD/ MOD...
 2290379  ~18      Nov 20   50% FTE - K-8 Education Specialist Mild/Mod, 202...
 2290384  ~18      Nov 20   50% FTE - K-8 Education Specialist Extensive Sup...
 2295137  ~19      Nov 19   Teacher, Special Education, Preschool @ Elder Cr...
 2292437  ~20      -        Teacher (3rd Grade) @ Higher Learning Academy ·...
 2292438  ~20      -        Teacher (Transitional Kindergarten) @ Higher Lea...
 2292450  ~20      -        RSP Teacher *High Demand Bonus $4000* (Specialis...
 2292453  ~20      -        RSP Teacher *High Demand Bonus $4000* (Specialis...
 2292513  ~20      -        Teacher (4th Grade) @ Higher Learning Academy ·...
 2292521  ~20      -        Teacher (TK-5th Grade, Spanish) @ Higher Learnin...
```

#### 8 search (piped, stdin=/dev/null)
args: search  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 80
```
The nearest 50 jobs. There are more: add --limit and a bigger number to see
them.
 Number   Drive    Closes   Job
 2293501  ~4-24    Nov 29   Augmentative and Alternative Communication Speci...
 2295139  ~5       Nov 19   Teacher, Special Education, Preschool SDC MMLE @...
 2287720  ~7-17    -        Education Specialist- Mild/Moderate 2026-2027 (T...
 2294005  ~9       Nov 25   2026-2027 Intervention Specialist- Westmore Oaks...
 2286960  ~10-28   -        Early Childhood Development - Site Supervisor (H...
 2291651  ~10-28   -        RSP Teacher - 2026/2027 School Year · Twin River...
 2294045  ~10-28   -        Teacher - ELA - (1.0 FTE) · Twin Rivers Unified
 2294848  ~10-28   -        Teacher - 7th/8th Science DLI Teacher · Twin Riv...
 2295141  ~11      Nov 19   Teacher, Elementary, 3rd Grade @ Theodore Judah...
 2291780  ~14-37   Nov 18   Teacher, Itinerant - Deaf & Hard of Hearing, Spe...
 2270705  ~14-41   Nov 29   ECE Content Specialist - Education at Marvin Mar...
```

#### 8 keepers (piped, stdin=/dev/null)
args: keepers  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 79
```
Keepers: 4 jobs, soonest deadline first
 Number   Drive    Closes   Job
 2294005  ~9       Nov 25   2026-2027 Intervention Specialist- Westmore Oaks...
 2293501  ~4-24    Nov 29   Augmentative and Alternative Communication Speci...
 2287720  ~7-17    -        Education Specialist- Mild/Moderate 2026-2027 (T...
 2286960  ~10-28   -        Early Childhood Development - Site Supervisor (H...
When you apply for one, note it by its number:
    python edtrawl.py applied 2294005
```

#### 8 match --review (piped, stdin=/dev/null)
args: match --review  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 77
```
2 listings set aside. Under each are the closest names I found; 1.00 would be
identical.
OPTIONS FOR YOUTH  (2 jobs)
    34674473430691  Options for Youth-San Juan  0.79
    34103480136275  Fortune  0.42
    34765056033336  Smythe Academy of Arts and Sciences  0.38
```

#### 8 chart --no-open (piped, stdin=/dev/null)
args: chart --no-open  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 79
```
Chart written to /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-
287d-4927-86ce-4355720f397b/scratchpad/p2/s8/edtrawl-chart.html. It shows where
home is, so keep the file to yourself.
```

#### 8 logbook (piped, stdin=/dev/null)
args: logbook  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 78
```
Logbook
This week: looked at 5, kept 4, applied to 0.
Since Nov 16: looked at 5, kept 4, applied to 0.
Nov 16  kept     Early Childhood Development - Site Supervisor (Head Start) ·
Twin Rivers Unified School District
Nov 16  kept     2026-2027 Intervention Specialist- Westmore Oaks · Westmore
Oaks K-8
Nov 16  kept     Education Specialist- Mild/Moderate 2026-2027 (Temporary
Contract) · Washington Unified School District - W. Sacramento
Nov 16  kept     Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1 · Sacramento City Unified School District
Nov 16  tossed   Teacher, Special Education, Preschool SDC MMLE @ Washington
ELEM-113 · Washington Elementary
```

#### 9 keepers hostile (piped, stdin=/dev/null)
args: keepers  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 80
```
Keepers: 3 jobs, soonest deadline first
 Number   Drive    Closes   Job
 901      ~9       Nov 30   Math Teacher RED · Westmore Oaks K-8
 905      ~9       Nov 30   <script>alert(1)</script> Teacher · Westmore Oak...
 906      ~9       Nov 30   </script><img src=x onerror=alert(1)> & "quote"...
When you apply for one, note it by its number:
    python edtrawl.py applied 901
```

#### 9 logbook hostile (piped, stdin=/dev/null)
args: logbook  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 80
```
Logbook
This week: looked at 5, kept 4, applied to 1.
Since Nov 17: looked at 5, kept 4, applied to 1.
Nov 17  kept     Math Teacher RED · Westmore Oaks K-8
Nov 17  applied  Teacher evil gnihsilbup here · Westmore Oaks K-8
Nov 17  tossed    · Westmore Oaks K-8
Nov 17  kept     <script>alert(1)</script> Teacher · Westmore Oaks K-8
Nov 17  kept     </script><img src=x onerror=alert(1)> & "quote" 'q' · Westmore
Oaks K-8
```

#### 9 hostile deck: skip through all
pty: drive2 s9 90 s s s s s s s q --
```
RAW: esc codes: 138 | max visible line width: 79 | non-ascii: ·─⛵ | replacement chars: 0 | '?' runs: 0
 Casting the net  <ESC>[36m⛵<ESC>[0m····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~<ESC>[36m⛵<ESC>[0m  71 of 71        
 Reading postings for school names  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~<ESC>[36m⛵<ESC>[0m  1 of 1     
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~<ESC>[36m⛵<ESC>[0m  64 of 64        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
<ESC>[36m    python edtrawl.py match --review<ESC>[0m
65 new jobs within range, nearest first.
<ESC>[36m ── 1 of 65 ───────────────────────────────────────────────────── closes Nov 29<ESC>[0m
<ESC>[1m Augmentative and Alternative Communication Specialist @ Special Education -<ESC>[0m
<ESC>[1m DEPT-62.1<ESC>[0m
 Site not listed · Sacramento City Unified
 Drive   ~4 to ~24 min across the district's 83 schools in range
 Pay     not listed
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 2 of 65 ─────────────────────────────────────────────── closes Thu (3 days)<ESC>[0m
<ESC>[1m Teacher, Special Education, Preschool SDC MMLE @ Washington ELEM-113<ESC>[0m
 Washington Elementary · Sacramento City Unified
 Drive   ~4 min there · ~5 home if you leave by 3:30   (about 50 min a week)
 School  362 students, shrinking (-4% in a year) · 19 teachers · Title I
 Pay     not listed
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mm<ESC>[0m]ore about the school   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 3 of 65 ───────────────────────────────────────────────────────────────────<ESC>[0m
<ESC>[1m Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)<ESC>[0m
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 4 of 65 ───────────────────────────────────────────────────── closes Nov 30<ESC>[0m
<ESC>[1m Math Teacher RED<ESC>[0m
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     Pay $50k
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mm<ESC>[0m]ore about the school   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 5 of 65 ───────────────────────────────────────────────────── closes Nov 30<ESC>[0m
<ESC>[1m Teacher evil gnihsilbup here<ESC>[0m
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     $1000
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mm<ESC>[0m]ore about the school   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 6 of 65 ───────────────────────────────────────────────────── closes Nov 30<ESC>[0m
<ESC>[1m LONG Teacher of Very Long Titles Teacher of Very Long Titles Teacher of Very<ESC>[0m
<ESC>[1m Long Titles Teacher of Very Long Titles Teacher of Very Long Titles Teacher...<ESC>[0m
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     $999999999999999999999999999999999999999999999999999999999999999999999
         9999999999999999999999999999999999999999999999999999999999999999999...
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mm<ESC>[0m]ore about the school   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 7 of 65 ───────────────────────────────────────────────────── closes Nov 30<ESC>[0m
<ESC>[1m <ESC>[0m
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     not listed
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mm<ESC>[0m]ore about the school   [<ESC>[36mq<ESC>[0m]uit
 > 
s
Skipped. It'll come up again next time.
<ESC>[36m ── 8 of 65 ───────────────────────────────────────────────────── closes Nov 30<ESC>[0m
<ESC>[1m <script>alert(1)</script> Teacher<ESC>[0m
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     <script>alert(3)</script>
[<ESC>[36mk<ESC>[0m]eep   [<ESC>[36mt<ESC>[0m]oss   [<ESC>[36ms<ESC>[0m]kip   [<ESC>[36mo<ESC>[0m]pen posting   [<ESC>[36mm<ESC>[0m]ore about the school   [<ESC>[36mq<ESC>[0m]uit
 > 
q
Stopping here: skipped 7. The other 58 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(10.4, 's'), (10.4, 's'), (10.4, 's'), (10.4, 's'), (10.4, 's'), (10.4, 's'), (10.4, 's'), (10.4, 'q')] | total 10.5 s]

#### 10 drove 'Westmore' 0
pty: drive2 s10 20 -- drove Westmore -- 0
```
Type the minutes as a number from 1 to 240.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 10 drove 'Westmore' 500
pty: drive2 s10 20 -- drove Westmore -- 500
```
Type the minutes as a number from 1 to 240.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 10 drove 'Westmore' -5
pty: drive2 s10 20 -- drove Westmore -- -5
```
Type the minutes as a number from 1 to 240.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 10 drove 'Westmore' abc
pty: drive2 s10 20 -- drove Westmore -- abc
```
usage: edtrawl.py drove [-h] [--db DB] [--config CONFIG] [--plain]
                        [--no-emoji] [--pm]
                        school minutes
edtrawl.py drove: error: argument minutes: invalid float value: 'abc'


[exit: 2 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 10 drove 'Westmore' 25
pty: drive2 s10 20 -- drove Westmore -- 25
```
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~23 to ~46 min.
That's far from my estimate, so I adjusted as far as I allow (half or double).
If that day's traffic was unusual, a typical day's time will fit better.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 10 drove Westmore -5 (no --)
$ ./run.sh s10 drove Westmore -5
```
Type the minutes as a number from 1 to 240.
[exit 1]
```

#### 10 drove (no args)
$ ./run.sh s10 drove
```
usage: edtrawl.py drove [-h] [--db DB] [--config CONFIG] [--plain]
                        [--no-emoji] [--pm]
                        school minutes
edtrawl.py drove: error: the following arguments are required: school, minutes
[exit 2]
```

#### 10 drove nonexistent 20
$ ./run.sh s10 drove Zzyzx 20
```
I couldn't find a school called "Zzyzx". Check the spelling, or use the
school's 14-digit code.
[exit 1]
```

#### 10 drove far-away school (Fresno High) 20
$ ./run.sh s10 drove Fresno High 20
```
I couldn't find a school called "Fresno High". Check the spelling, or use the
school's 14-digit code.
[exit 1]
```

#### 10 drove many matches 'Elementary' (non-tty)
$ ./run.sh s10 drove Elementary 20
```
More than one school matches "Elementary". Which one?
  [1] Abraham Lincoln Elementary, Sacramento
  [2] Albert Schweitzer Elementary, Carmichael
  [3] Anderson (Linford L.) Elementary, Dixon
  [4] Anna Kirchgater Elementary, Sacramento
  [5] Antelope Creek Elementary, Rocklin
  [6] Antelope Meadows Elementary, Antelope
  [7] Arlene Hein Elementary, Elk Grove
  [8] Arlington Heights Elementary, Citrus Heights
  [9] Arnold Adreani Elementary, Sacramento
Showing the first 9. Add more of the name to narrow it down.
[exit 1]
```

#### 10 drove 'Elementary' 20 pty: pick list, abc, 0, 99, 1
pty: drive2 s10 20 abc -- drove Elementary 20
```
More than one school matches "Elementary". Which one?
  [1] Abraham Lincoln Elementary, Sacramento
  [2] Albert Schweitzer Elementary, Carmichael
  [3] Anderson (Linford L.) Elementary, Dixon
  [4] Anna Kirchgater Elementary, Sacramento
  [5] Antelope Creek Elementary, Rocklin
  [6] Antelope Meadows Elementary, Antelope
  [7] Arlene Hein Elementary, Elk Grove
  [8] Arlington Heights Elementary, Citrus Heights
  [9] Arnold Adreani Elementary, Sacramento
Showing the first 9. Add more of the name to narrow it down.
Type its number, or press Enter to skip.
 > 
abc


[exit: 1 ]
[answers sent at seconds: [(0.1, 'abc')] | total 0.2 s]
```

#### 10 drove 'Elementary' pick 1
pty: drive2 s10 20 1 -- drove Elementary 20
```
More than one school matches "Elementary". Which one?
  [1] Abraham Lincoln Elementary, Sacramento
  [2] Albert Schweitzer Elementary, Carmichael
  [3] Anderson (Linford L.) Elementary, Dixon
  [4] Anna Kirchgater Elementary, Sacramento
  [5] Antelope Creek Elementary, Rocklin
  [6] Antelope Meadows Elementary, Antelope
  [7] Arlene Hein Elementary, Elk Grove
  [8] Arlington Heights Elementary, Citrus Heights
  [9] Arnold Adreani Elementary, Sacramento
Showing the first 9. Add more of the name to narrow it down.
Type its number, or press Enter to skip.
 > 
1
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~23 to ~21 min.


[exit: 0 ]
[answers sent at seconds: [(0.1, '1')] | total 0.2 s]
```

#### 10 drove Westmore 20
$ ./run.sh s10 drove Westmore 20
```
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~23 to ~46 min.
That's far from my estimate, so I adjusted as far as I allow (half or double).
If that day's traffic was unusual, a typical day's time will fit better.
[exit 0]
```

#### 10 drove Westmore 10
$ ./run.sh s10 drove Westmore 10
```
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~46 to ~27 min.
[exit 0]
```

#### 10 drove Westmore 20
$ ./run.sh s10 drove Westmore 20
```
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~27 to ~46 min.
That's far from my estimate, so I adjusted as far as I allow (half or double).
If that day's traffic was unusual, a typical day's time will fit better.
[exit 0]
```

#### 10 drove Westmore 10
$ ./run.sh s10 drove Westmore 10
```
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~46 to ~27 min.
[exit 0]
```

#### 10 drove Westmore 15 --pm
$ ./run.sh s10 drove Westmore 15 --pm
```
Thanks. I've scaled every afternoon estimate to match: the typical school near
you went from ~29 to ~41 min.
[exit 0]
```

#### 10 drove 14-digit code not in range
$ ./run.sh s10 drove 01611766001234 20
```
I couldn't find a school called "01611766001234". Check the spelling, or use
the school's 14-digit code.
[exit 1]
```

#### 10 drove empty name
$ ./run.sh s10 drove  20
```
More than one school matches "". Which one?
  [1] A. M. Winn Waldorf-Inspired, Sacramento
  [2] Abraham Lincoln Elementary, Sacramento
  [3] Adelante High (Continuation), Roseville
  [4] Albert Einstein Middle, Sacramento
  [5] Albert Schweitzer Elementary, Carmichael
  [6] Alice Birney Waldorf-Inspired, Sacramento
  [7] Alpha Technology Middle, Elverta
  [8] American Lakes, Sacramento
  [9] American Legion High (Continuation), Sacramento
Showing the first 9. Add more of the name to narrow it down.
[exit 1]
```

#### 10 applied 99
$ ./run.sh s10 applied 99
```
I don't have a job numbered 99. Each keeper's number is at the start of its
line here:
    python edtrawl.py keepers
[exit 1]
```

#### 10 applied abc
$ ./run.sh s10 applied abc
```
usage: edtrawl.py applied [-h] [--db DB] [--config CONFIG] [--plain]
                          [--no-emoji]
                          posting
edtrawl.py applied: error: argument posting: invalid int value: 'abc'
[exit 2]
```

#### 10 applied 2293501 x2
$ ./run.sh s10 applied 2293501
```
Marked as applied: Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1.
First one in the logbook. That's the hard part done.
[exit 0]
```

#### 10 applied 2293501 again
$ ./run.sh s10 applied 2293501
```
Marked as applied: Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1.
[exit 0]
```

#### 10 applied a tossed job
$ bash -c sqlite3 s10/edtrawl.db "select posting_id from job_marks where status='tossed'"
```
2295139
```

#### 11 ^C at home question
pty: drive2 s11a 20 x --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,946 of 9,946    
9,946 schools loaded from the California Department of Education, 2025-26.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,982 of 9,982    
9,982 schools loaded from the California Department of Education, 2024-25.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > ^CStopped. Nothing already saved is lost.


[exit: 130 ]
[answers sent at seconds: [(4.0, 'x'), (4.0, '^C')] | total 4.1 s]
```

#### 11 ^C at radius question (home already saved?)
pty: drive2 s11a 20 38.577,-121.495 x --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
38.577,-121.495
Home is set.
Step 2 of 4 · Schools near you
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > ^CStopped. Nothing already saved is lost.


[exit: 130 ]
[answers sent at seconds: [(0.1, '38.577,-121.'), (0.1, 'x'), (0.1, '^C')] | total 0.2 s]
```

#### 11 rerun after ^C at radius
pty: drive2 s11a 30  o  --
```
 Working out drive times  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  472 of 472           
Job listings come from edjoin.org. I ask it for teaching jobs in the counties
around you, and read a few postings to find the school. Your home isn't sent.
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.3 s]
```

#### 11 ^C during drive-time (osrm stalled)
pty: drive2 s11b 20 --
```
^CStopped. Nothing already saved is lost.


[exit: 130 ]
[answers sent at seconds: [(2.1, '^C@time')] | total 2.1 s]
```

#### 11 ^C during fetch (edjoin stalled)
pty: drive2 s11a 20 --
```
Job listings come from edjoin.org. I ask it for teaching jobs in the counties
around you, and read a few postings to find the school. Your home isn't sent.
^CStopped. Nothing already saved is lost.


[exit: 130 ]
[answers sent at seconds: [(2.3, '^C@time')] | total 2.3 s]
```

#### 11 ^C on third card after keep, toss
pty: drive2 s11c 40 k t s x --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
k
Kept.
 ── 2 of 56 ───────────────────────────────────────────────────── closes Nov 25
 2026-2027 Intervention Specialist- Westmore Oaks
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     M.A./M.S- $1,250 annual stipend+ $1,250 for doctorate/ BCLAD- $1,250
         annual stipend. Year for year match on verifiable experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > 
t
Tossed.
 ── 3 of 56 ───────────────────────────────────────────────────────────────────
 Early Childhood Development - Site Supervisor (Head Start)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     + $1,800 Stipend + $2,000 Master's Degree Stipend, $2,000 Doctorate
         Stipend.** Final placement determined upon receipt of official seal...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
s
Skipped. It'll come up again next time.
 ── 4 of 56 ───────────────────────────────────────────────────────────────────
 RSP Teacher - 2026/2027 School Year
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > ^CStopping here: kept 1, tossed 1, skipped 1. The other 53 jobs will be here next
time.


[exit: 130 ]
[answers sent at seconds: [(8.4, 'k'), (8.5, 't'), (8.5, 's'), (8.5, 'x'), (8.5, '^C')] | total 8.5 s]
```

#### 11 next run
pty: drive2 s11c 40 q --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  63 of 63        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
54 new jobs within range, nearest first.
 ── 1 of 54 ───────────────────────────────────────────────────────────────────
 Early Childhood Development - Site Supervisor (Head Start)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     + $1,800 Stipend + $2,000 Master's Degree Stipend, $2,000 Doctorate
         Stipend.** Final placement determined upon receipt of official seal...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 54 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'q')] | total 8.4 s]
```

#### 11 EOF (^D) on third card
pty: drive2 s11d 40 k t ^D --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
k
Kept.
 ── 2 of 56 ───────────────────────────────────────────────────── closes Nov 25
 2026-2027 Intervention Specialist- Westmore Oaks
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     M.A./M.S- $1,250 annual stipend+ $1,250 for doctorate/ BCLAD- $1,250
         annual stipend. Year for year match on verifiable experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > 
t
Tossed.
 ── 3 of 56 ───────────────────────────────────────────────────────────────────
 Early Childhood Development - Site Supervisor (Head Start)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     + $1,800 Stipend + $2,000 Master's Degree Stipend, $2,000 Doctorate
         Stipend.** Final placement determined upon receipt of official seal...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 4 of 56 ───────────────────────────────────────────────────────────────────
 RSP Teacher - 2026/2027 School Year
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 

[exit: still running (killed) ]
[answers sent at seconds: [(8.4, 'k'), (8.5, 't'), (8.5, '^D'), (8.5, '^D')] | total 8.5 s]
```

#### 11 EOF repeated mid-deck
pty: drive2 s11d 60 k ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D ^D --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
k
Kept.
 ── 2 of 56 ───────────────────────────────────────────────────── closes Nov 25
 2026-2027 Intervention Specialist- Westmore Oaks
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     M.A./M.S- $1,250 annual stipend+ $1,250 for doctorate/ BCLAD- $1,250
         annual stipend. Year for year match on verifiable experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 3 of 56 ───────────────────────────────────────────────────────────────────
 Early Childhood Development - Site Supervisor (Head Start)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     + $1,800 Stipend + $2,000 Master's Degree Stipend, $2,000 Doctorate
         Stipend.** Final placement determined upon receipt of official seal...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 4 of 56 ───────────────────────────────────────────────────────────────────
 RSP Teacher - 2026/2027 School Year
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Annual Salary: $68,500 - $133,534 + $2,000 Master's Degree Stipend,
         $2,000 Doctorate Stipend. Final placement determined upon receipt o...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 5 of 56 ───────────────────────────────────────────────────────────────────
 Teacher - ELA - (1.0 FTE)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Final placement determined upon receipt of official sealed transcripts
         and verification of prior contracted teaching experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 6 of 56 ───────────────────────────────────────────────────────────────────
 Teacher - 7th/8th Science DLI Teacher
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     Final placement determined upon receipt of official sealed transcripts
         and verification of prior contracted teaching experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 7 of 56 ─────────────────────────────────────────────── closes Thu (3 days)
 Teacher, Elementary, 3rd Grade @ Theodore Judah ELEM-114
 Theodore Judah Elementary · Sacramento City Unified
 Drive   ~11 min there · ~11 home if you leave by 3:30   (about 2 hrs a week)
 School  477 students, shrinking (-2% in a year) · 22 teachers
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 8 of 56 ─────────────────────────────────────────────── closes Wed (2 days)
 Teacher, Itinerant - Deaf & Hard of Hearing, Special Education, Vacancy 27-86
 Site not listed · Yolo County Office of Education
 Drive   ~14 to ~37 min across the district's 4 schools in range
 Pay     Class 0-V ** / MA stipend: $1,500 annually. SPEAE stipend: $3,000
         annually. Stipends are prorated based on start date and FTE.
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 9 of 56 ───────────────────────────────────────────────────── closes Nov 29
 ECE Content Specialist - Education at Marvin Marshall (PC #: 32158 / Job ID#:
 8859)
 Site not listed · San Juan Unified
 Drive   ~14 to ~41 min across the district's 76 schools in range
 Pay     Placement on the ECE Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 10 of 56 ──────────────────────────────────────────────────────────────────
 Secondary Teacher Math Intervention and Reading Intervention 1.0 FTE at
 Barrett (PC #: 36537/ Job ID# 8014) ***$60,000 - $126,000/annually***
 Site not listed · San Juan Unified
 Drive   ~14 to ~41 min across the district's 76 schools in range
 Pay     Placement on the Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 11 of 56 ──────────────────────────────────────────────────────────────────
 Special Education Teacher **Sign on Bonus $16K**
 Marconi Learning Academy · Robla Elementary
 Drive   ~14 min there · ~15 home if you leave by 3:30   (about 2.5 hrs a week)
 School  438 students, shrinking (-6% in a year) · 18 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 12 of 56 ──────────────────────────────────────────────────────────────────
 Special Education Teacher **Sign on Bonus $16K**
 Marconi Learning Academy · Robla Elementary
 Drive   ~14 min there · ~15 home if you leave by 3:30   (about 2.5 hrs a week)
 School  438 students, shrinking (-6% in a year) · 18 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 13 of 56 ────────────────────────────────────────────────── closes tomorrow
 Teacher, Elementary, 6th Grade @ Nicholas ELEM-28.4
 Nicholas Elementary · Sacramento City Unified
 Drive   ~15 min there · ~15 home if you leave by 3:30   (about 2.5 hrs a week)
 School  534 students, growing (+11% in a year) · 23 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 14 of 56 ──────────────────────────────────────────────────── closes Jan 31
 Learning Recovery Emgercy Block Grant Elementary Lead Teacher
 Yav Pem Suab Academy - Preparing for the Future Charter
 Sacramento City Unified
 Drive   ~14 min there · ~16 home if you leave by 3:30   (about 2.5 hrs a week)
 School  464 students, shrinking (-3% in a year) · 22 teachers · Title I
 Pay     Experience Placement - Entering teachers will be granted credit for a
         maximum of 10 years (*) teaching only experience. Experience must b...
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 15 of 56 ──────────────────────────────────────────────────────────────────
 SDC Teacher- Mild/Moderate Bridgeway Island Elementary 2026-2027 ($5000
 Signing Bonus)
 Bridgeway Island K-8 School · Washington Unified
 Drive   ~16 min there · ~17 home if you leave by 3:30   (about 3 hrs a week)
 School  1,029 students, shrinking (-3% in a year) · 51 teachers · Title I
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1265 annual stipend+ $1,265
         for doctorate/ BCLAD- $1,265 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 16 of 56 ────────────────────────────────────────────── closes Thu (3 days)
 Teacher, Resource, Special Education @ Will C. Wood SEC-113
 Will C. Wood Middle · Sacramento City Unified
 Drive   ~16 min there · ~17 home if you leave by 3:30   (about 3 hrs a week)
 School  826 students, growing (+21% in a year) · 42 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 17 of 56 ──────────────────────────────────────────────────────────────────
 RESOURCE TEACHER - SPECIAL EDUCATION - MILD/ MOD (Special Education
 Department)
 Site not listed · Elk Grove Unified
 Drive   ~17 to ~45 min across the district's 69 schools in range
 Pay     See Salary Schedule below.
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 18 of 56 ────────────────────────────────────────────── closes Fri (4 days)
 50% FTE - K-8 Education Specialist Mild/Mod, 2026/27 (Westlake Charter,
 Natomas)
 Westlake Charter · Natomas Unified
 Drive   ~15 min there · ~18 home if you leave by 3:30   (about 2.5 hrs a week)
 School  1,492 students, steady (same as a year before) · 70 teachers
 Pay     Placement on Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 19 of 56 ────────────────────────────────────────────── closes Fri (4 days)
 50% FTE - K-8 Education Specialist Extensive Support Needs (ESN), 2026/27
 (Westlake Charter, Natomas)
 Westlake Charter · Natomas Unified
 Drive   ~15 min there · ~18 home if you leave by 3:30   (about 2.5 hrs a week)
 School  1,492 students, steady (same as a year before) · 70 teachers
 Pay     Placement on Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 20 of 56 ────────────────────────────────────────────── closes Thu (3 days)
 Teacher, Special Education, Preschool @ Elder Creek ELEM-112
 Elder Creek Elementary · Sacramento City Unified
 Drive   ~17 min there · ~19 home if you leave by 3:30   (about 3 hrs a week)
 School  693 students, shrinking (-3% in a year) · 32 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 21 of 56 ──────────────────────────────────────────────────────────────────
 Teacher (3rd Grade) @ Higher Learning Academy
 Higher Learning Academy · Twin Rivers Unified
 Drive   ~17 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  501 students, shrinking (-3% in a year) · 18 teachers · Title I
 Pay     Health Benefits for single coverage paid by employer, health includes:
         medical, dental, vision & life. CalSTRS Retirement & TSA Options
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 22 of 56 ──────────────────────────────────────────────────────────────────
 Teacher (Transitional Kindergarten) @ Higher Learning Academy (HLA)
 Higher Learning Academy · Twin Rivers Unified
 Drive   ~17 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  501 students, shrinking (-3% in a year) · 18 teachers · Title I
 Pay     Health Benefits for single coverage paid by employer, health includes:
         medical, dental, vision & life. CalSTRS Retirement & TSA Options
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 23 of 56 ──────────────────────────────────────────────────────────────────
 RSP Teacher *High Demand Bonus $4000* (Specialist, 9th-12th Grade,) @ Futures
 High School
 Futures High · Twin Rivers Unified
 Drive   ~17 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  394 students, shrinking (-16% in a year) · 22 teachers · Title I
 Pay     $4,000 High Demand Stipend Annually; Health Benefits for single
         coverage paid by employer, health includes: medical, dental, vision...
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 24 of 56 ──────────────────────────────────────────────────────────────────
 RSP Teacher *High Demand Bonus $4000* (Specialist, Mild/Mod, TK-8th Grade) @
 Higher Learning Academy (HLA)
 Higher Learning Academy · Twin Rivers Unified
 Drive   ~17 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  501 students, shrinking (-3% in a year) · 18 teachers · Title I
 Pay     $4,000 High Demand Stipend Annually; Health Benefits for single
         coverage paid by employer, health includes: medical, dental, vision...
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 25 of 56 ──────────────────────────────────────────────────────────────────
 Teacher (4th Grade) @ Higher Learning Academy
 Higher Learning Academy · Twin Rivers Unified
 Drive   ~17 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  501 students, shrinking (-3% in a year) · 18 teachers · Title I
 Pay     Health Benefits for single coverage paid by employer, health includes:
         medical, dental, vision & life. CalSTRS Retirement & TSA Options
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 26 of 56 ──────────────────────────────────────────────────────────────────
 Teacher (TK-5th Grade, Spanish) @ Higher Learning Academy
 Higher Learning Academy · Twin Rivers Unified
 Drive   ~17 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  501 students, shrinking (-3% in a year) · 18 teachers · Title I
 Pay     Health Benefits for single coverage paid by employer, health includes:
         medical, dental, vision & life. CalSTRS Retirement & TSA Options
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 27 of 56 ──────────────────────────────────────────────────────────────────
 RSP Teacher *High Demand Bonus $4000* (Specialist, Mild/Mod, TK-8th Grade) @
 Gateway International School (GIS)
 Gateway International · San Juan Unified
 Drive   ~19 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  660 students, growing (+5% in a year) · 25 teachers · Title I
 Pay     $4,000 High Demand Stipend Annually; Health Benefits for single
         coverage paid by employer, health includes: medical, dental, vision...
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 28 of 56 ──────────────────────────────────────────────────────────────────
 RSP Teacher *High Demand Bonus $4000*(Specialist, Mod/Severe, TK-5th, Special
 Day Class Teacher) @ Gateway International School (GIS)
 Gateway International · San Juan Unified
 Drive   ~19 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  660 students, growing (+5% in a year) · 25 teachers · Title I
 Pay     $4,000 High Demand Stipend Annually; Health Benefits for single
         coverage paid by employer, health includes: medical, dental, vision...
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 29 of 56 ──────────────────────────────────────────────────────────────────
 Teacher (TK-5th Grade, Russian) @ Gateway International School
 Gateway International · San Juan Unified
 Drive   ~19 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  660 students, growing (+5% in a year) · 25 teachers · Title I
 Pay     Health Benefits for single coverage paid by employer, health includes:
         medical, dental, vision & life. CalSTRS Retirement & TSA Options
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 30 of 56 ──────────────────────────────────────────────────────────────────
 Teacher (TK-5th Grade, Spanish) @ Gateway International School
 Gateway International · San Juan Unified
 Drive   ~19 min there · ~20 home if you leave by 3:30   (about 3 hrs a week)
 School  660 students, growing (+5% in a year) · 25 teachers · Title I
 Pay     Health Benefits for single coverage paid by employer, health includes:
         medical, dental, vision & life. CalSTRS Retirement & TSA Options
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 31 of 56 ──────────────────────────────────────────────────────────────────
 RSP Teacher *High Demand Bonus $4000*(Specialist, Mild/Mod, TK-8th Grade) @
 Community Outreach Academy (COA Elementary and Middle school)
 Community Outreach Academy · Twin Rivers Unified
 Drive   ~21 min there · ~22 home if you leave by 3:30   (about 3.5 hrs a week)
 School  1,894 students, shrinking (-2% in a year) · 91 teachers · Title I
 Pay     $4,000 High Demand Stipend Annually; Health Benefits for single
         coverage paid by employer, health includes: medical, dental, vision...
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 32 of 56 ──────────────────────────────────────────────────────────────────
 Instructor for Teacher Intern Program
 Site not listed · Davis Joint Unified
 Drive   ~23 to ~40 min across the district's 16 schools in range
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 33 of 56 ──────────────────────────────────────────────────────────────────
 RESOURCE TEACHER, SPECIAL EDUCATION - MODERATE/SEVERE (MS) or EXTENSIVE
 SUPPORT NEEDS (ESN) Eligibility Pool (Prairie Elementary School)
 Prairie Elementary · Elk Grove Unified
 Drive   ~21 min there · ~23 home if you leave by 3:30   (about 3.5 hrs a week)
 School  839 students, shrinking (-2% in a year) · 44 teachers · Title I
 Pay     See Salary Schedule below.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 34 of 56 ──────────────────────────────────────────────────────────────────
 Science Teacher (Grade 7-9) 1.0 FTE, 184 Days, 2026-2027 (Begins November 30,
 2026) School Year, Harper Junior High School
 Frances Ellen Watkins Harper Junior High · Davis Joint Unified
 Drive   ~21 min there · ~23 home if you leave by 3:30   (about 3.5 hrs a week)
 School  532 students, steady (same as a year before) · 31 teachers · Title I
 Pay     Will give credit up to 20 years of Teaching Experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 35 of 56 ──────────────────────────────────────────────────────────────────
 Homeschool Educational Consultant - Homeschool K-5th Grades - (0.5 FTE)
 *TEMPORARY* 2026/2027 At-Will - Folsom Cordova Community Charter Homeschool
 Site not listed · Folsom-Cordova Unified
 Drive   ~24 to ~43 min across the district's 28 schools in range
 Pay     See Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 36 of 56 ──────────────────────────────────────────────────────────────────
 RESOURCE TEACHER - SPECIAL EDUCATION - MILD/ MOD (Edward Harris, Jr. Middle
 School)
 Edward Harris, Jr. Middle · Elk Grove Unified
 Drive   ~23 min there · ~24 home if you leave by 3:30   (about 4 hrs a week)
 School  1,250 students, growing (+5% in a year) · 59 teachers · Title I
 Pay     See Salary Schedule below.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 37 of 56 ──────────────────────────────────────────────────── closes Nov 23
 ELEMENTARY 6TH GRADE TEACHER (Marion Mix Elementary School)
 Marion Mix Elementary · Elk Grove Unified
 Drive   ~24 min there · ~25 home if you leave by 3:30   (about 4 hrs a week)
 School  751 students, growing (+2% in a year) · 39 teachers · Title I
 Pay     See Salary Schedule #10 Link below.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 38 of 56 ──────────────────────────────────────────────────────────────────
 Special Education Moderate/Severe Teacher (1.0 FTE) 2026/2027 *$10,000 SIGNING
 BONUS* - Cordova High School
 Cordova High · Folsom-Cordova Unified
 Drive   ~26 min there · ~27 home if you leave by 3:30   (about 4.5 hrs a week)
 School  2,043 students, growing (+5% in a year) · 110 teachers · Title I
 Pay     See Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 39 of 56 ──────────────────────────────────────────────────────────────────
 Physical Education Teacher (1.0 FTE) *TEMPORARY* 2026/2027 - Cordova High
 School
 Cordova High · Folsom-Cordova Unified
 Drive   ~26 min there · ~27 home if you leave by 3:30   (about 4.5 hrs a week)
 School  2,043 students, growing (+5% in a year) · 110 teachers · Title I
 Pay     See Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 40 of 56 ───────────────────────────────────────────────────── closes Dec 4
 Special Education Teacher (Learning Resource) Intern Candidates May Apply
 Site not listed · Dry Creek Joint Elementary
 Drive   ~27 to ~40 min across the district's 9 schools in range
 Pay     May be granted year for year in accordance with the Dry Creek JESD
         Teacher Annual Salary Schedule 25-26 (per Article 24 - Salary Sched...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 41 of 56 ──────────────────────────────────────────────────────────────────
 English Teacher [Temporary] @ Antelope High School (Spring 2026-27)
 Antelope High · Roseville Joint Union High
 Drive   ~26 min there · ~28 home if you leave by 3:30   (about 4.5 hrs a week)
 School  1,781 students, shrinking (-2% in a year) · 87 teachers · Title I
 Pay     Appropriate placement on the teacher salary schedule. Year-for-year
         credit for previous full-time, fully credentialed teaching experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 42 of 56 ──────────────────────────────────────────────────────────────────
 Biology Teacher (NGSS) [Temporary] @ Antelope High School (2026-27)
 Antelope High · Roseville Joint Union High
 Drive   ~26 min there · ~28 home if you leave by 3:30   (about 4.5 hrs a week)
 School  1,781 students, shrinking (-2% in a year) · 87 teachers · Title I
 Pay     Appropriate placement on the teacher salary schedule. Year-for-year
         credit for previous full-time, fully credentialed teaching experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 43 of 56 ──────────────────────────────────────────────────────────────────
 PE Teacher 6/7/8 [1.0 FTE] at Will Rogers Middle School (PC #: 6774, 3605/ Job
 ID# 8001) ***$60,000 - $126,000/annually***
 Will Rogers Middle · San Juan Unified
 Drive   ~25 min there · ~28 home if you leave by 3:30   (about 4.5 hrs a week)
 School  570 students, steady (+1% in a year) · 34 teachers · Title I
 Pay     Placement on the Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 44 of 56 ──────────────────────────────────────────────────────────────────
 SPED MOD/SEVERE K/12TH TEACHER [1.0 FTE] at Barrett Middle Schools (PC #
 28207/ Job ID# 8342) ***$60,000 - $126,000/annually, plus $5K - $14K...
 John Barrett Middle · San Juan Unified
 Drive   ~26 min there · ~28 home if you leave by 3:30   (about 4.5 hrs a week)
 School  849 students, growing (+6% in a year) · 36 teachers
 Pay     Placement on the Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 45 of 56 ──────────────────────────────────────────────────────────────────
 Special Education Teacher - Extensive Supports Needs - Dudley Elementary
 Arthur S. Dudley Elementary · Center Joint Unified
 Drive   ~30 min there · ~32 home if you leave by 3:30   (about 5 hrs a week)
 School  520 students, steady (same as a year before) · 29 teachers · Title I
 Pay     *Intern teachers' salaries will be deducted by $2,698.96 annually to
         pay the mentor stipend.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 46 of 56 ──────────────────────────────────────────────────────────────────
 SPED Mod/Severe Teacher [1.0 FTE] at Bella Vista High School (PC #: 3964/ Job
 ID 8343) ***$60,000 - $126,000/annually, plus $5K - $14K stipends!
 Bella Vista High · San Juan Unified
 Drive   ~30 min there · ~32 home if you leave by 3:30   (about 5 hrs a week)
 School  1,909 students, shrinking (-2% in a year) · 82 teachers
 Pay     Placement on the Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 47 of 56 ────────────────────────────────────────────────── closes tomorrow
 ELEMENTARY 1ST GRADE TEACHER (Carroll Elementary School)
 Carroll Elementary · Elk Grove Unified
 Drive   ~30 min there · ~32 home if you leave by 3:30   (about 5 hrs a week)
 School  876 students, growing (+3% in a year) · 44 teachers
 Pay     EGEA Salary Schedule #10. See Salary Schedule Link below.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 48 of 56 ──────────────────────────────────────────────────────────────────
 RESOURCE TEACHER - SPECIAL EDUCATION - MILD/ MOD - GRADES TK/K- (Carroll
 Elementary School)
 Carroll Elementary · Elk Grove Unified
 Drive   ~30 min there · ~32 home if you leave by 3:30   (about 5 hrs a week)
 School  876 students, growing (+3% in a year) · 44 teachers
 Pay     See Salary Schedule below.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 49 of 56 ──────────────────────────────────────────────────────────────────
 RESOURCE TEACHER - SPECIAL EDUCATION - MODERATE/SEVERE (MS) or EXTENSIVE
 SUPPORT NEEDS (ESN) - GRADES TK/K- (Carroll Elementary School)
 Carroll Elementary · Elk Grove Unified
 Drive   ~30 min there · ~32 home if you leave by 3:30   (about 5 hrs a week)
 School  876 students, growing (+3% in a year) · 44 teachers
 Pay     See Salary Schedule below.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 50 of 56 ───────────────────────────────────────────────────── closes Dec 1
 Online Middle School Teacher (Intervention Specialist) - 2026/27 SY
 Visions In Education · San Juan Unified
 Drive   ~33 min there · ~34 home if you leave by 3:30   (about 5.5 hrs a week)
 School  7,877 students, growing (+6% in a year) · 328 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 51 of 56 ────────────────────────────────────────────── closes Wed (2 days)
 Math Teacher (0.20 FTE) *TEMPORARY / INTERNAL ONLY* 2026/2027 - Folsom High
 School
 Folsom High · Folsom-Cordova Unified
 Drive   ~35 min there · ~37 home if you leave by 3:30   (about 6 hrs a week)
 School  2,988 students, growing (+3% in a year) · 122 teachers
 Pay     See Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 52 of 56 ──────────────────────────────────────────────────────────────────
 3rd Grade Teacher
 American River Collegiate Academy · Sacramento County Office of Education
 Drive   ~35 min there · ~38 home if you leave by 3:30   (about 6 hrs a week)
 School  129 students, shrinking (-2% in a year) · 10 teachers
 Pay     Starting range $59,219- $85,855 ($1,500 2nd Adv Degree stipend; $1,500
         National Board Certification)
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 53 of 56 ──────────────────────────────────────────────────────────────────
 Special Education Moderate/Severe Teacher (1.0 FTE) 2026/2027 *$10,000 SIGNING
 BONUS* - Sutter Middle School
 Sutter Middle · Folsom-Cordova Unified
 Drive   ~37 min there · ~39 home if you leave by 3:30   (about 6.5 hrs a week)
 School  1,692 students, growing (+4% in a year) · 69 teachers
 Pay     See Certificated Salary Schedule
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 54 of 56 ──────────────────────────────────────────────────────────────────
 Math Teacher [Temporary] @ Woodcreek High School (Spring 2026-27)
 Woodcreek High · Roseville Joint Union High
 Drive   ~37 min there · ~39 home if you leave by 3:30   (about 6.5 hrs a week)
 School  1,969 students, steady (+1% in a year) · 91 teachers
 Pay     Appropriate placement on the teacher salary schedule. Year-for-year
         credit for previous full-time, fully credentialed teaching experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
 ── 55 of 56 ──────────────────────────────────────────────────────────────────
 Teacher, Visually Impaired Program (Certificated Position #1694)
 Site not listed · Placer County Office of Education
 Drive   ~40 min to the district's one school in range
 Pay     Placement based upon education and experience, Annual Stipends: MA/MA
         - $1,500, Bilingual - $500, Benefits Prorated Based on FTE
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > Skipped. It'll come up again next time.
 ── 56 of 56 ──────────────────────────────────────────────────────────────────
 Spanish Teacher - Cooley Middle School - 2026/2027
 Robert C. Cooley Middle · Roseville City
 Drive   ~40 min there · ~41 home if you leave by 3:30   (about 7 hrs a week)
 School  1,179 students, growing (+3% in a year) · 57 teachers
 Pay     Full Salary Range per Salary Schedule $64,337 - $129,105 (including
         MA&Doctorate stipend)
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > Skipped. It'll come up again next time.
That's the whole catch: kept 1, skipped 55.
Nothing else is new today, so you're done.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'k'), (8.4, '^D'), (8.4, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D'), (8.5, '^D')] | total 8.5 s]
```

#### 12 config.toml deleted, db kept: keepers
pty: drive2 s12a 30 -- keepers
```
No keepers yet. Press k on a job's card and it will wait here.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 config deleted: bare go
pty: drive2 s12a 30 q --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
q
I couldn't read that as an address, ZIP code or map position. A ZIP code is
five digits, like 93721; a map position looks like 36.74,-119.79.
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 

[exit: still running (killed) ]
[answers sent at seconds: [(0.1, 'q')] | total 0.1 s]
```

#### 12 db deleted, config kept: keepers
pty: drive2 s12b 30 -- keepers
```
No keepers yet. Press k on a job's card and it will wait here.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 db deleted: bare (config has home_key)
pty: drive2 s12b 60 --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,946 of 9,946    
9,946 schools loaded from the California Department of Education, 2025-26.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,982 of 9,982    
9,982 schools loaded from the California Department of Education, 2024-25.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 

[exit: still running (killed) ]
[answers sent at seconds: [] | total 4.0 s]
```

#### 12 config deleted: logbook / search
pty: drive2 s12a 30 -- logbook
```
Logbook
This week: looked at 2, kept 1, applied to 0.
Since Nov 16: looked at 2, kept 1, applied to 0.
Nov 16  kept     Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1 · Sacramento City Unified School District
Nov 16  tossed   Teacher, Special Education, Preschool SDC MMLE @ Washington
ELEM-113 · Washington Elementary


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]

#### 12 config deleted: search
pty: drive2 s12a 30 -- search
```
No teaching jobs are posted within 20 miles right now. To look again another
day:
    python edtrawl.py


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]

#### 12 config deleted: chart
pty: drive2 s12a 30 -- chart --no-open
```
There's no home set yet, so I can't measure any drives. This sets one up in a
few steps:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]

#### 12 config deleted: applied 2293501
pty: drive2 s12a 30 -- applied 2293501
```
Marked as applied: Augmentative and Alternative Communication Specialist @
Special Education - DEPT-62.1.
First one in the logbook. That's the hard part done.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]

#### 12 misspelt key
pty: drive2 s12c 30 -- keepers
```
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s12c/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 routing=google
pty: drive2 s12d 30 -- keepers
```
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s12d/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 config syntax broken
pty: drive2 s12e 30 -- keepers
```
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s12e/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 radius text
pty: drive2 s12f 30 -- commute
```
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s12f/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 radius -3
pty: drive2 s12g 30 -- commute
```
There are no public schools within -3 miles of that spot. Try a wider radius,
like -6.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 corrupt db
pty: drive2 s12h 30 -- keepers
```
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s12h/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 read-only folder+files: keepers
pty: drive2 s12r 30 -- keepers
```
Keepers: 1 job, soonest deadline first
 Number   Drive    Closes   Job
 2293501  ~4-24    Nov 29   Augmentative and Alternative Communication Speci...
When you apply for one, note it by its number:
    python edtrawl.py applied 2293501


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 read-only: applied
pty: drive2 s12r 30 -- applied 2293501
```
Traceback (most recent call last):
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 303, in main
    return COMMANDS[args.command](args, conn, cfg) or 0
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/flows.py", line 393, in applied
    first = _mark(conn, args.posting, "applied")
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/flows.py", line 51, in _mark
    conn.execute("INSERT INTO job_marks (posting_id, status, marked_on) VALUES (?, ?, ?) "
sqlite3.OperationalError: attempt to write a readonly database

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-287d-4927-86ce-4355720f397b/scratchpad/p2/nonet.py", line 38, in <module>
    sys.exit(edtrawl.main())
             ^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 312, in main
    ui.say("err_unexpected", path=str(_log_unexpected(e, args.db)))
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 288, in _log_unexpected
    with open(path, "a", encoding="utf-8") as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 13] Permission denied: '/tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-287d-4927-86ce-4355720f397b/scratchpad/p2/s12r/edtrawl-error.log'


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 read-only: chart
pty: drive2 s12r 30 -- chart --no-open
```
Traceback (most recent call last):
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 303, in main
    return COMMANDS[args.command](args, conn, cfg) or 0
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 182, in cmd_chart
    chart.write_chart(conn, cfg, str(out))
  File "/home/james/Claudorable/EdTrawl-Cla/chart.py", line 376, in write_chart
    with open(path, "w", encoding="utf-8") as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 13] Permission denied: '/tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-287d-4927-86ce-4355720f397b/scratchpad/p2/s12r/edtrawl-chart.html'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-287d-4927-86ce-4355720f397b/scratchpad/p2/nonet.py", line 38, in <module>
    sys.exit(edtrawl.main())
             ^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 312, in main
    ui.say("err_unexpected", path=str(_log_unexpected(e, args.db)))
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 288, in _log_unexpected
    with open(path, "a", encoding="utf-8") as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 13] Permission denied: '/tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-287d-4927-86ce-4355720f397b/scratchpad/p2/s12r/edtrawl-error.log'


[exit: 1 ]
[answers sent at seconds: [] | total 0.3 s]
```

#### 12 read-only dir only (files writable? db rw but dir ro)
pty: drive2 s12s 30 -- keepers
```
Keepers: 1 job, soonest deadline first
 Number   Drive    Closes   Job
 2293501  ~4-24    Nov 29   Augmentative and Alternative Communication Speci...
When you apply for one, note it by its number:
    python edtrawl.py applied 2293501


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 ro dir: applied
pty: drive2 s12s 30 -- applied 2293501
```
Traceback (most recent call last):
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 303, in main
    return COMMANDS[args.command](args, conn, cfg) or 0
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/flows.py", line 393, in applied
    first = _mark(conn, args.posting, "applied")
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/flows.py", line 51, in _mark
    conn.execute("INSERT INTO job_marks (posting_id, status, marked_on) VALUES (?, ?, ?) "
sqlite3.OperationalError: attempt to write a readonly database

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-287d-4927-86ce-4355720f397b/scratchpad/p2/nonet.py", line 38, in <module>
    sys.exit(edtrawl.main())
             ^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 312, in main
    ui.say("err_unexpected", path=str(_log_unexpected(e, args.db)))
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/james/Claudorable/EdTrawl-Cla/edtrawl.py", line 288, in _log_unexpected
    with open(path, "a", encoding="utf-8") as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 13] Permission denied: '/tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-287d-4927-86ce-4355720f397b/scratchpad/p2/s12s/edtrawl-error.log'


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 12 ro dir: bare go
pty: drive2 s12s 30 q --
```
This computer doesn't seem to be online, so I couldn't reach edjoin.org. Your
keepers and saved drive times are all still here. Once you're connected:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 13 keepers while another process holds the write lock (40s)
pty: drive2 s13b 60 -- keepers
```
Keepers: 1 job, soonest deadline first
 Number   Drive    Closes   Job
 2293501  ~4-24    Nov 29   Augmentative and Alternative Communication Speci...
When you apply for one, note it by its number:
    python edtrawl.py applied 2293501


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]

#### 13 applied while locked
pty: drive2 s13b 60 -- applied 2293501
```
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s13b/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 5.2 s]
```

#### 13 fetch from file while locked
pty: drive2 s13b 60 -- fetch --from-file /home/james/Claudorable/EdTrawl-Cla/tests/fixtures/edjoin_listing.json
```
Something unexpected went wrong, so I stopped. Nothing already saved is lost.
The details are in /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe42
7-287d-4927-86ce-4355720f397b/scratchpad/p2/s13b/edtrawl-error.log.


[exit: 1 ]
[answers sent at seconds: [] | total 5.2 s]
```

#### 14 odd answers on cards
pty: drive2 s14 60 keep TOSS s  yes ? help no next ok  quit --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
58 new jobs within range, nearest first.
 ── 1 of 58 ───────────────────────────────────────────────────── closes Nov 29
 Augmentative and Alternative Communication Specialist @ Special Education -
 DEPT-62.1
 Site not listed · Sacramento City Unified
 Drive   ~4 to ~24 min across the district's 83 schools in range
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
keep
Kept.
Your first keeper. It'll wait in your list, with its deadline, until you apply
or toss it.
 ── 2 of 58 ─────────────────────────────────────────────── closes Thu (3 days)
 Teacher, Special Education, Preschool SDC MMLE @ Washington ELEM-113
 Washington Elementary · Sacramento City Unified
 Drive   ~4 min there · ~5 home if you leave by 3:30   (about 50 min a week)
 School  362 students, shrinking (-4% in a year) · 19 teachers · Title I
 Pay     not listed
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > 
TOSS
Tossed.
 ── 3 of 58 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
s 
Skipped. It'll come up again next time.
 ── 4 of 58 ───────────────────────────────────────────────────── closes Nov 25
 2026-2027 Intervention Specialist- Westmore Oaks
 Westmore Oaks K-8 · Washington Unified
 Drive   ~8 min there · ~9 home if you leave by 3:30   (about 1.5 hrs a week)
 School  527 students, steady (-1% in a year) · 30 teachers · Title I
 Pay     M.A./M.S- $1,250 annual stipend+ $1,250 for doctorate/ BCLAD- $1,250
         annual stipend. Year for year match on verifiable experience.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > 
yes
Type one of these letters, then Enter: k, t, s, o, m, q.
 > 
?
Type one of these letters, then Enter: k, t, s, o, m, q.
 > 
help
Type one of these letters, then Enter: k, t, s, o, m, q.
 > 
no
Type one of these letters, then Enter: k, t, s, o, m, q.
 > 
next
Type one of these letters, then Enter: k, t, s, o, m, q.
 > 
ok
Opened the posting in your browser.
[k]eep   [t]oss   [s]kip   [o]pen posting   [m]ore about the school   [q]uit
 > 

Skipped. It'll come up again next time.
 ── 5 of 58 ───────────────────────────────────────────────────────────────────
 Early Childhood Development - Site Supervisor (Head Start)
 Site not listed · Twin Rivers Unified
 Drive   ~10 to ~28 min across the district's 52 schools in range
 Pay     + $1,800 Stipend + $2,000 Master's Degree Stipend, $2,000 Doctorate
         Stipend.** Final placement determined upon receipt of official seal...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
quit
Stopping here: kept 1, tossed 1, skipped 2. The other 54 jobs will be here next
time.
[40655:40655:1116/162957.777441:ERROR:chromium/extensions/browser/service_worker/service_worker_task_queue.cc:538] DidStartWorkerFail mpognobbkildjkofajifpdfhcoklimli: 18
[40655:40655:1116/163005.313499:ERROR:CONSOLE:1] "Uncaught (in promise) Error", source: chrome-extension://mpognobbkildjkofajifpdfhcoklimli/bundle.js (1)
[40655:40655:1116/163006.932451:ERROR:CONSOLE:1] "Uncaught (in promise) Error: The pipe has already been closed.", source: chrome-extension://mpognobbkildjkofajifpdfhcoklimli/bundle.js (1)
[40655:40655:1116/163007.507312:ERROR:CONSOLE:1] "Uncaught (in promise) Error: The pipe has already been closed.", source: chrome-extension://mpognobbkildjkofajifpdfhcoklimli/bundle.js (1)
[40655:40655:1116/163012.223652:ERROR:CONSOLE:1] "Uncaught (in promise) Error: The pipe has already been closed.", source: chrome-extension://mpognobbkildjkofajifpdfhcoklimli/bundle.js (1)


[exit: 0 ]
[answers sent at seconds: [(8.4, 'keep'), (8.4, 'TOSS'), (8.4, 's '), (8.4, 'yes'), (8.4, '?'), (8.4, 'help'), (8.4, 'no'), (8.4, 'next'), (8.4, 'ok'), (8.4, ''), (8.4, 'quit')] | total 60.2 s]
```

#### 3 Las Vegas in setup; radius Enter, Enter, 100, then NYC
pty: drive2 s3c 60 36.17,-115.14   100 --
```
Welcome to EdTrawl.
It finds California teaching jobs within driving distance of home and shows you
each new one once, so you can keep it or toss it. Setup is four short steps,
and you can change any answer later.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,946 of 9,946    
9,946 schools loaded from the California Department of Education, 2025-26.
 Loading California schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  9,982 of 9,982    
9,982 schools loaded from the California Department of Education, 2024-25.
Step 1 of 4 · Home port
Your street address is never saved; I keep only a spot rounded to about a city
block.
Where is home? Any one of these works:
    a street address    123 Main St, Fresno
    a ZIP code          93721
    a map position      36.74,-119.79
 > 
36.17,-115.14
Home is set.
Step 2 of 4 · Schools near you
How many miles from home should I look, as the crow flies? Press Enter for 20.
 > 

There are no public schools within 20 miles of that spot. Try a wider radius,
like 40.
How many miles from home should I look, as the crow flies? Press Enter for 40.
 > 

There are no public schools within 40 miles of that spot. Try a wider radius,
like 80.
How many miles from home should I look, as the crow flies? Press Enter for 80.
 > 
100
Within 100 miles of home, as the crow flies: 11 public schools in 3 districts.
The nearest is Death Valley High Academy, about 64.6 miles away.
Step 3 of 4 · Drive times
How should I work out drive times?
  [o]ffline: a formula on straight-line distance. Nothing leaves this computer,
    but it can't see bays, mountains or freeways.
  [r]oads: real road distances from a free OpenStreetMap routing server
    (router.project-osrm.org). It receives your home spot, rounded to about a
    city block, and the positions of schools near you. Nothing else.
Both add typical rush-hour traffic, and both are estimates. Offline or roads?
[o/r]
 > 

[exit: still running (killed) ]
[answers sent at seconds: [(4.1, '36.17,-115.1'), (4.1, ''), (4.2, ''), (4.2, '100')] | total 4.3 s]
```

#### 3 home NYC 40.7,-74
pty: drive2 s3d 20 -- home 40.7,-74
```
That spot is outside California, and EdTrawl only knows California schools.
Nothing was saved. Check the address, or try your ZIP code.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 home Las Vegas (existing db) then bare go
pty: drive2 s3d 20 -- home 36.17,-115.14
```
Home is set.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 bare go after Vegas
pty: drive2 s3d 20 q --
```
There are no public schools within 20 miles of that spot. Try a wider radius,
like 40.


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 3 keepers after Vegas
pty: drive2 s3d 20 -- keepers
```
Keepers: 1 job, soonest deadline first
 Number   Drive    Closes   Job
 2293501  -        Nov 29   Augmentative and Alternative Communication Speci...
When you apply for one, note it by its number:
    python edtrawl.py applied 2293501


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 14 fresh folder, bare, piped (piped, stdin=/dev/null)
args:   | exit 1 | ESC bytes: 0 | CR bytes: 0 | longest line: 78
```
Setup asks a few questions, so it needs a terminal window to type in. Open one
and run:
    python edtrawl.py
```

#### 14 fresh folder: search (piped, stdin=/dev/null)
args: search  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 76
```
No teaching jobs are posted within 20 miles right now. To look again another
day:
    python edtrawl.py
```

#### 14 fresh folder: keepers (piped, stdin=/dev/null)
args: keepers  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 62
```
No keepers yet. Press k on a job's card and it will wait here.
```

#### 14 fresh folder: logbook (piped, stdin=/dev/null)
args: logbook  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 68
```
Logbook
Nothing in the logbook yet. It fills in as you keep, toss and apply.
```

#### 14 fresh folder: fetch (piped, stdin=/dev/null)
args: fetch  | exit 1 | ESC bytes: 0 | CR bytes: 0 | longest line: 77
```
There's no home set yet, so I can't measure any drives. This sets one up in a
few steps:
    python edtrawl.py
```

#### 14 fresh folder: commute (piped, stdin=/dev/null)
args: commute  | exit 1 | ESC bytes: 0 | CR bytes: 0 | longest line: 77
```
There's no home set yet, so I can't measure any drives. This sets one up in a
few steps:
    python edtrawl.py
```

#### 14 fresh folder: chart (piped, stdin=/dev/null)
args: chart  | exit 1 | ESC bytes: 0 | CR bytes: 0 | longest line: 77
```
There's no home set yet, so I can't measure any drives. This sets one up in a
few steps:
    python edtrawl.py
```

#### 14 fresh folder: school Westmore (piped, stdin=/dev/null)
args: school Westmore  | exit 1 | ESC bytes: 0 | CR bytes: 0 | longest line: 74
```
I couldn't find a school called "Westmore". Check the spelling, or use the
school's 14-digit code.
```

#### 14 fresh folder: drove Westmore 20 (piped, stdin=/dev/null)
args: drove Westmore 20  | exit 1 | ESC bytes: 0 | CR bytes: 0 | longest line: 77
```
There's no home set yet, so I can't measure any drives. This sets one up in a
few steps:
    python edtrawl.py
```

#### 14 fresh folder: match --review (piped, stdin=/dev/null)
args: match --review  | exit 0 | ESC bytes: 0 | CR bytes: 0 | longest line: 21
```
Nothing is set aside.
```

#### 14 fresh folder: applied 5 (piped, stdin=/dev/null)
args: applied 5  | exit 1 | ESC bytes: 0 | CR bytes: 0 | longest line: 79
```
I don't have a job numbered 5. Each keeper's number is at the start of its line
here:
    python edtrawl.py keepers
```

#### 15 edjoin HTTP 403
pty: drive2 s15 30 -- fetch
```
edjoin.org turned the request away, so I stopped. Nothing you've already saved
is lost. Try again tomorrow:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 15 edjoin HTTP 429
pty: drive2 s15 30 -- fetch
```
edjoin.org asked me to slow down, so I stopped for now. Nothing you've already
saved is lost. Try again in a few hours:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 15 edjoin HTTP 500
pty: drive2 s15 30 -- fetch
```
edjoin.org isn't working properly right now, so I stopped. Nothing you've
already saved is lost. Try again later today:
    python edtrawl.py


[exit: 1 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 15 llm unreachable: match
pty: drive2 s15 60 -- match
```
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
The matching model at http://127.0.0.1:9/v1 didn't answer, so matching ran
without it. Nothing is lost; anything it would have helped with is in the
review list:
    python edtrawl.py match --review
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review


[exit: 0 ]
[answers sent at seconds: [] | total 0.4 s]
```

#### 15 match --review interactive: x, 9, n, 1
pty: drive2 s15b 30 x 9 n -- match --review
```
3 listings set aside. Under each are the closest names I found; 1.00 would be
identical.
OPTIONS FOR YOUTH  (2 jobs)
  [1] Options for Youth-San Juan  0.79
  [2] Fortune  0.42
  [3] Smythe Academy of Arts and Sciences  0.38
Type a number to choose one, n if none of these is right, or press Enter to
skip.
 > 
x
Center Joint Unified School District · Dudley Elementary  (1 job)
  [1] Arthur S. Dudley Elementary  0.79
  [2] North Country Elementary  0.63
  [3] Cyril Spinelli Elementary  0.57
Type a number to choose one, n if none of these is right, or press Enter to
skip.
 > 
9


[exit: 0 ]
[answers sent at seconds: [(0.2, 'x'), (0.2, '9')] | total 0.2 s]
```

#### 15 chart with no browser
pty: drive2 s15b 30 -- chart
```
Chart written to /tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-
287d-4927-86ce-4355720f397b/scratchpad/p2/s15b/edtrawl-chart.html. I couldn't
open a browser from here, so open that file yourself.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 15 o on a card with no browser
pty: drive2 s15b 60 o q --
```
 Casting the net  ⛵····························  0                            
0 new listings saved, and 0 I'd seen before.
 Matching listings to schools  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  70 of 70        
Set aside: 2 listings I couldn't place at a school or district with confidence.
To check by hand:
    python edtrawl.py match --review
56 new jobs within range, nearest first.
 ── 1 of 56 ───────────────────────────────────────────────────────────────────
 Education Specialist- Mild/Moderate 2026-2027 (Temporary Contract)
 Site not listed · Washington Unified
 Drive   ~7 to ~17 min across the district's 13 schools in range
 Pay     SPED- $1,495 annual stipend, M.A./M.S- $1,295 annual stipend+ $1,295
         for doctorate/ BCLAD- $1,295 annual stipend. Year for year match on...
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
o
I couldn't open a browser from here. The posting is at:
    https://www.edjoin.org/Home/JobPosting/2287720
[k]eep   [t]oss   [s]kip   [o]pen posting   [q]uit
 > 
q
Stopping here: nothing marked. The other 56 jobs will be here next time.


[exit: 0 ]
[answers sent at seconds: [(8.4, 'o'), (8.4, 'q')] | total 8.5 s]
```

#### 16 real OSRM (Modoc, 7 schools)
pty: drive2 s16 90 -- commute
```
 Working out drive times  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~⛵  7 of 7               
Drive times are ready for 7 schools.
Road distances: © OpenStreetMap contributors, routed by OSRM.


[exit: 0 ]
[answers sent at seconds: [] | total 3.6 s]
```

#### 16 search --max-commute 3 --level elementary (nearly_filtered?)
pty: drive2 s16 30 -- search --max-commute 3 --posted-within 30
```
3 jobs, nearest drive first.
 Number   Drive    Closes   Job
 2288422  ~1-4     -        Education Specialist Teacher/Intern -Year for Ye...
 2290417  ~1-4     -        Multiple Subject Teacher/Intern - Year for Year...
 2293900  ~1-4     -        World Language Teacher / Intern- Year for year e...


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 16 drove unchanged
pty: drive2 s16 30 -- drove Warner 5
```
Thanks. I've scaled every morning estimate to match: the typical school near
you went from ~2 to ~4 min.
That's far from my estimate, so I adjusted as far as I allow (half or double).
If that day's traffic was unusual, a typical day's time will fit better.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 16 drove unchanged 2
pty: drive2 s16 30 -- drove Warner 5
```
Thanks. My estimate for that drive was already close, so nothing needed to
change.


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 16 nearly_filtered
pty: drive2 s2 30 -- search --max-commute 2 --posted-within 90
```
Nothing within 2 minutes today.
3 jobs open up at 10 minutes. Run the same search again, with:
    --max-commute 10


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### 16 nearly_filtered via --new
pty: drive2 s2 30 -- search --max-commute 2 --new
```
Nothing within 2 minutes today.
3 jobs open up at 10 minutes. Run the same search again, with:
    --max-commute 10


[exit: 0 ]
[answers sent at seconds: [] | total 0.2 s]
```

#### search --limit 0 / negative
$ ./run.sh s2 search --limit 0
```
The nearest 0 jobs. There are more: add --limit and a bigger number to see
them.
 Number   Drive    Closes   Job
[exit 0]
```

#### search --max-commute -5
$ ./run.sh s2 search --max-commute -5
```
Nothing within -5 minutes today.
3 jobs open up at 10 minutes:
    python edtrawl.py search --max-commute 10
[exit 0]
```

#### search --level xyz
$ ./run.sh s2 search --level xyz
```
No jobs fit those filters. Try dropping one.
[exit 0]
```
