# Limitations and remaining work

## What blocks a higher score

**L1 — no novelty-sensitive truth population (the binding constraint).**
Both instruments in this repository score rules against *catalogue* geometry: the blocked holdout
(whole 4×4 blocks) and the near-field instrument (contiguous removed runs). They can measure
whether a rule recovers unseen fault geometry under the organizers' masking rule. They cannot
measure whether a rule finds a fault that is absent from every catalogue, because no such
population is available here. The consequence is sharp and measured: on the blocked holdout,
**every field tested lands within noise of the free carpet** (best 0.00289 vs carpet 0.00278 over
11 folds), so the far-field half of the shipped file is priced by the metric's algebra and capped,
not validated by an instrument.

*What would fix it.* An independent, expert-mapped fault population in the same region that is
**disjoint** from the competition catalogue. Named, free, official sources:

* **USGS Quaternary Fault and Fold Database (Qfaults)** — https://earthquake.usgs.gov/qfaults/
  Public domain. *Checkable but not reachable from this sandbox* (direct HTTPS fails at TLS for
  every host except GitHub). A sibling project built a 3-band raster from
  `https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip`
  (zip sha256 `447eadc5…`, product sha256 `538b4573…`) — but that is a *USGS catalogue*, so a rule
  that reproduces it reproduces known faults; it was tested for this purpose and rejected.
* **USGS SGMC** (Horton et al. 2017, DOI `10.5066/F7WH2N65`; NV part DOI `10.3133/ds1052`;
  ScienceBase `5888bf4fe4b05ccb964bab9d`; zips `mrdata.usgs.gov/geology/state/zip/NV.zip`,
  `CA.zip`). Their own provenance note says "rebuild-from-official pending", so nothing here
  depends on the sibling-built raster.

**L2 — no 1 m DEM in the sandbox.**
The competition supplies `1m_DEM_links.csv` (716 unique tiles, verified against the S3 listing)
but the tiles cannot be downloaded here. Every geomorphic criterion an expert would use —
scarps, facets, deflected drainages — is therefore unavailable, and every hypothesis that needs
it is **untested rather than rejected**. This is the largest unexplored evidence class.

**L3 — 2 CPU, ~4 GB RAM, no GPU.**
The organizers' own reference solution is a U-Net (5 epochs, Monte-Carlo dropout, patches of
128). It is out of reach here. Everything in this repository is deliberately CPU-only and runs
end-to-end in minutes.

**L4 — the masking wording admits two readings.**
"Masked/excluded from evaluation" can mean *not charged to FP_w* or *removed from evaluation
entirely*. Both readings make the free carpet non-harmful, and both make the collapse diagnosis
above valid; they differ on whether that mass can ever earn credit. Every decision here is safe
under both.

## What passes 3–4 changed, and what is still blocked

* **Closed:** the count question. `score = T/(0.2n + 0.8K)` is exact, calibrated on five live
  claims to RMSE 0.0045 inside 37,654–61,328 dots, and the shipped count (28,000) sits at the
  intersection of that instrument and the ledger's measured mass slope. The field question is also
  closed as far as this workspace can close it: eight mechanisms were screened on eleven blocked
  folds with the emission shape held fixed, and the winner was not the hypothesis this repository
  was built around.
* **Still blocked, unchanged:** there is no *novelty-sensitive* truth here. SGMC is an independent
  official compilation, but it is still a catalogue; every arm is validated as a necessary
  condition only. The 1 m DEM, the 1:24,000 geologic maps and the geothermal well records remain
  unreachable from the sandbox and are named with links in `docs/data/hypotheses.json`.
* **Pass 4, measured:** the score²-weighted consensus of the group's own sixteen live-scored
  artifacts is a *worse* SGMC proxy than the curvature ridge (4,398.3 vs 5,454.7 pooled credit), so
  leaderboard agreement is not truth; the normalised sum of the two is better than either
  (5,698.6, winning at all three blockings). The shipped primary is that blend; the ridge alone
  remains as the fallback. Both files are gated, both carry projections, and neither projection is a
  receipt.
* **Measured negative results, not to be re-tried:** the power-law credit fit (underdetermined,
  c1 at its bound); the leaderboard inversion (LOO correlation −0.381); catalogue distance as a
  ranking feature (identical histograms across top/middle/bottom groups); and H6, the
  basin-margin-step field, which lost to the curvature ridge by 37 % on the pre-registered screen.

## Open questions, and the experiment that settles each

| # | Question | Experiment |
| --- | --- | --- |
| Q1 | Does the far-field payload earn anything on the real test set? | spend one slot on the shipped file, read the public score, compare with the group's 0.2778 claim |
| Q2 | Is the group's 0.2778 attributable to `gemsdoe32-h33-h33-2-b2-…-zeros.tif`? | obtain one submission receipt or submission id — none exists in any sibling repository, and that file's own `.zip` is 0 bytes |
| Q3 | Would a payload restricted to ≥ 800 m from the catalogue beat 0.2778? | the shipped payload's median is 9 px; the three best claimed artifacts sit at medians of 16.8–19.6 px. Rebuild with `--min-dcat 8` and compare on the real board — no local instrument can rank this |
| Q4 | Does the 1 m DEM carry the signal? | download a handful of tiles off-sandbox and test the scarp-curvature hypothesis |

## Suggested next steps, in order

1. Obtain Qfaults or SGMC out-of-band, build a novelty-sensitive truth population (faults ≥ 300 m
   from the competition catalogue), and re-run `scripts/run_hypotheses.py` against it.
2. Re-run the same script with `--free-mode dilate3` and compare the ranking: if it flips, L4 is
   the constraint to resolve first.
3. Download 3DEP 1 m DEM tiles over the highest-ranked structural targets and test the
   scarp-curvature hypothesis — the only major evidence class still untested.
4. Spend a slot only on a candidate that clears `scripts/run_gate.py` and beats the current best
   on at least one instrument, and record the outcome in `registry/history.json` with its
   evidence class.
