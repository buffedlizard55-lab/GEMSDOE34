# Official sources — read this before adding any claim to this repository

Every line below was read by this project directly (fetch, `git`, or a hash
verification) on the date shown. Nothing here is quoted from a secondary blog
post, a model's memory, or another participant's summary. Where a source could
**not** be reached from this sandbox, it is marked `NOT FETCHED` and no claim
depends on it.

## 1. The competition

| What | Where | Evidence class |
| --- | --- | --- |
| Problem description (task, structure, datasets, metric, format, worked example) | https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ | OFFICIAL, fetched 2026-10-04 (both chunks) |
| Competition home / rules entry | https://www.drivendata.org/competitions/306/competition-doe-gems/ | OFFICIAL, fetched 2026-10-04 |
| Public leaderboard | https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ | OFFICIAL snapshot, read 2026-10-04 (rank 1 = 0.3262) |
| Organizers' reference solution | https://github.com/drivendataorg/gems-prize-reference-solution | OFFICIAL code, cloned + read 2026-10-04 |
| NLR/DOE rules PDF | https://docs.nlr.gov/docs/fy26osti/96647.pdf | named by the competition; **NOT FETCHED** |
| GeoDAWN survey data (USGS) | https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and | official product page; **NOT FETCHED** |
| GeoDAWN study-area catalogue entry | https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7 | official; **NOT FETCHED** |
| INGENIOUS project (Great Basin Center for Geothermal Energy) | https://gbcge.org/current-projects/ingenious/ | official; **NOT FETCHED** |
| USGS Quaternary Fault and Fold Database (Qfaults) | https://earthquake.usgs.gov/qfaults/ | official; **NOT FETCHED here** (a sibling project fetched `Qfaults_GIS.zip`, recorded below) |
| USGS State Geologic Map Compilation (SGMC), Horton et al. 2017 | https://www.sciencebase.gov/catalog/item/5888bf4fe4b05ccb964bab9d · DOI 10.5066/F7WH2N65 · NV part DOI 10.3133/ds1052 | official identifiers recorded from a sibling manifest; **staging page NOT FETCHED** |

### Verbatim statements from the problem description that drive the design

* "we have consulted with fault experts who have **manually identified faults that
  are not contained within the current public USGS database**. These new faults
  will comprise the test dataset for the initial prize round."
* "The GeoDAWN region is chunked and split into a public test set and a private
  test set."
* Final round: "An **expanded** label set — Initial Prize Round labels **plus**
  previously-unknown faults that experts verify after reviewing *every team's*
  submission … Predictions that helped experts identify previously-unmapped
  faults can score higher here than in the Initial Prize Round."
* "The labels for this challenge come from the USGS quaternary fault maps and
  from INGENIOUS."
* Provided features: `training_features.tif`, EPSG:32611, 100 m, with layers —
  surface conductivity and depth to conductive base surface; detrended elevation
  and its slope; dilatation rate, shear strain rate, second invariant of the
  strain-rate tensor; isostatic gravity anomaly and its slope; magnetics
  (RTP anomaly, TMI, vertical and horizontal slope of TMI, top-of-crustal
  magnetic source depth); earthquake density.
* "A sample submission that predicts **total fault absence** is provided for your
  reference" — see `docs/irregularities.md` IR-34-01: the shipped file does
  **not** do that; it contains 60,988 ones at the label cells.

## 2. Organizer rulings on the forum (quoted)

| Topic | Quote | Link | Read |
| --- | --- | --- | --- |
| Known faults are masked from the penalty terms | "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not count towards penalty terms." · "Re-evaluation will also mask/exclude the existing USGS/INGENIOUS faults." · "for scoring purposes it should not matter whether these known faults are included with predictions or not." — chrisk-dd | https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516 | 2026-10-04 |
| What counts as a "new fault" | "'new fault' means 'any fault pixel not already captured by USGS/INGENIOUS' and can include newly mapped geometry of an existing fault system." — chrisk-dd | https://community.drivendata.org/t/where-do-you-draw-the-line/11536 | 2026-10-04 |
| Test-fault provenance | "We're not sharing details about the data sources, fault types, or coverage behind the test faults beyond what's in the problem description." — chrisk-dd | https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527 | 2026-10-04 |

## 3. The competition rasters, verified by hash

Measured in this workspace on 2026-10-04 by re-reading the bytes; the SHA-256 of
`training_features.tif` additionally matches the pin recorded in the sibling
bridge manifest, so the file is self-consistent across two independent
checkouts (it is **not** checked against an organizer-published checksum,
because the data tab requires a login).

| File | SHA-256 | Geometry / values |
| --- | --- | --- |
| `training_features.tif` | `4371c82e…` (full hash in `docs/data/collapse-diagnosis.json`) | 19 bands, float32, EPSG:32611, 100 m, 3292x3730, nodata −3.4028234663852886e+38 in 7,113,308 cells |
| `labels.tif` (= `existing_faults.tif`) | `7ba308cc…` | int8, nodata −1 in 7,111,787 cells; 5,106,385 zeros; **60,988 ones** |
| `sample_submission.tif` (= `example_submission.tif`) | `2176d08e…` | float32, nodata nan in 7,111,787 cells; 5,106,385 zeros; **60,988 ones — at exactly the label cells** |

## 4. Third-party material actually relied on

| Item | Provenance recorded | Used for |
| --- | --- | --- |
| `Qfaults_GIS.zip` → 3-band uint8 prior on the competition grid | source URL https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip, zip sha256 `447eadc5…`, product sha256 `538b4573…`, feature count and observed attribute list recorded in the sibling manifest | **catalogue-gap sensitivity only** — it is a USGS catalogue, so a model that reproduces it is reproducing known faults, not finding new ones |
| `smp.Unet` / `segmentation_models_pytorch` (reference solution) | read from the organizers' notebook | understanding the organizers' own baseline; not runnable here (no GPU) |

