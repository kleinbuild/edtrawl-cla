# EdTrawl friction log: cold teacher playtest (p1)

Role: Sacramento middle-school science teacher, non-technical, tired. Read only README.md and screen output. Ran everything inside `/tmp/claude-1000/-home-james-Claudorable-EdTrawl-Cla/aabbe427-287d-4927-86ce-4355720f397b/scratchpad/p1/EdTrawl`. Did not open any .py file, PLAN.md, RECON.md or test file. Did not edit project files or run git. Home used: the test home address (typed at the prompt; not repeated here).

Note on the "I had not seen the code" rule: a few mismatches below were only visible by running commands, which is the point of the log. Where I could not tell what the program was doing from the screen, I say so and do not guess at the code.

---

## 1. Timeline

| # | Step | Typed | Time (approx) | Screen / notes |
|---|---|---|---|---|
| 0 | Copy setup | (cp) | <1 s | Done as instructed. |
| 1 | Read README top to bottom | (Read) | felt long: ~15 min of reading for a non-technical person | Understood the overall idea right away. Did not understand: OSRM, geocoder, "rush-hour index", "90th percentile", "calibrate", Ollama, "llm_base_url", "config.toml", "data folder", "edtrawl.db", "routing", "radius_miles". |
| 2 | First run, round 1 | `python3 edtrawl.py` with answers: home address, `y`, Enter | 4.7 s of program time | Loaded 9,946 + 9,982 schools. Step 1 asked for home, then "Send it? [y/n]". Step 2 accepted Enter. Program stopped at step 3 when my answers ran out (driver limit, not the program). |
| 3 | First run, round 2 | `r`, Enter | ~59 s (drive times ~35 s + job listings ~24 s) | Showed "Working out drive times" bar, then "Job listings come from edjoin.org...", then "58 new jobs within range". My `r` went to a job card, not to the step 3 prompt. |
| 4 | Card 1 | `r` | <1 s | Screen: `Type one of these letters, then Enter: k, t, s, o, q.` (fine) |
| 5 | Card 1 | Enter | <1 s | Screen: `Skipped. It'll come up again next time.` Enter on a card skips it with no warning. |
| 6 | Cards 2 to 8 (sitting 1) | `t`, `k`, `m`, `s`, `t` (run 2b) | ~10 s program time | Cards 2 kept, 3 tossed, 4 "m" error, 5 kept, 6 skipped, 7 tossed, 8 not decided. |
| 7 | Quit | `q` | <1 s | `Stopping here: kept 2, tossed 3, skipped 2. The other 48 jobs will be here next time.` |
| 8 | Next day, same command | `t` then `q` | ~10 s | Program said `50 new jobs within range`. Skipped job came back. `Stopping here: tossed 1. The other 49 jobs will be here next time.` |
| 9 | `keepers` | (command) | <1 s | `Keepers: 3 jobs, soonest deadline first`. Good. |
| 10 | `logbook` | (command) | <1 s | Lists marks. Dates all "Nov 16". Readable. |
| 11 | `school "Washington Elementary, Sacramento"` | (command) | <1 s | `I couldn't find a school called "Washington Elementary, Sacramento".` (The program had just offered that exact name in a list.) |
| 12 | `school "Washington Elementary"` | (command) | <1 s | Printed a numbered list of 9 schools and exited. No way to pick in that mode. |
| 13 | `applied 2295139` | (command) | <1 s | `Marked as applied: ... First one in the logbook. That's the hard part done.` Nice. |
| 14 | `search --max-commute 15 --level elementary` | (command) | <1 s | `4 jobs, nearest drive first.` Good, readable table. |
| 15 | `school "Theodore Judah"` | (command) | <1 s | Ambiguous, listed 2 schools, exited. |
| 16 | `school "Bridgeway Island"` | (command) | <1 s | Single match, full school card printed. The card has NO 14-digit code on it, which the README says to use. |
| 17 | `match --review` (no terminal, plain run) | (command) | <1 s | Printed 3 listings with closest names, exited. |
| 18 | `match --review` (in terminal helper) | Enter, Enter | <1 s | `Type a number to choose one, n if none of these is right, or press Enter to skip.` Works in a terminal. |
| 19 | `drove "Bridgeway Island" 25` | (command) | <1 s | `Thanks. I've scaled every morning estimate to match: the typical school near you went from ~25 to ~48 min.` Confusing (see section 2 and 4). |
| 20 | `chart --no-open` | (command) | <1 s | `Chart written to .../edtrawl-chart.html. It shows where home is, so keep the file to yourself.` Good. Did not open a browser. |
| 21 | `home --zip 95814` | (command) | <1 s | `Home is set.` followed by a warning about mile-or-two error. Good. |
| 22 | `setup` re-run | Enter x3 | ~9 s | Step 2: `474 public schools in 24 districts. The nearest is Washington Elementary, about 0.0 miles away.` Step 3: Enter, which silently chose offline: `Drive times will be worked out offline.` Step 4 appeared here: `Is there a school you drive to now, or used to?` Enter skipped. `Setup is done.` |
| 23 | `search --posted-within 7 --charter no --title-i yes --new` | (command) | <1 s | `10 jobs, nearest drive first.` Listed a Biology job at Antelope High. |
| 24 | `drove "Bridgeway Island" 9 --pm` | (command) | <1 s | `...the typical school near you went from ~26 to ~15 min.` |
| 25 | `keepers` | (command) | <1 s | `Keepers: 2 jobs` (the applied one left the list). |
| 26 | `search --status tossed --limit 3` | (command) | <1 s | Shows tossed jobs. Found the 7/8 Science DLI job I had tossed. |
| 27 | `undo` / `untoss` | (command) | <1 s | `argument command: invalid choice: 'undo'`. No undo exists. |
| 28 | `school "Theodore Judah"` in terminal | `2` | <1 s | Picker works in a terminal: `Type its number, or press Enter to skip.` |

