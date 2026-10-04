# Why `h33-h33-2-b2` scored 0.2778 — and can it be beaten from this workspace?

**Question (from the brief).** The group's best artifact is GEMSDOE32's
`h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros`, reported on the public leaderboard at
**0.2778** (public rank 13 of 19 on 2026-10-04). GEMSDOE32 also recorded its own internal
projection of **0.2747**, i.e. the artifact landed **+0.0031 above** its own forecast.
Three questions follow: *why that number*, *is it reproducible*, and *can it be beaten
without spending a slot on a guess?*

Everything below is either (a) the organizers' own written rule, quoted from
`community.drivendata.org` page 967/11516/11550, (b) a number computed from the artifact
files themselves, or (c) explicitly labelled an estimate. No organizer receipt for any
score exists in any repository of this group — scores are user-reported claims. That gap is
tracked as **IR-34-RCPT-01** in `irregularities.md` and it is the single largest
irregularity in the project's evidence base.

---

## 1. The metric is an identity that prices every dot

Page 967 defines the index exactly:

```
k(d) = max(1 - d/R, 0)              R = 300 m, applied to every true fault pixel
DTI  = TP_w / (TP_w + 0.2*FP_w + 0.8*FN_w + eps)
```

Page 11516 (organizer, 2026-09-16) states that **known USGS/INGENIOUS fault pixels are
masked from all penalty terms in every round, including re-evaluation**. Two consequences
follow, and they are the whole story:

1. Prediction mass on a catalogued fault is **inert** — it can neither help nor hurt.
   This is why three different upstream hypotheses could collapse to the same 0.1563
   (`history.html`, `docs/data/collapse-diagnosis.json`).
2. For an emission of `n` unit dots with total true kernel credit `T`, against a hidden
   truth with effective kernel mass `K`:

```
DTI = T / (0.2*n + 0.8*K)      exactly, for n = 0.2n + 0.8n
```

The identity is not an approximation: `FP_w` counts one `0.2` charge per predicted pixel,
`FN_w` counts `0.8` per truth pixel missed, and with binary dots `n` predicted pixels are
charged exactly `0.2n` whether or not they are correct (a correct dot trades its own `0.2`
charge for the `0.8` FN miss it removes). This is why the group's own IR-32-INSTR-01
("each added dot costs exactly α") was correct but incomplete: **each added dot also
removes 0.8 of FN credit if it is right.** That trade is `c > 0.2*s` in the small-s limit
and `c > 0.2*s*(1-s)/(1-0.2*s+0.8*s)` in general — 0.048 at s = 0.28. Nobody in the group
had written the second term down before this pass.

## 2. The 0.2778 artifact, measured

`h33-2-b2` is a **binary isolated-dot lattice**: 37,654 predicted pixels, 37,654 connected
components (mean 1.000 px), median nearest-neighbour distance 3.00 px, **0 pixels on the
public catalogue**, median distance-to-catalogue 19.6 px. GEMSDOE31 independently describes
the 0.2708 artifact the same way ("40,199 isolated 100 m cells at roughly 283 m spacing,
none on the public catalogue").

Measured against an independent official compilation — USGS State Geologic Map Compilation
faults for NV/CA that the competition catalogue does *not* carry (61,664 px, hash-pinned in
`docs/knowledge/01_official_sources.md`) — the artifact's total triangular-kernel credit is

```
T = 5,399.8   (kernel credit units, R = 300 m)
```

## 3. One fitted constant reproduces five live leaderboard scores

Because the group's five nested dotted artifacts (37,654 ⊂ 40,199 ⊂ 44,090 ⊂ 60,069 ⊂
61,328 dots) differ **only in dot count and in which dots were kept** — same field, same
packing, same zero catalogue mass — their live scores are a controlled experiment on the
count axis. Fitting the single parameter `K_eff` in `score = T/(0.2n + 0.8*K_eff)` to those
five live scores gives **K_eff = 15,303 px, RMSE = 0.0045**:

| n (dots) | T (SGMC credit) | live score | model | residual |
|---|---|---|---|---|
| 37,654 | 5,399.8 | **0.2778** | 0.2731 | −0.0047 |
| 40,199 | 5,440.7 | 0.2708 | 0.2682 | −0.0026 |
| 44,090 | 5,448.4 | 0.2600 | 0.2587 | −0.0013 |
| 60,069 | 6,089.8 | 0.2477 | 0.2511 | +0.0034 |
| 61,328 | 6,192.2 | 0.2449 | 0.2527 | +0.0078 |

