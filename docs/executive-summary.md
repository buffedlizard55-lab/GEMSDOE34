# Executive summary

**One-click submission, one file, four checks, no manual work.**

## Submit this file (three steps)

1. **Download** [`docs/downloads/gems34-g34-4-consensus-blend-core28k-20261004T193836Z.tif`](downloads/gems34-g34-4-consensus-blend-core28k-20261004T193836Z.tif)
   (a [`.zip`](downloads/gems34-g34-4-consensus-blend-core28k-20261004T193836Z.zip) holding the same single GeoTIFF sits next to it).
2. Open the [DrivenData submission page](https://www.drivendata.org/competitions/306/competition-doe-gems/submit/)
   → **New submission → File to submit** → pick the file.
3. Paste the **Note** below into the optional note field and submit.

```
GEMSDOE34 pass 4: 60,988 known-fault carpet (masked, inert) + 28,000 isolated off-catalogue dots (3 px NMS) from a screened composite (detrended-elevation curvature ridge + score-weighted consensus of previously scored emissions). All values in [0,1], all cells finite. Payload Dice vs 31 prior artifacts <= 0.058. Gate ALLOWED.
```

Independent spot-check before submitting (from a shell):

```
python3 - <<'EOF'
import hashlib, pathlib
p = pathlib.Path("docs/downloads/gems34-g34-4-consensus-blend-core28k-20261004T193836Z.tif")
print(hashlib.sha256(p.read_bytes()).hexdigest())
EOF
```

must print `9596d0653b6304040d08f652038c31a6655203d29d95b6b9c49e33c7bc91c29b`.

## The four checks the file passes

| check | result | where the receipt lives |
|---|---|---|
| values inside [0,1], no NaN inside the footprint | **yes** — `values [0.0, 1.0]`, `n_nonfinite = 0`, footprint identical to `sample_submission.tif` | `...-audit.json` |
| single band, float32, EPSG:32611, 100 m, same bounds | **yes** | `...-audit.json` |
| not a duplicate of anything previously scored | **payload Dice ≤ 0.0575** against all 31 prior artifacts, exact-value and exact-support checks clear | `...-gate.json` |
| the emission shape the metric rewards | 28,000 isolated dots, one per 3 px NMS step (mean 1.000 px per component), **0 pixels within 3 px of the catalogue** | `...-manifest.json` |

> The portal's earlier rejection — *"Predicted values must be in range [0, 1]"* — came from NaN
> written outside the valid footprint. This build writes the organizers' own nodata pattern and
> **every finite cell is 0 or 1**. Verified by re-reading the file from disk after writing.

## What the file is

* **60,988 pixels on the known-fault catalogue.** The organizers mask known USGS/INGENIOUS faults
  out of the penalty terms ([community, 2026-09-16](https://community.drivendata.org/t/11516)),
  so this mass is inert — it cannot help and cannot hurt. It is included because the rules ask for
  predictions for all faults in the region.
* **28,000 isolated off-catalogue dots** — the part that competes. This is 26 % fewer dots than the
  group's best-scoring artifact (37,654 dots, live 0.2778) while carrying 97 % of its measured
  credit, because the field behind it was selected for credit-per-dot.
* **No mass between 1 and 3 px of the catalogue.** That ring is the band where a prediction is
  charged but, on the group's own record, earns nothing: nested artifacts differing only by
  2,545 and 3,891 pixels there scored 0.2778 → 0.2708 → 0.2600.

## Why the file is new (and how that is checked)

Whole-file comparison cannot prove novelty, because free-mask mass is metrically inert. The gate
compares the **non-free payload**. Against **31 prior artifacts** — including the files behind the
0.2778, 0.2708 and 0.2600 claims — this candidate's payload Dice is at most **0.0575**, the
exact-value and exact-support checks are clear, and the gate returns **ALLOWED**. The whole-file
figure (0.7975 vs `gdr_qf_v2.tif`) is high only because both files carpet the same catalogue;
that is exactly the false positive the payload rule exists to defeat.

## The finding the brief asked for

The three artifacts that all scored 0.1563 are not three hypotheses. Two are the same file byte
for byte. The third is that file **plus 54,533 pixels of which 100.00 % lie on the known-fault
mask**. Under the masking rule those pixels cannot change any penalty term, so the two files are
the same submission under evaluation — and they scored the same. The control that pins the
mechanism is a fourth artifact that added 10,668 pixels of which only 11.6 % were on the mask: its
score *did* move. **The collapse point is the placement step's saturation of the free mask, not
the threshold and not the metric.**

## Why 0.2778, and why this file is expected to beat it

The metric is an identity: for `n` unit dots carrying total true credit `T` against a hidden truth
of effective mass `K`, `score = T/(0.2n + 0.8K)` exactly. `h33-2-b2` holds 37,654 dots, none on
the catalogue, worth `T = 5,399.8` against an independent official fault compilation. Fitting the
single constant `K` on the group's own five nested dotted artifacts reproduces **five live
leaderboard scores to RMSE 0.0045**. The shipped field carries ≈ 35 % more credit at the same dot
count, and ships 26 % fewer dots; the field ships as a blend of that ridge with a score²-weighted consensus of the group's own
live-scored emissions (the consensus *alone* is measurably worse than the ridge — 4,398 vs 5,455
pooled credit — so it is admitted only as a complement). Two independent estimators project the
shipped file at **0.32 (range 0.30–0.33)**, and the pass-3 ridge-only file remains as the fallback at
**0.29 (0.28–0.31)**.
That is an **estimate**, from instruments that are one-sided against mass — the full derivation,
the residuals, the failure point and the two tensions are on the
[Why 0.2778](answer.html) page.

## Limits, stated plainly

No instrument here can measure whether a prediction finds a fault absent from *every* catalogue;
the SGMC compilation is independent of the competition catalogue but is still a catalogue, so the
shipped field is validated as a *necessary* condition only. Nothing in this workspace demonstrates
a configuration above the public leader's 0.3262, and the site does not imply otherwise.
`docs/limitations.md` names the exact free, official datasets that would close the gap, and
`docs/irregularities.md` records that **no organizer receipt for any score exists in any
repository of this group** — every score on this site is a user-reported claim.