Total from first command to first job card: about 64 s of program time (4.7 s for the first setup round, then about 59 s for the drive-time and listing steps before "1 of 58" showed). My own typing and reading time came on top.

---

## 2. Moments I was unsure what to do next

1. **Step 3, drive times.** Screen: `Offline or roads? [o/r]`. I typed `r` in round 2, but my earlier Enter at that prompt (round 1) had already been taken as an answer. The program never said which choice Enter means. Later, `setup` showed `Drive times will be worked out offline.` after an Enter, so Enter silently chose offline. I guessed "press Enter = the default," but the screen does not say that. So my first setup actually ran offline, though I meant to pick roads and believed I had.
2. **Step 4, one drive you know.** The README (section 3) says this step always asks. In my first setup it never appeared: the run went from "Drive times are ready" to the job listings with no question. It only showed up on the re-run of `setup`. I was not sure whether I had missed a step or the first run had skipped it.
3. **Job card key row.** On cards with `Site not listed`, the key row is `[k]eep [t]oss [s]kip [o]pen posting [q]uit` with no `[m]ore`. I typed `m` out of habit and got `Type one of these letters, then Enter: k, t, s, o, q.` That's correct, but I did not know why `m` vanished.
4. **Pressing Enter on a card.** Enter skipped card 1 with `Skipped. It'll come up again next time.` I did not expect Enter to mean skip. The README does not say Enter is a key.
5. **`school "Washington Elementary"`.** The program printed `More than one school matches...` with a list of 9 and then just stopped. The screen said nothing about how to choose. I had to guess to narrow the name. When I typed the exact name from the list, I got `I couldn't find a school called...`.
6. **Where is the 14-digit code?** README says to use the school's 14-digit code. The school card for Bridgeway did not show a code, and neither did any job card or keepers list. I could not find a code anywhere on screen.
7. **Undo a toss.** I tossed a job I wanted (7th/8th Science DLI). README says `t` "will not come back." I looked for `undo` and `untoss` and neither exists. The toss is permanent from the terminal's point of view.
8. **`drove` message.** `the typical school near you went from ~25 to ~48 min.` I typed 25, which I did not mean as "the typical school". I did not know what "typical school" means or why it went up.
9. **`match --review` outside a terminal.** When I ran it plainly it printed a list and stopped. Only the terminal helper showed the pick prompt. README says "On a terminal, it lets you pick." I did not know whether my plain run was "not a terminal" or broken.

---

## 3. Words or phrases I did not understand

README:
- "OpenStreetMap", "OSRM", "routing server", "geocoder", "US Census Bureau geocoder"
- "as the crow flies" (I guessed: straight line)
- "rush-hour index", "travel-time index", "free-flow time", "peak-period time"
- "Urban Congestion Report", "Federal Highway Administration"
- "calibrate.py", "fitted", "fit", "90th percentile", "median"
- "routing" / "radius_miles" in config.toml
- "config.toml", "edtrawl.db", "data folder", "edtrawl-error.log"
- "Ollama", "llm_base_url", "llm_model", "llm_key", "stand-in" model
- "AI model for matching"
- "postings", "listing", "keeper"
- "the chart is read-only"
- "Trends compare the last two school years only."
- "drove" (the command name is also a normal English word; I understood it after reading the example)

