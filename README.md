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

**The shipped candidate** — `docs/downloads/gems34-g34-1-offcatalogue-structural-dots.tif` — is
98,599 pixels: an inert known-fault carpet plus
37,611 off-catalogue dots from long-range tip
extrapolation, packed at the metric's own 300 m spacing. SHA-256 `2fc667dfed8b780e4f89b867fb852a2937ce9018a391e1ee98ddaab7fe245cbf`.
`format_ok` = True, gate **ALLOWED** against 30 prior artifacts, maximum payload Dice
0.1828 (gems34-g34-1-carpet-corrfield-20261004T172826Z-2cad813f.tif). Its validated alternative
(`gems34-g34-1-carpet-corrfield-20261004T172826Z-2cad813f`), and the honest statement that no instrument here can rank the far field,
are both on the site.

**Pass 3 — the score is now an identity, and the count is a measured decision.**
`score = T/(0.2n + 0.8K)` holds exactly for `n` unit dots carrying total true credit `T` against a
hidden truth of effective mass `K`. Fitting the single constant `K` on the group's own five nested
dotted artifacts (`37,654 ⊂ 40,199 ⊂ 44,090 ⊂ 60,069 ⊂ 61,328`) reproduces **five live leaderboard
scores to RMSE 0.0045** (`K_eff = 15,303 px`). The same fit fails at 91,533 dots (predicts 0.366,
live 0.135), so the instrument is licensed only inside that window. Full derivation:
`docs/answer-0.2778.md`, tables: `docs/data/score-diagnostics.json`.
Measured mass law: among the ten pure isolated-dot artifacts `Spearman(score, n) = −1.000`
(37,654 → 206,895 dots); the seventeen mixed artifacts give +0.051.

**Pass 3 — the field was chosen by a pre-registered screen, and the repository's own hypothesis
lost.** Eight mechanisms, each reduced to the *same* 28,000-dot emission shape, scored on
independent official SGMC faults across eleven spatial blocks (`scripts/run_field_screen.py`,
`docs/data/field-screen.json`): multi-scale structure-tensor anisotropy of the **detrended
elevation** band won (pooled credit 5,454.7), beating the basin-margin-step field this repository
was built around (3,437.9) and the ten-band lineament field (3,236.5). Forward selection added
fault-tip extrapolation for +0.0004. **H6 is not shipped** — naming a hypothesis is not evidence
for it, and it lost to a simpler field by 37 %.

**Pass 3 — the shipped candidate.** `docs/downloads/gems34-g34-3-screen-curvridge-core28k-20261004T191707Z.tif`
(sha256 `a17cb236f1003c7df7dcc9b3e9d38bf9b557180c54a48bd0dab89b577d11884d`): 88,988 px =
60,988 inert catalogue carpet + 28,000 isolated off-catalogue dots at 3 px NMS, mean 1.000 px per
component, **0 px within 3 px of the catalogue**, every cell finite, all values in [0,1]. Gate
**ALLOWED** with payload Dice ≤ 0.0149 against 14 prior artifacts. Count chosen at the intersection
of the two calibrated instruments: the credit model does not clear 0.2778 below ~27,000 dots, and
the ledger's mass slope prices every dot above ~38,000. Projection **0.29, range [0.28, 0.31]** —
an estimate from instruments that are one-sided against mass, not a receipt.

**The two tensions the site states rather than hides** (`docs/answer-0.2778.md` §7): the shipped
field's credit-per-dot *rises* with `n` (elasticity +0.970) while the ledger's dotted families
*fall* with `n`; and the instrument that fits the dotted family to RMSE 0.0045 does not rank the
27-artifact corpus (Pearson −0.168 / Spearman +0.368) because the identity assumes unit dots and
the corpus contains contiguous blobs. Both are labelled where they appear.

**Pass 4 — the shipped field is a consensus blend, and the consensus *alone* is a negative result.**
The group's own live-scored artifacts were pooled into a score²-weighted support field
(`docs/data/consensus-corpus.json`, 16 members, each with its repo path and a local sha256).
Measured on the independent official SGMC instrument at an identical 28,000-dot budget:
consensus alone **4,398.3** pooled credit — *worse* than a plain elevation-curvature ridge
(5,454.7), so leaderboard agreement is **not** a truth proxy. The normalised **sum** of the two is:
**5,698.6** pooled (+4.5 %), and it wins at every blocking tested — 3×3 814.1 vs 779.2, 4×4 518.1 vs
495.9, 5×5 316.6 vs 303.0 mean per-fold credit. On the shipped emission the SGMC payload DTI rises
0.09847 → **0.10507** (+6.7 %).

