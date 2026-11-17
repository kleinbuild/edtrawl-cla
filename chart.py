"""`python edtrawl.py chart`: one self-contained HTML page, a chart of home, the schools in range and the catch.

Everything the reader sees is rendered here, on the server side, with html.escape on every database string,
so the page reads (and prints) even with scripting off. The script only filters and highlights. No network of
any kind: the only links are edjoin postings built from the numeric posting id, and https school websites.
Home's coordinates are never written; every position is an offset from home in miles.
"""
import html
import math
import re
from datetime import date

import query
import ui

MILE_DEG = 69.17  # miles per degree of latitude; longitude is scaled by cos(home latitude)
# Drive-time bands (upper bound in minutes, label, glyph). Shape and label carry the meaning; colour only helps.
BANDS = ((15, "Up to 15 min", "circle"), (30, "15 to 30 min", "square"),
         (45, "30 to 45 min", "diamond"), (math.inf, "Over 45 min", "triangle"))
SIZE, PAD = 800, 70  # SVG user units; the map circle's radius is SIZE/2 - PAD
SOON_DAYS = 7
EDJOIN = "https://www.edjoin.org/Home/JobPosting/"

# Marks live in one <defs>; the map and the chips both <use> them (an in-page reference, not a request).
GLYPHS = {
    "circle": '<circle r="7"/>',
    "square": '<rect x="-6.5" y="-6.5" width="13" height="13"/>',
    "diamond": '<path d="M0-9L9 0 0 9-9 0z"/>',
    "triangle": '<path d="M0-8.5L9 6.5H-9z"/>',
}


def band_of(m):
    return next(i for i, (top, _, _) in enumerate(BANDS) if m <= top)


def _e(value):
    return html.escape(ui.clean(value), quote=True)


def _https(url):
    url = (url or "").strip()
    return url if re.fullmatch(r"https://[^\s\"'<>]+", url) else ""


def _days_left(value, today):
    d = ui._date(value)
    return None if d is None else (d - today).days


def gather(conn, cfg, today):
    """Plain data for the page: schools as (miles east, miles north) of home, jobs from query.search."""
    lat0, lng0 = (float(x) for x in cfg.home_key.split(","))
    kx, ky = MILE_DEG * math.cos(math.radians(lat0)), MILE_DEG
    schools = {}
    for r in conn.execute(
            "SELECT s.cds_code, s.school_name, s.district_name, s.website, c.straight_miles, c.provider, "
            "COALESCE(s.lat_override, s.lat) AS lat, COALESCE(s.lng_override, s.lng) AS lng, "
            "c.am_minutes * h.factor_am AS am, c.pm_minutes * h.factor_pm AS pm "
            "FROM commutes c JOIN schools s USING (cds_code) JOIN homes h ON h.home_key = c.home_key "
            "WHERE c.home_key = ?", (cfg.home_key,)):
        if r["lat"] is None or r["lng"] is None:
            continue
        times = [m for m in (r["am"], r["pm"]) if m is not None]
        schools[r["cds_code"]] = dict(
            name=r["school_name"], district=r["district_name"], website=r["website"], provider=r["provider"],
            x=round((r["lng"] - lng0) * kx, 2), y=round((r["lat"] - lat0) * ky, 2),
            miles=r["straight_miles"], minutes=max(times) if times else None)
    jobs = []
    for r in query.search(conn, cfg, limit=None):
        if r["drive_minutes"] is None or r["mark_status"] == "tossed":
            continue  # same rule as the deck: only jobs with a drive time, and nothing the user tossed
        left = _days_left(r["deadline"], today)
        if left is not None and left < 0:
            continue
        r["days_left"] = left
        jobs.append(r)
    return dict(schools=schools, jobs=jobs, today=today,
                fetched=bool(conn.execute("SELECT 1 FROM jobs LIMIT 1").fetchone()),  # false: no cast has ever run
                roads=any(s["provider"] == "osrm" for s in schools.values()))