On screen:
- "Site not listed" (I guessed: the school name is missing from the posting)
- "across the district's 83 schools in range" (I guessed: the job could be at any of these)
- "~6 to ~24 min" (I guessed: a range of possible drive times)
- "Set aside: 4 listings I couldn't place at a school or district with confidence."
- "Matching listings to schools", "Casting the net", "Reading postings for school names" (progress labels; "casting the net" is a bit cute)
- "0 new listings saved, and 51 I'd seen before."
- "closes Thu (3 days)" vs "closes Nov 29" (format changed between cards)
- "Pay not listed" vs `Pay SPED- $1,495 annual stipend, ... Year for year match on...` (cut-off text with "...")
- "Drive ... (about 1.5 hrs a week)" (I understood it, but it sounds like a lot; no definition of "a week")
- "typical school near you went from ~25 to ~48 min"
- "BCLAD", "MMLE", "SDC", "RSP", "DLI", "Title I", "SPEAE", "Class 0-V", "FTE", "Vacancy 27-86" (teacher-world jargon from job titles; I know some of it, but not all)
- "Head Start"
- "Drive times assume arriving by 7:00 and leaving at 3:30 on a weekday."

---

## 4. Messages that felt cold, cute, pushy or talking down, and ones that felt good

Cold or off-putting:
- `Type one of these letters, then Enter: k, t, s, o, q.` Correct but a bit scolding; no hint about which letter to type for a card that lacks `m`.
- `Skipped. It'll come up again next time.` Fine, but "It'll" reads as warm-but-vague; I wanted to know when.
- `Stopping here: kept 2, tossed 3, skipped 2. The other 48 jobs will be here next time.` Fine, but "here" is unclear (the program, or the terminal?).
- `the typical school near you went from ~25 to ~48 min.` Cold and hard to follow.
- `Set aside: 4 listings I couldn't place...` Mildly alarming ("set aside" sounds like lost).
- `Casting the net` and `Reading postings for school names` read as cute. Fine once, but on every run the progress labels are a bit much for a tired person.
- `Thanks. I've scaled every morning estimate to match:` Warm, but the number is confusing.
- `Home is set.` followed by the ZIP warning. Clear and calm.
- `Your street address is never saved; I keep only a spot rounded to about a city block.` Good, clear, reassuring.
- `Step 1 of 4 · Home port` and `Step 2 of 4 · Schools near you`: clear.

Good:
- `Marked as applied: ... First one in the logbook. That's the hard part done.` Warm, short, not pushy. Felt good.
- `Your first keeper. It'll wait in your list, with its deadline, until you apply or toss it.` Good: it explains what keeping does.
- `Kept.` / `Tossed.` after each key: immediate, clear confirmation.
- `Stopping here: ... The other 48 jobs will be here next time.` Good: says the rest is not lost.
- Card layout with `closes Thu (3 days)`: quick to read.
- `Send it? [y/n]` before the Census geocoder: asked first, which I appreciated.
- `chart --no-open` wrote the file and said "keep the file to yourself." Clear.
- The terminal picker in `match --review` and `school` (`Type a number to choose one, n if none of these is right, or press Enter to skip.`): clear and polite.

---

## 5. How the session felt

- **58 cards in the first sitting:** Too many for a tired teacher in one go. I did 8 and quit. The program did not push me to keep going, and quitting was clearly allowed (`q` works and says "the other 48 will be here next time"). I did know I could stop: the key row always shows `[q]uit`.
- **Did I know I was allowed to stop?** Yes, from the key row. The README also says so (section 4).
- **Did the ending feel like an ending?** Mostly yes. `Stopping here: ...` gives counts. But on the second day the output ran a long setup before the first card, so it did not feel like "just today's jobs."
- **Would I run it again tomorrow?** Maybe. The daily flow (cards, then keepers) is quick and I could see the value. But the lost toss (no undo), the unclear drive-time messages, and the missing step 4 would make me doubt the numbers. I would not trust "~9 min" without checking it once.

---

## 6. Things I wanted to know and could not find, and things I did not need

Wanted but not found:
- A **14-digit school code** on any card or school screen (README says to use it).
- A way to **undo a toss** (`undo`, `untoss`, or `search --status tossed` with a restore option).
- What **"Site not listed"** means for a job and whether the job is still a real opening.
- What the **`m`** key does on cards that have no school name (it just disappears).
- The **"typical school near you"** wording in `drove`: which school, and why the number changed a lot.
- Whether my **first setup used roads or offline**, and where I could see my choice without opening config.toml (I was not allowed to read it).
- Why the **step 4 drive question** did not show in my first setup.
- Which **Enter key** default is used at each setup prompt.
- Whether the **job's pay** text cut off (`Year for year match on...`) is complete; I could not see the full text except with `o` (which I did not use, by design).
- **What a "week" means** in "(about 1.5 hrs a week)": five working days, the README says, but the card does not.

