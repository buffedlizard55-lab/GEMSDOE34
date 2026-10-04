# Geology, the target population, and the resulting strategy

Only statements traceable to the sources in `01_official_sources.md` are
asserted here. Anything this project has *not* verified is marked.

## What the target actually is (verified from the problem description)

The competition is not "reproduce the USGS fault map". The organizers state that:

1. the mapping is incomplete and "may even contain some inaccurate data";
2. the test set is a set of faults **manually identified by fault experts that are
   not contained within the current public USGS database**;
3. the region is split into a public and a private test set;
4. the **Final Prize Round** re-scores the same submissions against a label set
   that experts expand *after reviewing every team's submission* — "Predictions
   that helped experts identify previously-unmapped faults can score higher here
   than in the Initial Prize Round."

Consequence: the metric and the prize structure both reward **real, precisely
located faults that are absent from the published catalogue**, not a
reproduction of the catalogue. The $250k final round explicitly rewards
predictions an expert panel can verify.

## The masking rule and the free carpet

Known USGS/INGENIOUS pixels are excluded from the penalty terms (see
`02_metric_and_masking.md`). Prediction mass there is free. This makes
"saturate the known-fault mask" a weakly dominant policy, and it explains why
several of this group's submissions scored the same to four decimal places
while differing by tens of thousands of pixels: their differences were inside
the inert region (measured; `docs/data/collapse-diagnosis.json`).

## What the provided layers can and cannot show

`training_features.tif` carries nineteen float32 bands. Per the problem
description they cover: surface conductivity and depth to conductive base;
detrended elevation and its slope; dilatation rate, shear strain rate and the
second invariant of the strain-rate tensor; isostatic gravity anomaly and its
slope; magnetics (RTP anomaly, TMI, vertical and horizontal slope of TMI,
top-of-crustal magnetic source depth); earthquake density.

What is **not** provided, and cannot be obtained from this sandbox:

* the 1 m DEM tiles (`1m_DEM_links.csv` is available, the tiles are not
  reachable — direct HTTPS from this workspace fails at TLS for every host
  except GitHub);
* any high-resolution imagery, LiDAR point cloud, or field mapping.

So every geomorphic criterion that a fault expert would use — scarps, triangular
facets, deflected drainages, spring lines — is unavailable here. What *is*
available is potential-field and strain-rate data, which respond to structure at
depth as well as at the surface.

## Strategy this implies

1. **Carpet the known-fault mask** — free, weakly dominant, and it makes the
   submission "predictions for all faults in the region" as the rules ask.
2. **Spend the charged budget on precisely located, line-like predictions** that
   an expert could confirm or reject from the published geophysics. Because the
   metric charges every predicted pixel `0.2 * (d/R)` and gives credit only
   within 300 m of a real fault, the payout of a prediction is dominated by
   whether it sits on a fault, not by how many pixels it covers.
3. **Never let the pipeline's "improvement" step saturate the inert region** —
   that is the mechanism that collapsed three submissions onto 0.1563.

## Honest limits of the evidence gathered here

* The instruments in this repository score candidate rules against *catalogue*
  geometry (held-out blocks and held-out runs). They can measure whether a rule
  recovers unseen fault geometry under the organizers' masking rule. They cannot
  measure whether a rule finds a fault that is absent from every catalogue,
  because no such population is available in this workspace.
* One external population that *would* help — additional USGS-mapped faults not
  in the competition labels — was tested for exactly this purpose and rejected:
  the Qfaults prior in the sibling repositories is itself a USGS catalogue, so a
  rule that reproduces it is reproducing known faults, not finding new ones.
  It is kept as a catalogue-gap sensitivity check, nothing more.
* Therefore the shipped payload is a *hedge*: a bounded set of precisely located
  sites from structural extrapolation and corroborated geophysical lineaments,
  priced with the break-even rule above, with its worst case stated rather than
  hidden.