def _rings(radius):
    step = 2 if radius <= 12 else 5 if radius <= 40 else 10
    return [m for m in range(step, int(radius) + 1, step)] or [radius]


def _map(data, radius):
    k = (SIZE / 2 - PAD) / radius  # user units per mile
    c = SIZE / 2
    out = [f'<svg id="map" viewBox="0 0 {SIZE} {SIZE}" role="group" aria-label="Chart of schools around home">',
           "<defs>" + "".join(f'<symbol id="g-{n}" overflow="visible">{p}</symbol>' for n, p in GLYPHS.items())
           + "</defs>", '<g class="rings">']
    for m in _rings(radius):
        r = m * k
        out.append(f'<circle cx="{c}" cy="{c}" r="{r:.1f}"/>')
    out.append("</g>")
    out.append('<g class="ringlabels" aria-hidden="true">')
    for m in _rings(radius):
        r = m * k  # labels ride the rings at the lower right, where the compass and the title never are
        out.append(f'<text x="{c + r * 0.7071:.1f}" y="{c + r * 0.7071 + 4:.1f}">{m} mi</text>')
    out.append("</g>")
    hiring = {}
    for j in data["jobs"]:
        if j["cds_code"] in data["schools"]:
            hiring.setdefault(j["cds_code"], []).append(j)
    out.append('<g class="quiet" aria-hidden="true">')
    for code, s in data["schools"].items():
        if code not in hiring:
            out.append(f'<circle cx="{c + s["x"] * k:.1f}" cy="{c - s["y"] * k:.1f}" r="3">'
                       f'<title>{_e(s["name"])}</title></circle>')
    out.append("</g>")
    out.append('<g class="hiring">')
    for code, js in sorted(hiring.items(), key=lambda kv: -data["schools"][kv[0]]["y"]):
        s = data["schools"][code]
        b = band_of(s["minutes"] if s["minutes"] is not None else js[0]["drive_minutes"])
        label = f'{ui.clean(s["name"])}, {BANDS[b][1]}, {ui.count(len(js), "job")}'
        out.append(f'<g class="mk b{b}" tabindex="0" role="button" data-school="{_e(code)}" data-band="{b}" '
                   f'transform="translate({c + s["x"] * k:.1f} {c - s["y"] * k:.1f})" aria-label="{_e(label)}">'
                   f'<circle class="hit" r="20"/><use href="#g-{BANDS[b][2]}" class="glyph"/>'
                   f'<title>{_e(label)}</title></g>')
    out.append("</g>")
    out.append(f'<g class="home" aria-label="Home"><circle cx="{c}" cy="{c}" r="9"/>'
               f'<path d="M{c - 15} {c}h30M{c} {c - 15}v30"/><text x="{c + 14}" y="{c - 12}">Home</text></g>')
    # Compass: a small north arrow in the top-right corner, outside the outer ring.
    out.append(f'<g class="compass" aria-label="North is up" transform="translate({SIZE - 52} 56)">'
               f'<path d="M0-30L7 0 0-6-7 0z" class="needle"/><path d="M0 30L5 0 0 6-5 0z"/>'
               f'<text y="-38">N</text></g>')
    out.append("</svg>")
    return "".join(out)


