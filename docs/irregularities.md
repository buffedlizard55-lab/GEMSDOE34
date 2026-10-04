# Irregularities flagged for review

Each item is a measured contradiction between what a source states and what the bytes show.
None is corrected in place; each is reported.

## IR-34-01 — the official sample submission is not "total fault absence"

The problem description says: *"A sample submission that predicts total fault absence is provided
for your reference on the data download page."*

**Measured** (`tests/test_raster.py::test_sample_submission_is_the_catalogue_not_an_empty_raster`
fails if this ever changes): `sample_submission.tif` is float32, nodata = nan, and contains
**60,988 cells with value 1.0** — at exactly the positive cells of `labels.tif`. The two files'
value patterns are equal on the common footprint and the support-mask hash is identical
(`d8b86f12ef449735…`). The provided "sample" is therefore the rasterised existing-fault catalogue,
not an empty raster.

**Why it matters.** The file doubles as the format template *and* as a ready-made prediction of
the known faults. A participant who trusts the prose and assumes a zeros template will
misunderstand the format; a participant who submits the template unchanged submits the catalogue.
Note that this is also the file that defines the expected nodata convention (NaN outside the valid
footprint), which every accepted artifact in this group's history follows.

## IR-34-02 — the portal error `"Predicted values must be in range [0, 1]"`

Two distinct mechanisms can produce it:

1. The float32 sentinel `-3.4028234663852886e+38` used as nodata in `training_features.tif`
   (7,113,308 cells). Writing those through unchanged puts values far outside [0, 1].
2. A validator that runs a naive range check over the whole array: `NaN >= 0` is False, so a
   raster whose nodata cells are NaN fails *if* the check is written as
   `(a >= 0).all() and (a <= 1).all()` rather than masked.

The shipped file cannot trip (1) — every finite value is in [0, 1]. It uses the NaN convention
because that is what the organizers' own sample uses and what every previously accepted artifact
in this group's history carries (`gemsdoe1-ens12-7f00890a.tif`,
`gemsdoe2-dual-family-union-f68e590f.tif`, `gemsdoe31-h27-4-solo-d28-…-nan.tif`: all `nodata=nan`,
all exactly 7,111,787 NaN cells). If (2) is nevertheless the real cause, rebuild with
`scripts/build_submission.py --outside zero`-equivalent behaviour (`raster.write_submission(...,
outside="zero")`), which produces an all-finite raster with the same positives.

## IR-34-03 — the three-way 0.1563 tie is not three hypotheses

Reported as three independent submissions. Measured: two are the same file
(`sha256 7f00890a…`, Dice 1.0), and the third is that file plus 54,533 pixels of which
**100.00 %** lie on the known-fault mask. Because free-mask mass is metrically inert, the two
files are the same submission under evaluation. The control: another artifact of the same family
added 10,668 pixels of which only 11.6 % were on the mask, and its claimed score did move
(0.1563 → 0.1560). See `docs/data/collapse-diagnosis.json`.

## IR-34-04 — the claimed 0.2778 artifact's own `.zip` is 0 bytes

`docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.zip` in the sibling
repository is an empty archive (0 bytes; its single entry is itself, 0 bytes long). The only copy
of the file behind the group's best claimed score is the bare `.tif`. There is no submission
receipt, submission id, or hash-to-score crosswalk for any artifact this group has submitted, so
every score in this repository is labelled **claim** or **dated snapshot**, never *verified*.

## IR-34-05 — attributions in the sibling ledgers conflict

The same artifact is described as 0.2778 in the group's brief and as *"unscored / not
slot-approved"* on its owner page; the 0.2708 row is attributed to `gemsdoe31-h27-4-solo-d28`
without a receipt. Where two sources disagree, this repository reports the disagreement instead
of picking one.

## IR-34-06 — the target moved during the competition

The brief quotes 0.3195 as the score to beat. The leaderboard read on 2026-10-04 shows
0.3262 / 0.3222 / 0.3195 for the top three. Any target derived from a dynamic board is a dated
snapshot; this repository stamps every value with its read time.

## IR-34-07 — a sibling knowledge file cites an unverified URL

`sibling knowledge/06_slot_strategy_2026-09-26.md` names NBMG Quaternary-fault mapping as the next
proxy source and gives a URL its own author did not check. It is recorded here as
*named-but-unverified*, and no claim in this repository depends on it.
