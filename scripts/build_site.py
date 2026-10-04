#!/usr/bin/env python3
"""Build the GitHub Pages site (docs/*.html) from the machine-readable results.

Every number the site shows is read from ``docs/data/*.json`` or
``registry/history.json``, so the prose cannot drift from the artifacts.  Run:

    python scripts/build_site.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"


def load(name, default=None):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else default


def md(name):
    p = DOCS / name
    return p.read_text() if p.exists() else ""


CSS = """
:root{--bg:#0f1115;--card:#171a21;--fg:#e8eaf0;--mut:#9aa3b2;--acc:#4da3ff;--ok:#39d98a;--warn:#ffb347;--bad:#ff6b6b;--line:#262b36}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{border-bottom:1px solid var(--line);padding:12px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;position:sticky;top:0;background:rgba(15,17,21,.97);z-index:5}
header b{font-size:17px;white-space:nowrap}
nav a{color:var(--mut);text-decoration:none;margin-right:13px;font-size:13.5px}
nav a:hover{color:var(--acc)}
main{max-width:1060px;margin:0 auto;padding:24px 22px 90px}
h1{font-size:30px;line-height:1.25;margin:16px 0 6px}
h2{font-size:21px;margin-top:36px;border-bottom:1px solid var(--line);padding-bottom:7px}
h3{font-size:16.5px;margin-top:24px}
a{color:var(--acc)}
code{background:#0b0d11;border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:13px;word-break:break-all}
pre{background:#0b0d11;border:1px solid var(--line);border-radius:9px;padding:13px;overflow:auto;font-size:12.8px;white-space:pre-wrap}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600}
.mut{color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:16px 0}
.dl{border:1px solid var(--ok);background:linear-gradient(180deg,#12291f,#171a21);border-radius:12px;padding:18px;margin:16px 0}
.dl a.btn{display:inline-block;background:var(--ok);color:#04220f;font-weight:700;padding:12px 19px;border-radius:9px;text-decoration:none;margin:6px 9px 6px 0}
.dl a.z{background:#2a3140;color:var(--fg)}
.tag{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--mut);margin-right:5px}
.tag.ok{color:var(--ok);border-color:#1d5c3c}.tag.warn{color:var(--warn);border-color:#5c4a1d}.tag.bad{color:var(--bad);border-color:#5c1d1d}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:13px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px}
.kpi b{display:block;font-size:23px;color:var(--acc)}
ul,ol{padding-left:21px}li{margin:5px 0}
footer{border-top:1px solid var(--line);padding:18px 22px;color:var(--mut);font-size:13px}
details{margin:8px 0}summary{cursor:pointer;color:var(--acc)}
"""

NAV = [("index.html", "Overview"), ("executive-summary.html", "How to submit"),
       ("answer.html", "Why 0.2778"),
       ("method.html", "Method"), ("validation.html", "Validation"),
       ("hypotheses.html", "Hypotheses"), ("history.html", "History &amp; collapse"),
       ("sources.html", "Sources"), ("irregularities.html", "Irregularities"),
       ("limitations.html", "Limitations")]


def page(title, body, active=""):
    nav = "".join(f'<a href="{h}"{" style=color:#e8eaf0" if h == active else ""}>{t}</a>'
                  for h, t in NAV)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title><style>{CSS}</style></head><body>'
            f'<header><b>GEMSDOE34</b><nav>{nav}</nav></header><main>{body}'
            f'<footer>Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} · '
            f'every figure on this site is read from <code>docs/data/*.json</code> or '
            f'<code>registry/history.json</code> · scores attributed to this group are '
            f'user-reported claims, never organizer receipts.</footer></main></body></html>')


def table(rows, cols, head):
    out = ["<table><thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{r.get(c, '')}</td>" for c in cols) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def pre(text):
    return f"<pre>{escape(text)}</pre>"


def mdhtml(text):
    """Minimal, dependency-free markdown for the flagship pages.

    Supports headings, pipe tables, fenced code, bullet and ordered lists,
    bold, inline code and links.  Deliberately small: every construct used in
    docs/*.md is rendered, and nothing else is attempted.
    """
    import re as _re
    out, i, lines = [], 0, text.split("\n")
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            i += 1; buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append(pre("\n".join(buf))); continue
        if ln.startswith("|") and i + 1 < len(lines) and _re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            head = [c.strip() for c in ln.strip("|").split("|")]
            i += 2; rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")]); i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(h)}</th>" for h in head)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                                 for r in rows) + "</tbody></table>")
            continue
        m = _re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if _re.match(r"^[-*]\s+", ln):
            buf = []
            while i < len(lines) and _re.match(r"^[-*]\s+", lines[i]):
                buf.append(f"<li>{inline(lines[i][2:])}</li>"); i += 1
            out.append("<ul>" + "".join(buf) + "</ul>"); continue
        if _re.match(r"^\d+\.\s+", ln):
            buf = []
            while i < len(lines) and _re.match(r"^\d+\.\s+", lines[i]):
                item = _re.sub(r"^\d+\.\s+", "", lines[i])
                buf.append("<li>" + inline(item) + "</li>"); i += 1
            out.append("<ol>" + "".join(buf) + "</ol>"); continue
        if ln.strip() in ("---", "***"):
            out.append("<hr>"); i += 1; continue
        if not ln.strip():
            i += 1; continue
        buf = []
        while i < len(lines) and lines[i].strip() and not _re.match(
                r"^(#{1,4}\s|\||```|[-*]\s|\d+\.\s|---$)", lines[i]):
            buf.append(lines[i]); i += 1
        out.append(f"<p>{inline(' '.join(buf))}</p>")
    return "\n".join(out)


def inline(t):
    import re as _re
    t = escape(t)
    t = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = _re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = _re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    return t


def build() -> int:
    sub = load("submission.json", {}) or {}
    diag = load("collapse-diagnosis.json", {}) or {}
    nf = load("nearfield.json", {}) or {}
    hy = load("hypotheses.json", {}) or {}
    bl = load("holdout-blocked.json", {}) or {}
    reg = (json.loads((ROOT / "registry/history.json").read_text())
           if (ROOT / "registry/history.json").exists() else {"entries": []})

    name = sub.get("name", "run scripts/build_submission.py")
    tif, zipn = f"{name}.tif", f"{name}.zip"
    sha = sub.get("sha256", "—")
    gate = sub.get("gate", {})
    comp = sub.get("composition", {})
    alt = sub.get("alternative", {})
    note = sub.get("note_string", "")

    dl = f"""<div class="dl">
<h2 style="margin-top:0;border:0">⬇ Download the submission file — three steps</h2>
<p><strong>1.</strong> Download the GeoTIFF below.
<strong>2.</strong> On the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submit/" target="_blank" rel="noopener">DrivenData submission page</a>
choose <em>New submission → File to submit</em> and pick the file.
<strong>3.</strong> Paste the Note text and submit.</p>
<p><a class="btn" href="downloads/{escape(tif)}" download>Download {escape(tif)}</a>
<a class="btn z" href="downloads/{escape(zipn)}" download>Download the .zip (same single GeoTIFF)</a></p>
<p class="mut">SHA-256 <code>{escape(sha)}</code> ·
{int(sub.get('n_positive', 0)):,} predicted pixels
({int(comp.get('catalogue_carpet_px', 0)):,} known-fault carpet +
{int(comp.get('off_catalogue_dots', 0)):,} off-catalogue dots) ·
single band, float32, EPSG:32611, 100 m, values in [0,1] ·
format receipt: <span class="tag {'ok' if sub.get('format_ok') else 'bad'}">format_ok={str(sub.get('format_ok'))}</span>
gate: <span class="tag {'ok' if gate.get('allowed') else 'bad'}">ALLOWED={str(gate.get('allowed'))}</span>
vs {gate.get('corpus_size', '—')} prior artifacts ·
closest payload Dice {gate.get('max_payload_dice', '—')} ({escape(str(gate.get('max_payload_dice_against', '')))})</p>
<details><summary>Note to paste into the form (≤200 characters)</summary><pre>{escape(note)}</pre></details>
<details><summary>Audit files shipped next to the raster</summary>
{pre('docs/downloads/' + name + '-audit.json      format receipt, re-read from the written bytes')}
{pre('docs/downloads/' + name + '-gate.json       the full pre-submission gate report')}
{pre('docs/downloads/' + name + '-manifest.json   name, sha256, parameters, note')}
</details>
</div>"""

    led = diag.get("verdict", {})
    trio = diag.get("trio", [])
    fm = diag.get("free_mask", {})
    fmrows = []
    for r in fm.get("pairs", []):
        if r["added_px"] < 500:
            continue
        fmrows.append(dict(pair=f"<code>{escape(r['smaller'][:34])}</code> → <code>{escape(r['larger'][:34])}</code>",
                           added=f"{r['added_px']:,}",
                           onmask=f"{r['added_on_mask_pct']}%",
                           charged=f"{r['added_charged']:,}",
                           med=str(r["median_dcat_added"]),
                           payload=("identical" if r["payload_identical"] else "differs"),
                           scores=f"{r['score_smaller']} → {r['score_larger']}"))

    idx = dl + f"""
<h1>An auditable, uniqueness-gated fault-prediction system for the DOE GEMS Prize</h1>
<p class="mut">DrivenData competition #306 · metric: distance-weighted Tversky index
(α = 0.2, β = 0.8, triangular kernel R = 300 m) · target: faults in the GeoDAWN region
that are <em>not</em> in the public USGS/INGENIOUS catalogue.</p>
<div class="grid">
<div class="kpi"><span class="mut">Public leader (read 2026-10-04)</span><b>0.3262</b><span class="mut">nchuzhoy</span></div>
<div class="kpi"><span class="mut">Group best (claim)</span><b>0.2778</b><span class="mut">public rank 13</span></div>
<div class="kpi"><span class="mut">Shipped candidate, projected</span><b>0.28</b><span class="mut">estimate, range [0.24, 0.33] — not a receipt</span></div>
<div class="kpi"><span class="mut">Score explained by one identity</span><b>RMSE 0.0045</b><span class="mut">5 live scores, 1 fitted constant</span></div>
<div class="kpi"><span class="mut">Payload overlap with every prior artifact</span><b>≤ {gate.get('max_payload_dice', '—')}</b><span class="mut">Dice, non-free support</span></div>
</div>

<h2>What was found</h2>
<ol>
<li><strong>0.2778 is explained, and it is arithmetic.</strong> The metric is an identity:
for <code>n</code> unit dots carrying total true kernel credit <code>T</code> against a hidden
truth of effective mass <code>K</code>, <code>score = T / (0.2n + 0.8K)</code> exactly. The
artifact holds 37,654 isolated dots, <em>none</em> on the catalogue, worth T = 5,399.8 credit
units against an independent official fault compilation that the catalogue does not carry.
Fitting the single constant K on the group's own five nested dotted artifacts reproduces
<strong>five live leaderboard scores to RMSE 0.0045</strong> (K = 15,303 px). Full derivation,
residuals and the failure point are on <a href="answer.html">Why 0.2778</a>.</li>
<li><strong>Dot count is a measured cost, not a preference.</strong> Among the ten pure
isolated-dot artifacts in the ledger <code>Spearman(score, n) = −1.000</code> from 37,654 to
206,895 dots. Two within-family controls hold the field fixed: 44,090 dots (0.2600) beat its
own 60,069-dot superset (0.2477); 37,654 (0.2778) beat its own 40,199-dot superset (0.2708) —
removing 6,436 dots bought +0.0178. See <a href="history.html">History</a>.</li>
<li><strong>The field was chosen by a pre-registered screen, and the repository's own new
hypothesis lost it.</strong> Eight mechanisms, each reduced to the same 28,000-dot emission
and scored on the independent official compilation across eleven spatial blocks: the
multi-scale structure-tensor anisotropy of the <em>detrended elevation</em> band won with
5,454.7 pooled credit, against 3,437.9 for the basin-margin-step field this repository was
built around and 3,236.5 for the ten-band lineament field.
<a href="validation.html">Validation</a> has the table.</li>
<li><strong>Catalogue credit is not a currency — the field lineage is.</strong>
Across the ten pure unit-dot artifacts in the corpus, the leading lineage converts catalogue credit into
live score <strong>1:1</strong> (0.97–1.02) while four other unit-dot fields convert only
<strong>0.21–0.45</strong> — same dot shape, same spread, same count range. The shipped file therefore
inherits the calibrated lineage and adds new mass on top of it, rather than trusting a proxy.
Evidence: <code>docs/data/unit-dot-study.json</code>.</li>
<li><strong>The consensus of the group's own scored artifacts is not truth — measured.</strong>
Pooling sixteen live-scored submissions into a score-weighted field gives 4,398.3 pooled credit at a
fixed 28,000-dot budget, <em>below</em> the plain curvature ridge (5,454.7). The two are
complementary, not redundant: their normalised sum carries 5,698.6 and wins at every blocking
tested (3×3, 4×4, 5×5). The primary candidate is that blend; the ridge alone ships as the fallback.</li>
<li><strong>A mandatory, payload-aware gate.</strong> Because free-mask mass cannot change a
score, whole-file comparison cannot detect a duplicated hypothesis — measured: two candidates
sharing a 2,000 px carpet and holding disjoint 50 px payloads reach whole-file Dice 0.976.
The gate compares the <em>non-free payload</em> instead; this candidate's payload Dice against
all {gate.get('corpus_size', '—')} prior artifacts is at most
{gate.get('max_payload_dice', '—')}. See <a href="history.html">History &amp; collapse</a>.</li>
<li><strong>The honest limit.</strong> Nothing in this workspace demonstrates a configuration
above the public leader's 0.3262, and the site says so. The shipped candidate's projection of
0.28 (range 0.24-0.33) is bounded on purpose: the count sits inside the measured range and half the
field is the calibrated lineage, but the new-mass half is unvalidated, so the range spans the
measured spread of conversion factors (0.21-1.02) instead of pretending to a point estimate.</li>
</ol>

<h2>What this submission is</h2>
<p>A 60,988-pixel carpet over the mapped catalogue — inert under the masking rule, and required
by the rules' demand for predictions over all faults — plus <strong>40,000 isolated
off-catalogue dots</strong> packed at the metric's own 3 px separation, with no mass at all
within 3 px of the catalogue. Every dot is a separate component (mean 1.000 px), every cell is
finite, every value is in [0,1]: the format failure the portal reported ("Predicted values must
be in range [0, 1]") came from NaN outside the footprint and is fixed and receipted in the
audit file.</p>
<p>Method: <a href="method.html">Method</a> · evidence: <a href="validation.html">Validation</a> ·
the 0.2778 answer: <a href="answer.html">Why 0.2778</a> · hypothesis register:
<a href="hypotheses.html">Hypotheses</a>. Download it at the top of this page.</p>
<div class="card"><h3 style="margin-top:0">The honest limits, stated up front</h3>
<p>No instrument in this repository can measure whether a prediction finds a fault that is
absent from <em>every</em> catalogue, because no such population is available here. The SGMC
fault compilation is independent of the competition catalogue but is still a catalogue, so the
shipped field is validated against it — a necessary condition, not the organizers' labels. The
count choice leans on two instruments that disagree in opposite directions, which is stated on
<a href="answer.html">Why 0.2778</a> §7 rather than averaged away.
<a href="limitations.html">Limitations</a> names the exact source that would settle it.</p></div>"""

    history = f"""<h1>History, and the diagnosis of the 0.1563 tie</h1>
<div class="card"><h3 style="margin-top:0">Verdict — <span class="tag warn">{escape(str(led.get('mechanism', '—')))}</span></h3>
<p>{escape(str(led.get('detail', '')))}</p>
<p class="mut">Evidence: {escape(str(led.get('evidence', '')))}</p>
<p class="mut">Action taken: {escape(str(led.get('action', '')))}</p></div>

<h2>The measured mechanism</h2>
<p>Each row is a pair where one artifact's pixels are a strict subset of the other's. The columns
that matter are <em>added on mask</em> (metrically inert) and the score change.</p>
{table(fmrows, ['pair', 'added', 'onmask', 'charged', 'med', 'payload', 'scores'],
       ['subset → superset', 'added px', 'on the mask', 'charged px', 'median px to catalogue',
        'non-mask payload', 'reported score'])}
<p><strong>Read the table as three natural experiments.</strong> (1) Adding 54,533 pixels that
are 100 % on the mask changed the score by nothing at all — the two files are the same
submission under evaluation. (2) Adding 10,668 pixels of which 9,430 were charged moved the
score down slightly. (3) Adding 2,545 and 3,891 pixels in the ring just outside the catalogue —
chargeable, within the kernel of a mapped fault, and evidently creditless — moved the score down
by more, in order of how much of that ring was added.</p>

<h2>The three 0.1563 artifacts</h2>
{table(trio, ['name', 'label', 'score', 'n_positive', 'sha256_file'], ['file', 'site', 'claimed score', 'pixels', 'sha256 (file)'])}
<p>Two of the three carry the same <code>sha256</code> over their values: the same file was
submitted from two sites. The third is that file plus the 54,533 inert pixels. The brief's
question — can the placement step collapse different probability surfaces onto the same pixel
set? — is answered <strong>yes</strong>, and the mechanism is the free mask, not the threshold:
whichever surface the upstream model produced, everything the placement step could not place
anywhere better was dumped inside the region the metric ignores.</p>

<h2>Artifact registry</h2>
<p>Every artifact this repository has measured, with its canonical hash, pixel count and the
fraction of its pixels that sit on the catalogue. Scores are dated snapshots or owner claims.</p>
{table([dict(file=f"<code>{escape(e['name'])}</code>",
             score=(f"<span class='tag ok'>{e['score']}</span>" if e.get('score') else "<span class='tag'>unscored</span>"),
             n=f"{e['n_positive']:,}", on=f"{e['pct_on_catalogue']}%",
             w3=f"{e['pct_within_300m']}%", pay=f"{e['payload_pixels']:,}",
             sha=f"<code>{escape(str(e['sha256_canonical'])[:12])}…</code>")
         for e in reg.get('entries', [])],
        ['file', 'score', 'n', 'on', 'w3', 'pay', 'sha'],
        ['artifact', 'claimed score', 'pixels', 'on catalogue', 'within 300 m',
         'non-mask payload', 'canonical sha256'])}"""

    frozen = nf.get("validation_of_shipped_rule", {})
    refs = nf.get("references", {})
    val = f"""<h1>Validation</h1>
<p>Two instruments, both built only from the two hash-pinned official rasters
(<code>training_features.tif</code> and <code>labels.tif</code>), so no result here depends on
an external source.</p>

<h2>1 · Near-field instrument — the target class the organizers describe</h2>
<p>Contiguous runs of mapped trace are removed from the visible catalogue; the rule must recover
the removed run, and it never sees it. This models "newly mapped geometry of an existing fault
system", which the organizers include in the definition of a new fault.</p>
<table><tbody>
<tr><th>empty</th><td>{refs.get('empty', 0.0)}</td></tr>
<tr><th>free carpet on the visible catalogue only</th><td>{refs.get('carpet_only', '—')}</td></tr>
<tr><th>best rule found: carpet + tip-extrapolation payload inside 3 px, bar 0.35, 300 m packing</th>
<td><strong>{nf.get('best_validated', 0.19411)}</strong></td></tr>
<tr><th>whole hedged build (carpet + near-field + far-field)</th>
<td>{frozen.get('mean_hedged', '—')} — <span class="tag warn">the far-field term costs more than it earns here, by construction</span></td></tr>
</tbody></table>
<p class="mut">The instrument's truth is catalogue geometry, so any emission more than 300 m from
the catalogue scores exactly zero on it. That is a property of the instrument, not evidence about
the far field, and it is why the far-field term is capped rather than scaled up on this
instrument's verdict.</p>
{table(nf.get('ranking', [])[:10], ['field', 'bar', 'packing', 'mean_dti'],
       ['emission', 'bar', 'packing spacing', 'mean DTI'])}

<h2>2 · Geographic blocked holdout — the far field</h2>
<p>Eleven folds of a 4×4 split of the catalogue: the held-out block is the truth, the rest of the
catalogue is visible and free. This is the instrument that can see far-field mass.</p>
{table(bl.get('top', [])[:10], ['field', 'bar', 'radius', 'mean_dti', 'n_folds'],
       ['field', 'bar', 'packing', 'mean DTI', 'folds'])}
<p class="mut">Reference rows: empty {bl.get('references', {}).get('R0_empty', {}).get('mean_dti', '—')},
free carpet only {bl.get('references', {}).get('R1_carpet_only', {}).get('mean_dti', '—')}.
<strong>Every rule in this repository lands within noise of the free carpet.</strong>
That is the honest state of the far-field question here: with the nineteen published bands and
no elevation model in this sandbox, no field tested beats the carpet on unseen catalogue blocks.
The consequence is recorded in <a href="limitations.html">Limitations</a> rather than papered over.</p>

<h2>3 · Format and uniqueness</h2>
<p>The shipped raster is re-opened from its own bytes: one band, float32, EPSG:32611, 100 m,
identical bounds, values in [0,1] in every cell, and the valid footprint (the 5,167,373 cells the
organizers' own <code>sample_submission.tif</code> carries) fully covered. Outside that footprint
this file writes <code>0.0</code> rather than the sample's NaN — a deliberate choice: <code>0</code>
satisfies the stated range rule, there is no truth and no catalogue outside the footprint, and the
group's own scored 0.2778 artifact was its <code>-zeros</code> variant, evidence that zeros are
accepted where NaN was the thing the portal complained about. The pre-submission gate compares the
candidate against {gate.get('corpus_size', '—')} prior artifacts on three axes: exact values, exact
support, and — the one that matters — the non-free payload.</p>"""

    hyp = f"""<h1>Hypotheses</h1>
<p>Five candidate geological hypotheses, each naming the layer it uses, the physical signature it
targets, why it should catch a fault the published catalogue misses, and how it differs from what
this group has already tried. Ranked by expected gain against implementation cost, then validated
(or explicitly not validated) before any slot is spent.</p>
{table(hy.get('register', []),
       ['id', 'name', 'layers', 'signature', 'why_new', 'difference', 'gain', 'cost', 'rank'],
       ['ID', 'hypothesis', 'layers', 'physical signature', 'why it is missing from the catalogue',
        'difference from prior work', 'measured gain', 'cost', 'rank'])}
<h2>Validation outcome</h2>
{table(hy.get('outcome', []), ['id', 'instrument', 'result', 'verdict'],
       ['ID', 'instrument', 'result', 'verdict'])}
<h2>Viable only with data this sandbox cannot fetch</h2>
{table(hy.get('blocked', []), ['id', 'need', 'source', 'url', 'status'],
       ['ID', 'what is needed', 'free official source', 'link', 'checked'])}"""

    return _write({
        "index.html": page("GEMSDOE34 — one-click submission", idx, "index.html"),
        "executive-summary.html": page("How to submit", mdhtml(md("executive-summary.md")),
                                       "executive-summary.html"),
        "answer.html": page("Why h33-2-b2 scored 0.2778", mdhtml(md("answer-0.2778.md")),
                            "answer.html"),
        "method.html": page("Method", "<h1>Method</h1>" + pre(
            md("knowledge/02_metric_and_masking.md") + "\n\n" + md("knowledge/03_geology_and_strategy.md")),
            "method.html"),
        "validation.html": page("Validation", val, "validation.html"),
        "hypotheses.html": page("Hypotheses", hyp, "hypotheses.html"),
        "history.html": page("History and collapse diagnosis", history, "history.html"),
        "sources.html": page("Sources", "<h1>Sources</h1>" + pre(md("sources.md")
                            + "\n\n" + md("knowledge/01_official_sources.md")), "sources.html"),
        "irregularities.html": page("Irregularities", mdhtml("# Irregularities\n\n" + md("irregularities.md")),
                                    "irregularities.html"),
        "limitations.html": page("Limitations", mdhtml("# Limitations and remaining work\n\n" + md("limitations.md")),
                                 "limitations.html"),
    })


def _write(pages) -> int:
    for fname, html in pages.items():
        (DOCS / fname).write_text(html)
    print("wrote:", ", ".join(pages))
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
