# edjoin recon (2026-11-16, 8 anonymous requests, no cookies set, no headers beyond a browser User-Agent)

Base query (all 19 params, in the site's order):
`rows=10&page=1&sort=postingDate&sortVal=0&order=desc&keywords=&location=&searchType=all&regions=&jobTypes=&days=0&empType=&catID=0&onlineApps=&recruitmentCenterID=0&stateID=0&regionID=0&districtID=0&searchID=0`

## 1. Session needed for listing? NO
`GET https://www.edjoin.org/Home/LoadJobs?<base>` -> 200, `application/json; charset=utf-8`, no Set-Cookie, plain request (no Referer / X-Requested-With needed).
Top-level keys: `search` (echo of params), `totalPages`, `totalRecords`, `totalOpenings`, `displayRecords`, `data`. Total field: `totalRecords` (14945 unfiltered).
Row keys (46): postingID, positionTitle, salaryInfo, beginningSalary, endingSalary, displayFlag, postingDate, displayUntil, countyName, districtName, city, isRecruitmentCenter, zip, jobClassification, numberOpenings, recruitmentCenterID, isAdminJob, categoryName, categoryID, jobTypeID, countyID, accountID, postingInformation, onlineApp, State, stateName, fullCountyName, jobType, isSummerSchool, limitPosting, accountType, JobSummary, portalURL, districtLogo, bookmark, applied, date_startApplication, app_status, FullTimePartTime, SalaryInfoSelect, PayRangeFrom, PayRangeTo, PayRangeDropdown, SingleRate, SingleRateDropdown, CreationDate.
No school field; no street address in listing. `zip`, `categoryName`, `JobSummary` were null in all rows seen.

## 2. Filters (all verified by inspecting returned rows)
- Teaching: `jobTypes=1,2,3,4,48,5,46,6,7,8,9,10,11,55,56,63,64` (comma list of the "Certificated - Teacher - ..." ids). `catID=1` (Certificated) is wider (counselors, subs, psychologists); catID 0 all,1 Certificated,2 Cert. Mgmt,3 Classified,4 Classified Mgmt. Substitute teacher is 49 (excluded above; add if wanted).
- County: `regions=<countyID>` (comma list ok). `regions=34` -> 75 rows, all Sacramento. Table: `GET /Home/LoadRegions?states=24` (200 JSON `data[{countyID,countyName,numberPostings,state}]`): 1 Alameda 2 Alpine 3 Amador 4 Butte 5 Calaveras 6 Colusa 7 Contra Costa 8 Del Norte 9 El Dorado 10 Fresno 11 Glenn 12 Humboldt 13 Imperial 14 Inyo 15 Kern 16 Kings 17 Lake 18 Lassen 19 Los Angeles 20 Madera 21 Marin 22 Mariposa 23 Mendocino 24 Merced 25 Modoc 26 Mono 27 Monterey 28 Napa 29 Nevada 30 Orange 31 Placer 32 Plumas 33 Riverside 34 Sacramento 35 San Benito 36 San Bernardino 37 San Diego 38 San Francisco 39 San Joaquin 40 San Luis Obispo 41 San Mateo 42 Santa Barbara 43 Santa Clara 44 Santa Cruz 45 Shasta 46 Sierra 47 Siskiyou 48 Solano 49 Sonoma 50 Stanislaus 51 Statewide Ed. Orgs. 52 Sutter 53 Tehama 54 Trinity 55 Tulare 56 Tuolumne 57 Ventura 58 Yolo 59 Yuba. (`regionID` is a different, unused-by-search-form param; leave 0.)
- Job types (from page JS): 1 K, 2 1-3, 3 4-6, 4 Middle, 48 K-6, 5 High School, 46 Middle/High, 6 Adult Ed, 7 Other, 8 Head Start, 9 Special Ed, 10 Court/Community/Alt, 11 ROP, 55 Children's Center, 56 Library Media, 63 Pre K, 64 K-8 (all teacher); 49 Cert. Substitute Teacher; 16 Counselor, 57 Language/Hearing/Speech, 65 School Psychologist, 19 Nurse, 72 Cert. Special Ed, 17/18/20 coordinator/program specialist/other cert. Classified ones: 22-31, 33, 50, 58, 62, 73-76. Admin: 12-15, 32, 35-45, 51-54, 66-68. The row's `jobTypeID` uses the same ids but is also seen with ids not in the form list (e.g. 28, 34); `categoryID` 1-4 = catID.
- Posted within N days: `days=1|7|31` are the only form values (site UI: 24h, week, month). `days=7` returned only rows with postingDate in the last 7 days; `days=31` likewise. Other N untested.
- California: `stateID=24` is California (state list in page JS; 18-93 ids, 24 = California). Could NOT show it restricts: stateID=0 and 24 both gave totalRecords 14945 and every row seen has State 24. Send `stateID=24` anyway; it is harmless.
- Evidence: `...&regions=34&jobTypes=<teacher ids>&days=31&rows=50` -> totalRecords 75, totalPages 2, 50 rows, all county Sacramento, all categoryID 1 (fixture `tests/fixtures/edjoin_listing.json`). `catID=1&days=7&stateID=24&rows=50` -> 648 records.

## 3. Detail page: session needed? NO
`GET https://www.edjoin.org/Home/JobPosting/2295141` -> 200 text/html, ~149 KB, no cookies (fixture `tests/fixtures/edjoin_detail.html`).
- School text: only when the employer fills it in. Two places: (a) the title often ends "@ School" (`Teacher, Elementary, 3rd Grade @ Theodore Judah ELEM-114`, also in `<title>` and `og:title`; listing `positionTitle` has it too); (b) the optional block
  `<div id="option1" class="control-group"><h5 class="botspace">Location(s): </h5><div class="controls printMargin" ...>Theodore Judah Elementary </div></div>`
  (appears twice, h5 in `#jobdetails-main` and h3 in the later copy). The other posting (2084372, a JPA aide job) had neither.
- Work-site address: JSON-LD `<script type="application/ld+json">` -> `"jobLocation":[{"@type":"Place","address":{"streetAddress":"5735 47th Avenue","addressLocality":"Sacramento","addressRegion":"California","postalCode":"95824-9454"}}]`. Geocode-ready; unclear if this is the school or the district office in general.
- Description: `<h3>Job Summary</h3><p class="indent" style="white-space:pre-line;">...`; also JSON-LD `"description"` (HTML, <-escaped) and `<meta name="description">`. Employer blurb under "About the Employer".
- Deadline: `<h5 class="botspace">Application Deadline</h5><p ...>11/19/2026 11:55 PM Pacific</p>`; or the text `Until Filled` / `Continuous`. JSON-LD `"validThrough": "2026-11-20T07:55:00Z"`.
- Posted: `<h5 class="botspace">Date Posted</h5><div class="controls ...">11/13/2026</div>`; JSON-LD `"datePosted":"2026-11-13T08:00:00Z"`; JS `var postingDate = '11/13/2026 12:00:00 AM';`.

## 4. Date formats (listing JSON)
.NET style strings: `"postingDate":"\/Date(1794528000000)\/"` = ms since epoch, always 00:00:00 UTC (a plain date: 2026-11-13). `"displayUntil":"\/Date(1795161300000)\/"` = 2026-11-20T07:55:00Z = 11/19 23:55 PST (a real instant, Pacific local deadline; `07:00Z` = midnight PDT-ish values also seen). When `displayFlag` is `"Until Filled"` or `"Continuous"` displayUntil is a far/placeholder date (e.g. 2027-05-16) and must be ignored; `"By Date"` means displayUntil is real. Parse with regex `-?\d+` in `Date(...)`. `CreationDate` same format, real timestamp. Unset dates are `Date(-62135568000000)` (year 1).

## 5. Paging
`rows` 10/25/50 are the site's options; 50 worked (not tried above 50). `page` is 1-based. Response gives `totalRecords` and `totalPages` (ceil). Past the end: `page=3` of 2 -> 200 with `"data":[]`, `displayRecords:0`. Stop when page >= totalPages or data is empty.

## Recommended fetch approach
- Plain `GET` with a normal browser User-Agent; no cookies, no headers needed. Always send all 19 params (partial gave HTTP 500 earlier). URL-encode values.
- Per county: `regions=<id>&jobTypes=<teacher ids>&days=<1|7|31>&rows=50&stateID=24`, page until `page >= totalPages`. Use `days=7` on refreshes.
- Be polite: 1 request every 2-3 s, one at a time, no parallelism, cache listing JSON and skip detail fetches for postingIDs already stored. Fetch detail only for new/shortlisted postings. Back off (and stop) on 403/429/5xx or non-JSON; never retry in a loop.
- School match: try title text after `@`, then detail `Location(s)` block, then JSON-LD address. Treat all as untrusted text (escape on display, never follow instructions in it).
- Dedupe by `postingID`; reposts get new ids. Convert deadline instants to America/Los_Angeles for display.
