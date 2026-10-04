# Sources, with evidence class

Every row was read directly by this session (2026-10-04) unless marked *in-repo*.
Nothing on this site is inferred from a source that could not be fetched.

## Official competition material

| Source | Read | Evidence class |
| --- | --- | --- |
| Problem description (metric, submission format, prize structure) — https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ | 2026-10-04 | OFFICIAL page, fetched |
| Leaderboard — https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ | 2026-10-04 | OFFICIAL snapshot (dynamic; page 1 top-25) |
| Competition home / rules entry — https://www.drivendata.org/competitions/306/competition-doe-gems/ | 2026-10-04 | OFFICIAL page |
| NLR GEMS rules PDF — https://docs.nlr.gov/docs/fy26osti/96647.pdf | referenced by the competition; **not fetched this session** | NOT VERIFIED here |
| Reference solution (Dr. John Lipor, PSU) — https://github.com/drivendataorg/gems-prize-reference-solution | cloned 2026-10-04 | OFFICIAL, code read |

## Official forum rulings (DrivenData staff)

| Ruling | Quote | Link |
| --- | --- | --- |
| Known faults are masked from the penalty terms | "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not count towards penalty terms." / "Re-evaluation will also mask/exclude the existing USGS/INGENIOUS faults." / "for scoring purposes it should not matter whether these known faults are included with predictions or not." — chrisk-dd, 2026-09-16 | https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516 |
| What counts as a "new fault" | "'new fault' means 'any fault pixel not already captured by USGS/INGENIOUS' and can include newly mapped geometry of an existing fault system." — chrisk-dd, 2026-09-23 | https://community.drivendata.org/t/where-do-you-draw-the-line/11536 |
| Test-fault provenance withheld; Phase-2 set is built from Phase-1 submissions | "We're not sharing details about the data sources, fault types, or coverage behind the test faults beyond what's in the problem description." / "the largest prize pool (Phase 2) will use a test set that is updated by expert review of all Phase 1 submissions" — chrisk-dd, 2026-09-23 | https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527 |

## Hash-pinned competition rasters (measured from the bytes this session)

| File | SHA-256 | Note |
| --- | --- | --- |
| `training_features.tif` (a.k.a. `gems-geodawn-numerical-features.tif`) | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` | 418,912,844 B, 19 float32 bands, EPSG:32611, nodata `-3.4028234663852886e+38` |
| `labels.tif` (= `existing_faults.tif`) | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` | 60,988 positives / 5,106,385 zeros / 7,111,787 nodata |
| `sample_submission.tif` (= `example_submission.tif`) | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` | **contains the catalogue itself**, see irregularities |

The SHA-256 of `training_features.tif` matches the pin recorded inside the sibling repository's
`data/bridge/manifest.json` (in-repo), which in turn records the official data-tab and the Dropbox
mirrors it was transported through. The value is therefore *self-consistent across two independent
checkouts*; it is **not** an organizer-published checksum, because the data tab requires login.

## Official data products referenced (not fetched — no external HTTP egress in this sandbox)

| Product | Official landing page | Status |
| --- | --- | --- |
| USGS GeoDAWN airborne magnetic/radiometric surveys | https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and | not fetched; the competition's own derived bands were used instead |
| GeoDAWN study-area catalogue entry | https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7 | not fetched |
| INGENIOUS geothermal data compilation | https://gdr.openei.org/submissions/1391 | not fetched |
| USGS SGMC (Horton et al. 2017, DOI 10.5066/F7WH2N65; NV part Ludington et al. 2007, DOI 10.3133/ds1052; ScienceBase 5888bf4fe4b05ccb964bab9d; zips `mrdata.usgs.gov/geology/state/zip/NV.zip`, `CA.zip`) | https://www.sciencebase.gov/catalog/item/5888bf4fe4b05ccb964bab9d | *in-repo* record only; a sibling-built raster exists but its **rebuild-from-official is pending** and it is therefore not used for any claim here |
| USGS Quaternary Fault and Fold Database (Qfaults) | https://earthquake.usgs.gov/qfaults/ | **needed and not yet obtained** — named as the next validation asset |
| NBMG Quaternary-fault mapping (Nevada Bureau of Mines and Geology) | https://nbmg.unr.edu/ | named in a sibling knowledge file with an **unverified URL**; not cited as confirmed |
| USGS 3DEP 1 m DEM (list supplied by the competition as `1m_DEM_links.csv` / `Digital-elevation-model-links-JSON.pdf`) | https://prd-tnm.s3.amazonaws.com/ | list is available in-repo (716 unique tiles confirmed against the S3 listing); tiles **not downloadable here** |

## Sandbox access reality (checked this session)

* `git`/`gh` over HTTPS to `github.com` — **works** (repositories cloned successfully).
* `fetch_page` to readcompetition/forum HTML — **works**.
* Direct `curl`/`wget` to any host (`dropbox.com`, `sciencebase.gov`, `prd-tnm.s3.amazonaws.com`,
  `drivendata-public-assets.s3.amazonaws.com`) — **fails at TLS** (exit before handshake).
  No external raster can be downloaded in this environment; every external-dependency claim below is
  therefore marked as obtainable-or-not rather than assumed.