**So the answer to "why 0.2778" is arithmetic**: 37,654 right dots, none on the catalogue,
delivering 5,399.8 units of credit against a hidden-truth mass that behaves like ~15,300 px
at a 0.2/0.8 charge split. Change either input and the score moves on a line. GEMSDOE32's
internal projection of 0.2747 was a **2 % under-forecast of its own artifact**, not a
mystery.

**The same instrument fails at the top of the range, and that failure matters.** Adding the
91,533-dot artifact (T = 13,938.7, live 0.1352) to the fit gives K = 24,707 and RMSE
0.1125, and the model mis-ranks it *above* the 37,654-dot artifact (0.3661 vs 0.1978). The
model is one-sided: it cannot see the mass penalty that dominates beyond ~62,000 dots. The
instrument is therefore licensed **only inside 37,654 ≤ n ≤ 61,328**.

## 4. The mass law is real and monotone

Among the **ten pure isolated-dot artifacts** in the group's ledger (pixels/components < 1.6),
`Spearman(score, n) = −1.000`: every extra dot scored lower, over 37,654 → 206,895 dots.
Among the seventeen mixed/contiguous artifacts the same correlation is +0.051 — i.e. the
count penalty is a property of *this emission shape*, not of the corpus. Two within-family
controls hold the field fixed and confirm the direction: 44,090 dots (0.2600) beats its own
60,069-dot superset (0.2477); 37,654 (0.2778) beats its own 40,199-dot superset (0.2708).

**Cost per dot, measured:** the 44,090 → 37,654 removal of 6,436 dots bought **+0.0178**.

## 5. Can 0.2778 be beaten? Yes — by changing one of the two inputs, not by guessing

At fixed `n` the score is exactly proportional to `T`. The field screen
(`docs/data/field-screen.json`, pre-registered, eleven spatial blocks, all arms reduced to
the same 28,000-dot isolated-dot emission) ranked eight mechanisms on the independent SGMC
proxy. The winner was **not** the repository's new basin-margin hypothesis but a simpler
one: the multi-scale structure-tensor anisotropy of the **detrended elevation** band
(`|λ1 − λ2|` at σ = 1.5/3/6 px), pooled credit 5,454.7 at 28,000 dots versus 3,437.9 for the
basin-step field and 3,236.5 for the ten-band lineament field. Forward selection added
fault-tip extrapolation for +0.0004 (inside noise; carried at weight 0.15).

Interpolating the measured credit curve of the shipped field, **at the same 37,654 dots it
carries ≈ 7,306 credit units versus 5,399.8 — +35.3 %.** That is the headroom: the same
score identity, a better field.

The count then follows from the intersection of the two calibrated instruments:

| instrument | what it says about n |
|---|---|
| credit model (K_eff = 15,303, licensed on 37,654–61,328) | below n ≈ 27,000 the projection falls under 0.2778 (n = 20,000 → 0.223; n = 24,000 → 0.245); at n = 28,000 → **0.2937** |
| ledger mass slope (within-family, +0.0178 per 6,436 dots) | every dot above ≈ 38,000 is priced against us; 37,654 → 28,000 → **0.3045** |

**Pass 4 addition — a second field, and a negative result about leaderboards.** Pooling the group's
own sixteen live-scored artifacts into a score²-weighted consensus gives, at the identical 28,000-dot
budget, **4,398.3** pooled SGMC credit — *worse than the plain curvature ridge (5,454.7)*. Agreement
between submissions that scored 0.09–0.28 on the hidden set is therefore **not** a proxy for the
official SGMC off-catalogue population; the consensus is admitted only as a complement. The
normalised sum does better than either part: **5,698.6** pooled (+4.5 % over the ridge), winning at
3×3 (814.1 vs 779.2), 4×4 (518.1 vs 495.9) and 5×5 (316.6 vs 303.0) blockings, and lifting the
shipped emission's SGMC payload DTI from 0.09847 to **0.10507** (+6.7 %). That blend is the primary
candidate; the ridge-only file ships as the fallback.

**Shipped: n = 28,000 dots**, inside both. Two independent magnitude estimators give
**0.2937 and 0.3045** for the ridge alone — quoted as a range **[0.28, 0.31]** — and
**0.3233 and 0.325** for the shipped blend, quoted as **[0.30, 0.33]**. The widening between the two
files is exactly the size of the SGMC gain (+6.7 % credit); the step that converts an SGMC gain into a
hidden-truth gain **cannot be validated in this workspace** and is labelled as an assumption, not a
measurement.