def _card(j, today, schools):
    school = ui.clean(j["school_name"]) if j["cds_code"] else ""
    on_map = bool(j["cds_code"]) and j["cds_code"] in schools
    where = " · ".join(x for x in (school or ui.text("site_not_listed"),
                                   ui.clean(j["district_name"]) or ui.clean(j["district_raw"])) if x)
    if j["cds_code"]:
        drive = ui.drive_line(j["am_minutes"], j["pm_minutes"], j["provider"])
    else:
        drive = ui.range_line(j["district_min_minutes"], j["district_max_minutes"],
                              j["district_schools_in_range"], j["provider"])
    facts = []
    if j["cds_code"] and j["enroll_total"]:
        t = ui.trend(j["enroll_total"], j["prev_enroll_total"])
        facts.append(ui.text("students", n=j["enroll_total"]) + (", " + t if t else ""))
    if j["cds_code"] and j["staff_teacher"]:
        facts.append(ui.text("teachers", n=j["staff_teacher"]))
    if j["cds_code"] and j["title_i"] == "Y":
        facts.append(ui.text("title_i"))
    b = band_of(j["drive_minutes"])
    due = ui.deadline(j["deadline"], today)
    mark = ui.text("mark_" + j["mark_status"]) if j["mark_status"] else ""
    dl = lambda label, value: f"<dt>{_e(ui.text(label))}</dt><dd>{value}</dd>"
    rows = [dl("label_drive", f'<svg class="bandmark b{b}" aria-hidden="true" viewBox="-11 -11 22 22">'
                              f'<use href="#g-{BANDS[b][2]}"/></svg> {_e(drive)}')]
    if facts:
        rows.append(dl("label_school", _e(" · ".join(facts))))
    rows.append(dl("label_pay", _e(j["salary_info"]) or _e(ui.text("pay_not_listed"))))
    site = ""
    if j["cds_code"]:
        url = (schools.get(j["cds_code"]) or {}).get("website") or ""
        site = (f' · <a href="{_e(url)}" rel="noopener noreferrer">School website</a>' if _https(url) else "")
    link = f'<a href="{EDJOIN}{int(j["posting_id"])}" rel="noopener noreferrer">Open the posting on edjoin.org</a>'
    note = "" if on_map or j["cds_code"] else (
        '<p class="note">Not on the chart: this job names the district, not a school, so it has no single dot.</p>')
    find = ('<button type="button" class="find">Find on chart</button>' if on_map else "")
    days = "" if j["days_left"] is None else f' data-days="{j["days_left"]}"'
    return (f'<li class="card" data-band="{b}" data-school="{_e(j["cds_code"] if on_map else "")}" '
            f'data-kept="{int(j["mark_status"] == "kept")}"{days}>'
            f'<div class="top"><span class="due">{_e(due)}</span><span class="status">{_e(mark)}</span></div>'
            f'<h3>{_e(j["title"])}</h3><p class="where">{_e(where)}</p><dl>{"".join(rows)}</dl>{note}'
            f'<p class="acts">{link}{site}{find}</p></li>')


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
<title>EdTrawl chart</title>
<style>
:root{--paper:#eef2f1;--panel:#f8faf8;--ink:#17303f;--ink2:#41596a;--rule:#b7c6cb;--ring:#8ea5ae;--focus:#0a58c9;
--b0:#2a78d6;--b1:#d9531e;--b2:#13875f;--b3:#6250d6;--quiet:#7d939c;--hot:#17303f}
@media (prefers-color-scheme:dark){:root{--paper:#0d1a21;--panel:#12232c;--ink:#e6eef0;--ink2:#a9bec6;--rule:#2d4450;--ring:#4f6a76;
--focus:#8bbcff;--b0:#3987e5;--b1:#e0642f;--b2:#25a97c;--b3:#9085e9;--quiet:#5d7886;--hot:#e6eef0}}
*{box-sizing:border-box}
html{color-scheme:light dark}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.serif,h1,h2,.ringlabels text,.home text{font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
a{color:inherit;text-underline-offset:3px}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
header,main,footer{max-width:1240px;margin:0 auto;padding:0 16px}
header{padding-top:22px;padding-bottom:6px}
h1{font-size:clamp(1.5rem,3.5vw,2.1rem);line-height:1.15;margin:0 0 4px;font-weight:600}
.lead{margin:0;color:var(--ink2);max-width:62ch}
.layout{display:grid;gap:20px;padding:16px 0 8px}
@media(min-width:900px){.layout{grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);align-items:start}
.chartwrap{position:sticky;top:12px}}
.chartwrap{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:8px}
svg#map{display:block;width:100%;height:auto;max-height:86vh}
.rings circle{fill:none;stroke:var(--ring);stroke-width:1;stroke-dasharray:2 5}
.rings circle:last-child{stroke-dasharray:none;stroke-width:1.4}
.ringlabels text{font-size:18px;font-style:italic;fill:var(--ink2);paint-order:stroke;stroke:var(--panel);stroke-width:5px}
.quiet circle{fill:var(--quiet);opacity:.5}
.mk{cursor:pointer;color:var(--b0)}
.mk.b1{color:var(--b1)}.mk.b2{color:var(--b2)}.mk.b3{color:var(--b3)}
.mk .hit{fill:transparent}
.mk .glyph{fill:currentColor;stroke:var(--panel);stroke-width:2;transform:scale(1.5)}
.mk.dim{opacity:.18}
.mk.on .glyph,.mk:hover .glyph{stroke:var(--hot);stroke-width:3}
.mk:focus-visible{outline:none}
.mk:focus-visible .hit{stroke:var(--focus);stroke-width:3}
.mk.hot .hit{fill:none;stroke:var(--hot);stroke-width:2.5;stroke-dasharray:4 3}
.home circle{fill:var(--ink);stroke:var(--panel);stroke-width:3}
.home path,.compass path{stroke:var(--ink);stroke-width:2;fill:none}
.home text{font-size:19px;font-weight:600;fill:var(--ink);paint-order:stroke;stroke:var(--panel);stroke-width:6px}
.compass path{fill:var(--ink2);stroke:none}.compass .needle{fill:var(--ink)}
.compass text{font:italic 600 17px Georgia,serif;fill:var(--ink);text-anchor:middle}
.pick:empty{display:none}
.pick{margin:6px 4px 0;font-size:.95rem;color:var(--ink2)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px;padding:0;list-style:none}
.chip{display:inline-flex;align-items:center;gap:7px;font:inherit;font-size:.92rem;color:var(--ink);background:var(--panel);
border:1px solid var(--ring);border-radius:999px;padding:6px 13px;min-height:40px;cursor:pointer}
.chip svg{width:16px;height:16px;fill:currentColor}
.chip[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.chip[aria-pressed=true] svg{fill:var(--paper)}
.chip .sw{color:var(--b0)}.chip .b1{color:var(--b1)}.chip .b2{color:var(--b2)}.chip .b3{color:var(--b3)}
.chip[aria-pressed=true] .sw{color:var(--paper)}
.chip svg{fill:currentColor}
.count{margin:0 0 10px;color:var(--ink2);font-size:.95rem}
ol.cards{list-style:none;margin:0;padding:0;display:grid;gap:12px}
.card{background:var(--panel);border:1px solid var(--rule);border-left:4px solid var(--ring);border-radius:4px;padding:12px 14px}
.card.hot{border-left-color:var(--hot);box-shadow:0 0 0 2px var(--hot)}
.card[hidden]{display:none}
.card .top{display:flex;justify-content:space-between;gap:8px;font-size:.88rem;color:var(--ink2)}
.card h3{margin:2px 0 0;font-size:1.08rem;line-height:1.3;overflow-wrap:anywhere}
.where{margin:0 0 6px;color:var(--ink2)}
dl{display:grid;grid-template-columns:4.5rem 1fr;gap:2px 10px;margin:0;font-size:.95rem}
dt{color:var(--ink2)}dd{margin:0;overflow-wrap:anywhere}
.bandmark{width:14px;height:14px;vertical-align:-2px;fill:currentColor}
.card [class~=b0]{color:var(--b0)}.card [class~=b1]{color:var(--b1)}.card [class~=b2]{color:var(--b2)}.card [class~=b3]{color:var(--b3)}
.note{margin:6px 0 0;font-size:.9rem;color:var(--ink2)}
.acts{margin:10px 0 0;font-size:.92rem;display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center}
.find,.clear{font:inherit;font-size:.88rem;color:var(--ink);background:none;border:1px solid var(--ring);border-radius:4px;padding:4px 10px;min-height:36px;cursor:pointer}
.empty{background:var(--panel);border:1px dashed var(--ring);border-radius:6px;padding:16px}
.empty p{margin:0 0 6px}
code{font:.92em ui-monospace,Menlo,Consolas,monospace}
.readonly{color:var(--ink2);font-size:.92rem;margin:0 0 12px}
footer{padding-top:14px;padding-bottom:30px;color:var(--ink2);font-size:.88rem;max-width:84ch;margin:0 auto 0 max(0px,calc((100vw - 1240px)/2))}
footer p{margin:0 0 6px}
@media(prefers-reduced-motion:no-preference){.mk .glyph,.card{transition:stroke-width .15s,box-shadow .15s}}
@media print{body{background:#fff;color:#000}.chips,.readonly,.find,.clear,.pick{display:none}.chartwrap{position:static}
.layout{display:block}.card{break-inside:avoid;margin-bottom:8px}svg#map{max-height:none}a{text-decoration:none}}
</style>
</head>
<body>
<header>
<h1>__TITLE__</h1>
<p class="lead">__LEAD__</p>
</header>
<main>
<div class="layout">
<section class="chartwrap" aria-label="Chart">
__MAP__
<p class="pick" id="pick" aria-live="polite"></p>
</section>
<section aria-label="Jobs">
__LIST__
</section>
</div>
</main>
<footer>
<p>Drive times marked ~ are estimates, assuming you arrive by 7:00 and leave at 3:30. Rings are straight-line miles from home; north is up.</p>
<p>__SOURCES__ Made __DATE__.</p>
<p>This page shows where home is relative to nearby schools, so treat the file as personal.</p>
</footer>
<script>
(function(){
var $=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
var cards=$('.card'),marks=$('.mk'),chips=$('.chip'),pick=document.getElementById('pick'),count=document.getElementById('count');
var st={bands:{},kept:false,soon:false,school:''};
var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion:reduce)').matches;
function show(c,withSchool){
 var anyBand=Object.keys(st.bands).length;
 if(anyBand&&!st.bands[c.dataset.band])return false;
 if(st.kept&&c.dataset.kept!=='1')return false;
 if(st.soon&&!(c.dataset.days!==undefined&&+c.dataset.days<=__SOON__))return false;
 return !(withSchool&&st.school&&c.dataset.school!==st.school);
}
function render(){
 var n=0;
 cards.forEach(function(c){var ok=show(c,true);c.hidden=!ok;if(ok)n++});
 var live={};cards.forEach(function(c){if(show(c,false))live[c.dataset.school]=1});
 marks.forEach(function(m){m.classList.toggle('dim',!live[m.dataset.school]);m.classList.toggle('on',m.dataset.school===st.school)});
 if(count)count.textContent=n+' of '+cards.length+(cards.length===1?' job':' jobs')+' showing.';
 pick.textContent='';
 if(st.school){
  var m=marks.filter(function(x){return x.dataset.school===st.school})[0];
  pick.appendChild(document.createTextNode((m?m.getAttribute('aria-label'):'')+'. '));
  var b=document.createElement('button');b.type='button';b.className='clear';b.textContent='Show all jobs';
  b.onclick=function(){st.school='';render()};pick.appendChild(b);
 }
}
function choose(code){st.school=st.school===code?'':code;render();
 if(st.school){var f=cards.filter(function(c){return !c.hidden})[0];if(f&&!reduce&&window.innerWidth<900)f.scrollIntoView({block:'nearest'})}}
chips.forEach(function(ch){ch.addEventListener('click',function(){
 var on=ch.getAttribute('aria-pressed')!=='true';ch.setAttribute('aria-pressed',on);
 var k=ch.dataset.kind;if(k==='band'){if(on)st.bands[ch.dataset.band]=1;else delete st.bands[ch.dataset.band]}else st[k]=on;render()})});
marks.forEach(function(m){
 m.addEventListener('click',function(){choose(m.dataset.school)});
 m.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(m.dataset.school)}});
});
cards.forEach(function(c){var f=c.querySelector('.find');if(!f)return;
 f.addEventListener('click',function(){
  var was=c.classList.contains('hot');
  cards.forEach(function(x){x.classList.remove('hot')});marks.forEach(function(x){x.classList.remove('hot')});
  if(was)return;c.classList.add('hot');
  var m=marks.filter(function(x){return x.dataset.school===c.dataset.school})[0];
  if(m){m.classList.add('hot');pick.textContent=m.getAttribute('aria-label')+'.';
   document.getElementById('map').scrollIntoView({block:'nearest',behavior:reduce?'auto':'smooth'})}})});
render();
})();
</script>
</body>
</html>
"""


def render(data, cfg):
    schools, jobs, today = data["schools"], data["jobs"], data["today"]
    radius = max([cfg.radius_miles] + [s["miles"] for s in schools.values() if s["miles"]])
    n_sch = len(schools)
    if jobs:
        near = sum(1 for j in jobs if j["drive_minutes"] <= 30)
        hiring = len({j["cds_code"] for j in jobs if j["cds_code"] in schools})
        title = "Your chart: " + ui.count(len(jobs), "job") + " in range"
        lead = (f"{ui.count(near, 'job')} within 30 minutes, nearest first. "
                f"{ui.count(hiring, 'school')} hiring, among the {n_sch:,} in range.")
    else:
        title = "Your chart: no jobs in range" if data.get("fetched", True) else "Your chart: no listings fetched yet"
        lead = f"{n_sch:,} schools in range are on the chart."
    soon = lambda j: j["days_left"] is not None and j["days_left"] <= SOON_DAYS
    chips = [f'<li><button type="button" class="chip" aria-pressed="false" data-kind="band" data-band="{i}">'
             f'<svg class="sw b{i}" viewBox="-11 -11 22 22" aria-hidden="true"><use href="#g-{g}"/></svg>'
             f'{_e(label)} ({sum(1 for j in jobs if band_of(j["drive_minutes"]) == i)})</button></li>'
             for i, (_, label, g) in enumerate(BANDS)]
    chips.append('<li><button type="button" class="chip" aria-pressed="false" data-kind="kept">'
                 f'Kept only ({sum(1 for j in jobs if j["mark_status"] == "kept")})</button></li>')
    chips.append('<li><button type="button" class="chip" aria-pressed="false" data-kind="soon">'
                 f'Closes within {SOON_DAYS} days ({sum(1 for j in jobs if soon(j))})</button></li>')
    if jobs:
        lst = ('<ul class="chips" aria-label="Filters">' + "".join(chips) + "</ul>"
               '<p class="readonly">To keep or toss a job, use the terminal: <code>' + ui.launcher() + ' edtrawl.py</code>. '
               "This page only shows.</p>"
               '<p class="count" id="count" aria-live="polite"></p><ol class="cards">'
               + "".join(_card(j, today, schools) for j in jobs) + "</ol>")
    else:
        said = ("None of the jobs saved so far are within range." if data.get("fetched", True)
                else "I haven't fetched any job listings yet, so there are no jobs to show.")
        lst = ('<div class="empty"><p>' + said + "</p>"
               "<p>The schools around you are still on the chart. To fetch listings or look again another day:</p>"
               "<p><code>" + ui.launcher() + " edtrawl.py</code></p></div>")
    sources = ("School data: California Department of Education. Listings: edjoin.org."
               + (" Road distances: © OpenStreetMap contributors, routed by OSRM." if data["roads"] else ""))
    page = PAGE
    for key, val in (("__TITLE__", _e(title)), ("__LEAD__", _e(lead)), ("__MAP__", _map(data, radius)),
                     ("__LIST__", lst), ("__SOURCES__", _e(sources)), ("__DATE__", f"{today:%b} {today.day}, {today.year}"),
                     ("__SOON__", str(SOON_DAYS))):
        page = page.replace(key, val)
    return page


def write_chart(conn, cfg, path="edtrawl-chart.html", today=None):
    """Write the chart page to `path` and return the path."""
    page = render(gather(conn, cfg, today or date.today()), cfg)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path