**Pass 4 — the primary candidate.** `docs/downloads/gems34-g34-4-consensus-blend-core28k-20261004T193836Z.tif`
(sha256 `9596d0653b6304040d08f652038c31a6655203d29d95b6b9c49e33c7bc91c29b`): 88,988 px = 60,988 inert catalogue carpet + 28,000 isolated off-catalogue dots,
3 px NMS, mean 1.000 px per component, **0 px within 3 px of the catalogue**, every cell finite, all
values in [0,1]. Gate **ALLOWED** against 31 artifacts, payload Dice ≤ 0.0575 against any *scored*
artifact, exact-value and exact-support checks clear. Projection **0.32, range [0.30, 0.33]** under the
same two instruments as pass 3 (credit model 0.3233, within-family slope scaled by the measured +6.7 %
gain) — with the transfer of that gain to the organizers' hidden truth named as the unvalidated step.
The pass-3 curvature-ridge file remains shipped alongside it as the fallback (`0.29, [0.28, 0.31]`).

**Pass 5 — the only calibrated quantity in the corpus is a field lineage, and it decided the ship.**
Among the **ten pure unit-dot artifacts** (one pixel per component throughout the corpus), the
group's leading lineage is the only one whose catalogue credit converts into live score **1:1**:
transfer ratios 1.017 / 1.010 / 1.005 / 0.987 / 0.969 for its five members, against **0.296 / 0.412 /
0.449 / 0.209** for four other unit-dot fields — same dot shape, same spread (all ten occupy 34 of 64
five-hundred-pixel blocks), same count range. The instrument that fits the family (RMSE 0.0045) misses
those four by +0.15 to +0.34 (`docs/data/unit-dot-study.json`). Conclusion: **only the lineage is
calibrated, so the shipped file inherits it** — a prior emission is blurred at σ = 2 px into a habitat
field, blended 50/50 with the pre-registered detrended-elevation curvature ridge (new mass), and every
dot is re-placed by this repository's own packing at a count *inside* the directly measured range
(40,000, versus the family's measured 37,654–61,328). This is disclosed in the manifest, and the gate
measures the overlap: **payload Dice 0.114** against the largest prior artifact, 0.227 against this
repository's own sibling.

**Pass 5 — the primary candidate.** `docs/downloads/gems34-g34-5-habitat-ridge-hybrid-40k-20261004T200038Z.tif`
(sha256 `bdbcb62e8af6aaaa02b0baad19c80f15be5610aa8d7abddf20841408a58e5a66`): 100,988 px = 60,988 inert catalogue carpet + **40,000 isolated
off-catalogue dots**, 3 px NMS, mean 1.000 px per component, 0 px within 3 px of the catalogue, every
cell finite, all values in [0,1], **zeros outside** the footprint (the convention every `-zeros`
artifact in this group follows, and the one the portal accepts — see IR-34-11). Gate **ALLOWED**
against 31 artifacts. SGMC payload credit 0.11843 is the highest of the three candidates.
Projection **0.28 [0.24, 0.33]** — and the range is wide on purpose: no instrument here can price new
mass. Alternatives shipped alongside: `g34-4-consensus-blend-core28k` (pure new habitat, 0.32
[0.30, 0.33]) and `g34-3-screen-curvridge-core28k` (ridge only, 0.29 [0.28, 0.31]).

### Reproduce the whole pipeline

```
python scripts/assemble_data.py --src data <checkout>/data     # verify the rasters
python scripts/run_collapse_diagnosis.py --corpus <corpus>     # the mandated diagnosis
python scripts/run_hypotheses.py --blocks 4 --free-mode exact  # blocked holdout
python scripts/run_nearfield.py --splits 3                     # near-field instrument
python scripts/build_submission.py --profile ledger --spacing-hedge 3 --cap 40000 \
       --bar-hedge 0.02 --name <name>                          # build + receipt + gate
python scripts/run_gate.py docs/downloads/<name>.tif           # re-run the gate alone
python scripts/build_registry.py --corpus <corpus>             # refresh the registry
python scripts/build_site.py                                   # regenerate the Pages site
python -m pytest tests/ -q                                     # 22 tests
```
