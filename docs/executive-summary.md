# Executive summary

## Submit this file (three steps)

1. **Download** `docs/downloads/h34-scatter-q50-arr-matched-20261004T223317Z.tif`
   (a `.zip` holding the same single GeoTIFF sits next to it).
2. Open the [DrivenData submission portal](https://www.drivendata.org/competitions/306/competition-doe-gems/submit/)
   → **New submission → File to submit** → pick the file.
3. Paste the **Note** below and submit.

```
h34-scatter-q50-arr-matched isolated-px n=37654
```

Spot-check before uploading (from a shell in the repo root):

```
python3 - <<'EOF'
import hashlib, pathlib
p = pathlib.Path("docs/downloads/h34-scatter-q50-arr-matched-20261004T223317Z.tif")
print(hashlib.sha256(p.read_bytes()).hexdigest())
EOF
```

must print `acf00361263a14c29fc6292bce2f10f862ec3ac258e1cd123a8a17c37bd5d203`.

## Read this before you spend the slot

**This file is not predicted to beat 0.2778.** The model that selected it
(`docs/data/leaderboard-regression.json`; ridge on 42 live leaderboard scores,
leave-one-out R² 0.885, RMSE 0.0275, Spearman 0.939) scores this design at
**0.2346** — and it also scores the 0.2778 artifact itself at 0.2345. The design
reproduces a known-good family; it does not exceed it.

What it *is* is the first candidate in this repository selected by an instrument
that measures the actual objective, rather than by one that has been measured to
point the wrong way. See [Findings](findings.html).

## What the file is

* **37,654 positive pixels, every one isolated.** 37,654 pixels form 37,654
  connected components; the largest component is 1 pixel. Every artifact that has
  ever scored above 0.24 in this family has `mean_component_px` exactly 1.0, and
  contiguous ribbons collapse (the 0.0020 artifact averages 60.2 px per
  component).
* **Zero pixels on the known-fault catalogue.** The organizers mask known
  USGS/INGENIOUS faults out of the penalty terms, so catalogue mass is
  metrically inert — it cannot help and cannot hurt. Earlier candidates in this
  repo carried a 60,988-pixel catalogue carpet; that mass is exactly what let
  three different files score an identical 0.1563 (below).
* **Arrangement matched to the 0.2778 artifact.** Distance-to-catalogue profile
  (5.77 % within 300 m, 50.8 % within 2 km) and 10 km block spread (0.9348 vs its
  0.9383) are reproduced deliberately, so the model is interpolating inside the
  region it was fitted on rather than extrapolating.
* **Habitat bias is mild, because the winner's was.** Pixels are drawn uniformly
  from the top half of a 21-band habitat weighted by the winner's own measured
  percentile lifts. The winner's dots sit at mean percentile 0.639 on
  `lid_upface_max` with 13.2 % in the top decile against 9.8 % for random — it
  was a mildly-biased scatter, not a detector. Selecting the *top* of the habitat
  instead drove `pr_tmi_vg` 11–18 standard deviations outside the training range
  and the model returned 51.16 for a metric bounded by 1.
* **Values are 1.0 on the payload, 0.0 elsewhere inside the footprint, NaN
  outside it.** The NaN mask is identical to `sample_submission.tif`
  (7,111,787 pixels), so the file cannot trip the "Predicted values must be in
  range [0, 1]" validation. All nine format checks pass.

## Why the file is new, and how that is checked

Whole-file comparison cannot prove novelty, because catalogue mass is metrically
inert — two files can differ by tens of thousands of pixels and be identical
under the metric. The gate therefore compares the **payload**, restricted to the
region evaluation can see, and reports three numbers separately: raw surface
correlation, final pixel agreement, and payload agreement.

Against **302 historical rasters** the closest match shares **4.07 %** of this
candidate's payload (Dice), against thresholds of 0.95. Verdict: **ALLOWED**.

## The finding the brief asked for

The three artifacts that all scored 0.1563 are not three hypotheses.

| comparison | raw correlation | final Dice | **payload Dice** | added px | % on masked faults |
|---|---|---|---|---|---|
| 5GEMSDOE vs GEMSDOE24 `ens12-adopted` | 1.0000 | 1.0000 | **1.0000** | 0 | — |
| 8GEMSDOE `Hedge-v2` | 0.8700 | 0.8638 | **1.0000** | 54,533 | **100.00 %** |
| GEMSDOE2 `dual-family-union` (control) | 0.9701 | 0.9701 | 0.9725 | 10,668 | 11.6 % |

Two are the same file, byte for byte. The third is that file **plus 54,533
pixels, 100.00 % of which lie on the known-fault mask**, so under the organizers'
masking rule they cannot change any penalty term. The control added 10,668 pixels
of which only 11.6 % were on the mask, and its score *did* move (0.1560).

Note what this does to the gate's design: raw correlation alone would have waved
`Hedge-v2` through at 0.87. Only the payload number catches it.

## The instrument problem, which is the real finding

Every repository in this family validates against **held-out catalogue faults**.
Measured directly, that instrument is inverted: the 0.2778 artifact earns
**0.26×** the credit of a size-matched *random* sample against the catalogue,
while the 0.0020 artifact earns **6.7×**. The test set is by construction the set
of faults the catalogue missed, so scoring well against held-out catalogue faults
means pointing at the wrong ground. That is why carefully "validated" candidates
in this family scored 0.02–0.15 while catalogue-avoiding ones scored 0.25–0.28.

## One retraction

An earlier session concluded that the 0.2778 artifact "over-emits ~4×" and that
cutting its budget was the lever. Both halves are wrong. The correct marginal
rule, derived from the metric and verified against the official worked example
(TPw 3.00, FPw 1.89, FNw 2.00 → 0.6027 vs the stated 0.60), is *keep a dot iff
its credit exceeds 0.2 × TI* — a bar of **0.0556**, not 0.0476. The winner's
implied mean credit per dot is **0.105–0.121** across the whole plausible range of
hidden truth mass, i.e. about twice the bar. Its dots are worth keeping on
average, and the leaderboard model agrees: across the matched arrangement the
budget curve is flat (0.2336 at 18,000 → 0.2346 at 37,654).

The identity reduces to `TI = T / (0.2 n + 0.8 M)`. At fixed budget the only free
term is `T`, total credit, so the only real lever is covering more distinct
hidden fault pixels — not emitting fewer or more dots.

## Limits, stated plainly

* Every score in this repository is a **user-reported claim**. No organizer
  receipt exists for any of them, so the regression that selected this file is
  fitted to claims.
* The regression has 42 rows and 34 descriptors. LOO R² 0.885 is good for that
  shape of problem, not proof; its RMSE of 0.0275 is larger than most of the
  differences this repository has ever argued about.
* No instrument here can measure whether a prediction finds a fault absent from
  *every* published catalogue. The hidden test set is not in this workspace.
* The projected score is a within-family estimate. The top of the leaderboard
  (0.3262) is ~0.05 above this family's ceiling, and nothing measured here
  explains that gap.