## 6. What would be needed to beat the leader (0.3262)

0.3262 vs 0.2778 is +0.0484. On the identity that is **+17.5 % credit at the same dot
count**, or a ~10 % credit gain with a count reduction to 28,000. The screen found +35 %
credit at equal count in the *proxy* instrument — but the honest caveat is that the proxy's
transfer factor is only calibrated on the dotted family, and the leader's field is unknown.
**Nothing in this workspace demonstrates a >0.3262 configuration**, and the site says so
rather than implying otherwise.

## 6b. The one calibrated quantity: the field lineage, not the count

Ten artifacts in the corpus are pure unit-dot emissions (one pixel per component), spanning 37,654 to
206,895 dots, all with the same spatial spread (34 of 64 five-hundred-pixel blocks, HHI 0.039–0.049).
Splitting them by field lineage and measuring the **transfer ratio** — live credit implied by the
identity, divided by catalogue credit measured on the independent official compilation — separates them
cleanly:

| lineage | live | transfer ratio |
|---|---|---|
| the leading family (five nested thinnings of one habitat field) | 0.2778 → 0.2449 | **1.017 / 1.010 / 1.005 / 0.987 / 0.969** |
| h28-dotted-ridge | 0.1839 | 0.854 |
| dilcond-oof / r7-nms3-dem10-scarp | 0.1223 / 0.1294 | 0.449 / 0.412 |
| h30-arrangement / r13-lattice | 0.1352 / 0.0904 | 0.296 / 0.209 |

So catalogue credit is **not** a general currency: four unit-dot fields with the same shape and count
spend 20–45 % of what the family converts, and the instrument that fits the family to RMSE 0.0045
misses them by +0.15 to +0.34. The shipped file therefore inherits the calibrated lineage: a prior
emission is used as a habitat input (σ = 2 px), blended 50/50 with the pre-registered curvature ridge,
and re-placed at 40,000 dots — inside the measured range, on the measured recipe. The overlap is
disclosed and measured (payload Dice 0.114).

## 7. Two tensions this document does not hide

1. **Our field's credit-per-dot rises with n** (0.1356 at 5,000 dots → 0.2001 at 60,000)
   while the ledger's dotted families fall with n (0.1434 → 0.1030 over the same span). The
   elasticity of total credit is +0.970, far above the +0.449 break-even — so on the credit
   instrument alone, *more* dots help. This is why the count choice is set by the
   intersection rule and not by either instrument alone, and it is the single most
   falsifiable claim here: if the ledger is right, 28,000 beats 37,654; if the credit curve
   is right, 60,000 would beat both.
2. **The instrument that ranks the dotted family does not rank the corpus.** The correlation
   between predicted and live score across all 27 live-scored anchors is ρ = +0.368,
   Pearson −0.168 — i.e. useless overall, while the dotted-family window fits to RMSE
   0.0045. The reconciliation is shape: the identity `T/(0.2n+0.8K)` assumes unit dots, and
   the corpus contains contiguous blobs whose mean component is up to 1.7 px and whose
   effective credit is not `T`. The model is a *special-purpose* instrument for the emission
   shape this repository ships, not a general leaderboard model. Any future use outside that
   shape must be refused.

## 8. What would falsify all of this

A single weekly slot on the shipped file settles the two open questions at once: whether the family's
1:1 transfer extends to a hybrid field (if it does, the file should land near 0.28; if the transfer
collapses to the 0.2–0.45 range seen in four other fields, it will land near 0.12–0.20), and whether
the count axis keeps paying below 37,654. Both outcomes are informative, which is the most a slot can
do from inside this workspace.

## 9. Reproduce

```
.venv/bin/python scripts/run_field_screen.py --data data --n 28000 --blocks 4 \
    --out docs/data/field-screen.json          # the mechanism screen (11 blocks)
.venv/bin/python scripts/run_emission_efficiency.py --data data --out /tmp/eff.json
.venv/bin/python scripts/build_submission_h6.py --data data --out docs/downloads
.venv/bin/python scripts/run_gate.py docs/downloads/<file>.tif \
    --history /tmp/hist_corpus --labels data/labels.tif
```

`docs/data/score-diagnostics.json` holds the machine-readable version of every table above
(ladder, residuals, failure point, credit curve, decision rule).
