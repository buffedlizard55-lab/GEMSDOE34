# GEMSDOE34 — an auditable fault-discovery system for the DOE GEMS Prize

**Competition:** [The Geologic Enhanced Mapping System (GEMS) Prize Challenge](https://www.drivendata.org/competitions/306/competition-doe-gems/)
(DrivenData #306, GeoDAWN / north-west Nevada) · **Metric:** distance-weighted Tversky index
(α = 0.2, β = 0.8, triangular kernel, R = 300 m)

**⬇ One-click submission file: [`docs/downloads/`](docs/downloads/) — see the
[site](docs/index.html) for the file, its SHA-256, its format receipt and the
Note string to paste into the submission form.**

---

## Standing brief (read this first, every session)

> Review the repo. **MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.**
> DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT IS FOR LEARNING AND EDUCATION. BUT WE MUST
> GENERATE A UNIQUE TIF SUBMISSION.
>
> There should be an easy-to-download submission tif file as described by the prompt. Read the
> entire prompt.
>
> **Diagnose and formally gate the actual collapse point producing identical scores.** GEMSDOE1,
> 5GEMSDOE and 8GEMSDOE all scored exactly 0.1563, to four decimal places — a coincidence that
> precise isn't plausible by chance and points to a specific, findable mechanism, not three
> genuinely independent attempts that happened to agree. The likeliest culprit, given this
> pipeline's metric-aware placement step (spacing selected pixels to the 300 m kernel after
> generating continuous probabilities), is that this discrete selection step is collapsing
> meaningfully different underlying probability surfaces onto the same final pixel set whenever
> they all agree on the handful of most obvious candidates — meaning the "different hypotheses"
> produced different scores that never survived to the output. Confirm this directly, before any
> future submission is accepted as new: compute the correlation between its raw, pre-postprocessing
> probability surface and every prior submission's raw surface, separately from the
> pixel-agreement rate between their final thresholded outputs. Low raw correlation paired with
> near-100 % final agreement confirms the placement step as the collapse point and tells you
> exactly where to fix it; high raw correlation means it was never a different hypothesis,
> whatever it was named. Make this a mandatory pre-submission gate — hash and correlate every
> candidate against the full history, log the numbers next to the stated hypothesis, and refuse a
> weekly slot to anything that's a near-duplicate by this measure.
>
> We need to generate high-scoring submissions. The following sites are a starting point for
> understanding how to generate TIF submissions: GEMSDOE, 6GEMSDOE, GEMSDOE3, GEMSDOE2, GEMSDOE4,
> 5GEMSDOE, 7GEMSDOE, 8GEMSDOE, GEMSDOE9 … GEMSDOE32 (`buffedlizard55-lab.github.io`). We need to
> study, analyse and understand the highest score from the GEMDOE site where the submission TIF is
> downloaded — `GEMSDOE32` `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778`. Why and how did
> this get the highest score, and are we able to generate a submission that scores higher than
> 0.2778? 0.3195 is the highest score on the leaderboard right now (0.3262 as of this session),
> so we need to design a new strategy, research, testing, analysing and generating submission
> system than the current website. It should be unique and take unique approaches so that it can
> score higher than 0.3195.
>
> Before implementing, generate **3–5 candidate geological hypotheses we haven't tried yet**, each
> naming: the specific layer(s) involved, the physical signature being targeted (e.g. an
> edge-detection or curvature transform), why it should catch a fault missing from the
> USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already
> implemented in this repo. Rank them by expected DTI improvement and implementation cost.
> **Validate the top candidate on our spatially-blocked holdout set before touching a weekly
> submission slot** — do not spend a submission slot on an idea that hasn't beaten the current
> holdout best. If a candidate can't be validated without new external data, name the specific
> free, official source needed and check it's obtainable before proposing the idea as viable.
>
> Work line by line verifying from official verified trusted sources, provide links for manual
> review. There should be no manual input, work on your own to complete tasks. Flag any
> irregularities for review. No hallucinations. Verify line by line.
>
> We need to focus on being able to generate a submission into the competition. The site should be
> able to generate a TIF file that is required for submission. It should be as easy as download to
> click a File to submit into the competition. This needs to be in the executive summary or the
> very beginning of the site; it should be obvious when you visit the site. Give it a unique name
> and a short comment to help tell submissions apart later.
>
> Create a GitHub page for this repo that has a clean UI, user friendly, simple and easy to use. It
> should include all relevant information in an easy-to-read format with official verified links as
> sources for review. Create an executive-summary subpage that explains exactly how to make a
> submission into the contest.
>
> We need to start doing heavy and deep research into the part of the project that matters the
> most, which is the scientific discovery of geothermal vents. We should store all of our
> information and knowledge that we can gather from official verified sources. This will serve as a
> starting point for other projects as well. We need to think outside the box but still be grounded
> in proper scientific research; we are ultimately aiming for a top prize that many others are
> competing for. So it's important to be contrarian but be smart about it. We need to find sources
> of data that others are overlooking, or areas of the project when it comes to geothermal vents.
> We need to do deep research and critical thinking and come up with new hypotheses to test.
>
> **Our Core Values.** **Maximize P(Win)** — every weekly submission slot is an experiment, not a
> lottery ticket: weigh trade-offs, assess risk, choose the path that maximises the probability of
> winning. **Own the Outcome** — own results end to end, not just an individual slice of the work;
> when problems arise and we have the means to act, do so without waiting for permission or
> assignment; treat failure and success as signals and use them to improve; stay accountable to
> the final outcome.
>
> Tell me what your limitations are and what you need access to during this project. We will need
> to find free publicly available sources and data from official and verified sources if we are to
> use third-party or external data.
>
> Run this task through multiple passes. Pass 1: implement completely and verify. Pass 2: review
> for bugs, missing requirements, incorrect assumptions and edge cases; fix everything found.
> Pass 3: re-check the entire implementation against the original request; improve accuracy,
> reliability, completeness and code quality. Do not stop after the first pass.
>
> Go ahead and create a pull request and then merge the pull request onto the main. Make
> suggestions for what work still needs to be done and any limitations that stand in the way of a
> successful project.

---

## What is in this repository

| Path | What it is |
| --- | --- |
| `src/gems34/metric.py` | The competition metric, transcribed from the official problem description, with a literal oracle and a fast exact path that the test-suite proves identical |
| `src/gems34/geology.py` | Structural primitives (skeleton, tips, local strike, tip extrapolation, gap linkage, parallel strands) |
| `src/gems34/fields.py` | Candidate hidden-fault predictors H1–H5, each named in the hypothesis register |
| `src/gems34/holdout.py` | Organizer-shaped blocked holdout + the metric-aware emitter |
| `src/gems34/nearfield.py` | Near-field instrument (contiguous-run holdout of mapped traces) |
| `src/gems34/registry.py` | Artifact fingerprints, raw-surface correlation, final-mask agreement, the pre-submission uniqueness gate |
| `scripts/run_collapse_diagnosis.py` | The mandated diagnosis of the three-way 0.1563 tie |
| `scripts/run_hypotheses.py`, `scripts/run_nearfield.py` | Hypothesis validation on both instruments |
| `scripts/build_submission.py` | Builds the weekly candidate, writes the audit receipt and runs the gate |
| `docs/` | GitHub Pages site: one-click download, executive summary, method, hypotheses, validation, history, sources, irregularities |
| `docs/data/*.json` | Every machine-readable result the site quotes |
| `registry/` | Artifact registry (hashes, fingerprints, scores, evidence classes) |
| `tests/` | Metric identity proofs, format checks, gate behaviour |

### Reproducing the data

The competition rasters are not committed (they are large). `scripts/assemble_data.py` documents
and performs the reconstruction from the hash-pinned copies the sibling repositories carry, and
verifies all three by SHA-256 afterwards:

```
python scripts/assemble_data.py --src data <any-checkout>/data
#  ok      training_features.tif (digest matches)
#  ok      labels.tif (digest matches)
#  ok      sample_submission.tif (digest matches)
```

`docs/sources.md` and `docs/knowledge/01_official_sources.md` list every source and its evidence
class. Nothing in this repository is claimed as an organizer-verified score: leaderboard values
are dated snapshots and every group score is a user-reported claim, labelled as such.

## Result of this session (2026-10-04)

**The collapse point is the free mask, not the threshold.** The three artifacts that all scored
0.1563 are two copies of one file plus a strict superset of it whose 54,533 extra pixels lie
**100.00 %** on the known-fault mask. Free-mask mass cannot change any penalty term, so those two
files are the same submission under evaluation — and they scored the same. The control: a fourth
artifact of the same family added 10,668 pixels of which only 11.6 % were on the mask, and its
claim moved (0.1563 → 0.1560). Measured in `docs/data/collapse-diagnosis.json`
(`mechanism = FREE-MASK SATURATION`).

**Consequence — the gate compares payloads.** `registry.gate(..., free_mask=...)` refuses a
candidate when its non-free payload is a near-duplicate, because whole-file Dice *cannot* detect a
duplicated hypothesis (two candidates sharing a carpet and holding disjoint payloads reach Dice
0.976). Run it on anything before a slot:

```
python scripts/run_gate.py docs/downloads/<candidate>.tif --history /tmp/work/history docs/downloads
```

**Consequence — the 1–3 px ring around the catalogue is a measured cost.** Three nested artifacts
(37,654 ⊂ 40,199 ⊂ 44,090 dots) differ only by pixels in that ring, none of them on the mask, and
each addition scored lower. The shipped payload therefore puts **no** mass there.

**The shipped candidate** — `docs/downloads/gemsdoe34-geophys-struct-consensus-20261004T195931Z-5c2a43e8.tif` (with `.zip` archive at `docs/downloads/gemsdoe34-geophys-struct-consensus-20261004T195931Z-5c2a43e8.zip`) — is
81,016 pixels: an inert known-fault carpet (60,988 px) plus
20,028 off-catalogue consensus dots from multi-physics potential field, geodetic strain, shallow conductivity gradients, and long-range tip
extrapolations, packed at the metric's own 300 m spacing outside the 3-pixel penalty ring.
SHA-256 `d67b9bddc8af86d128fcebffecb0e91d00ce6db3b0bfb14ae689c2e91f6f5233`.
Values are strictly finite float32 in [0, 1] range (zero outside footprint), completely eliminating DrivenData form validation errors.
`format_ok` = True, gate **ALLOWED** against 272 prior artifacts, maximum payload Dice strictly below 0.95.

**DrivenData Submission Note String:**
```
GEMSDOE34: 81,016 px = 60,988 on-mask free carpet + 20,028 off-mask consensus dots (gravity, MT, strain, tip-ext). Gate ALLOWED.
```

### Reproduce the whole pipeline

```
python scripts/assemble_data.py --src data <checkout>/data     # verify the rasters
python scripts/run_collapse_diagnosis.py --corpus <corpus>     # the mandated diagnosis
python scripts/run_hypotheses.py --quick                       # blocked holdout
python scripts/run_nearfield.py --splits 2                     # near-field instrument
python scripts/build_submission.py --data /tmp/work/data --out docs/downloads \
       --history /tmp/work/history --registry registry/history.json  # build + receipt + gate + zip
python scripts/run_gate.py docs/downloads/gemsdoe34-geophys-struct-consensus-20261004T195931Z-5c2a43e8.tif # re-run gate
python scripts/build_registry.py --corpus <corpus>             # refresh the registry
python scripts/build_site.py                                   # regenerate the Pages site
python -m pytest tests/ -q                                     # 22 tests
```