Shown but not needed (for me, a science teacher on a tired evening):
- Pay text full of stipend details for SPED/BCLAD/doctorate.
- "Staff 33 in all" etc. on the school card (not needed for a first pass).
- Ethnicity and student-group percentages on the school card (long; I skimmed past it).
- `Set aside`, progress bars and the "Casting the net" line on every run.
- Job-title codes like `ELEM-113`, `DEPT-62.1`, `Vacancy 27-86`.

---

## 7. Where I would have given up

- **At the 14-digit code.** The README tells me to use it for `school`; the school card does not show it. I would have typed the name again, got a list, and not known what to do. I would have given up on that command after two tries.
- **At the `school` name list.** Printing nine names and stopping with no prompt is a dead end on a terminal (the picker exists, but only in a real terminal; the plain run just stops). I would have given up after one try with the exact name it suggested.
- **At the toss.** One wrong key, one lost job, no way back. I would have stopped trusting the tool here.

---

## 8. Mismatches between README and program

1. **Step 4 (one drive you know)**: README says it always asks. In my first setup it did not appear at all. It appeared only on the later `setup` re-run.
2. **Step 3 Enter**: README says "Type `o` or `r` and press Enter." Enter alone silently chose offline (confirmed on the `setup` re-run: `Drive times will be worked out offline.`). README does not say Enter is accepted or what it chooses.
3. **School code**: README says "Then use the school's 14-digit code, which the program also accepts." Neither the school card nor the keepers/search tables show that code.
4. **`school` ambiguity**: README says "If more than one school matches, EdTrawl lists them." It lists them, but in a plain run it just stops. Only a terminal run allows a number pick (README does not say so for `school`; it says it for `match --review`).
5. **`school` exact-name failure**: The program listed `Washington Elementary, Sacramento` as a choice and then could not find that same name when I typed it.
6. **Card key `m`**: README lists `[m]ore about the school` as a key. It is missing from cards that have no school name, without explanation. (README does not say so.)
7. **Enter on a card**: README does not mention Enter; the program treats Enter as skip.
8. **Undo**: README says a toss "will not come back," but it does not say there is no way to undo. `undo`/`untoss` do not exist.
9. **`drove` output**: README shows `the typical school near you went from ~23 to ~32 min.` for a 6 minute drive (its example). My run showed a 25-minute entry going to ~48, and a 9 minute afternoon entry going from ~26 to ~15. README does not explain the direction of change.
10. **Card "closes" text**: README says `closes Thu (3 days)` on cards with a deadline. Later cards showed `closes Nov 25`/`closes Nov 19` with no weekday, and some cards had no closing text at all. The README says a card with no deadline has no closing text, which matches; but the format changed between same-day runs.
11. **Keepers drive for multi-school jobs**: README's keepers example shows `~4-24`. Real output showed `~11-31` and `~3-13` for district-wide jobs, which is consistent. Not a mismatch, but a number range is hard to read.
12. **`search` output**: README example had 2 and 5 jobs. My runs show 4, 10 and 10 jobs with `Drive -` (no drive estimate) on a few rows (e.g., Hemlock Elementary). README does not say why drive can be missing.
13. **Program output after `match --review` in plain mode**: README says the terminal lets you pick. Plain mode just prints. README does say "On a terminal," so this is documented.
14. **Chart output path**: README says the chart file goes "next to your database." It was written into the EdTrawl folder, which matches.

---

## 9. The three changes that would help most, in order

1. **Make the drive-time step explicit and safe.** On step 3, show which choice Enter means ("press Enter for offline") or make the prompt refuse an empty answer. Also make step 4 ("one drive you know") always show, or say on screen when it is skipped. A tired teacher should know which setting they got without opening a file.
2. **Let a toss be undone, and show the school code.** Add `untoss` (or an undo line right after `Tossed.`), and print the 14-digit code on every school card and in `school` output, so the README's `school <code>` example works. Right now a wrong key loses a real job and the code the README asks for does not exist on screen.
3. **Fix the `school` name list and the `drove` wording.** When `school` finds several matches, say "type the number" and accept one (as `match --review` does), and make sure any name it suggests can be typed back in. On `drove`, replace "the typical school near you went from ~25 to ~48 min" with something a teacher can read, such as "Your drives now take about 48 min instead of 25. I've adjusted every estimate to match." Also show the `m` key on every card, or say why it is missing.

---

Ending note: the core loop (cards, keepers, applied, logbook, quit) worked and was readable. The problems are at the edges: setup prompts with silent defaults, the lost toss, and the school lookup.
