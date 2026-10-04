# The metric, the masking rule, and what they imply for an emission

## The equations (verbatim from the problem description)

    k(d)  = max(1 - d/R, 0)                      triangular kernel, R = 300 m (= 3 px)
    TP_w  = sum_{g in G} max_{x: d(x,g)<=R} p(x) * k(d(x,g))
    FP_w  = sum_{x: p(x)>0} p(x) * [1 - max_{g in G} k(d(x,g))]
    FN_w  = sum_{g in G} [1 - max_{x: d(x,g)<=R} p(x) * k(d(x,g))]
    DTI   = TP_w / (TP_w + 0.2*FP_w + 0.8*FN_w + eps)

Published worked example: `TP_w = 3.00, FP_w = 1.89, FN_w = 2.00`,
`TI_w(0.2, 0.8) = 3.00 / (3.00 + 0.2*1.89 + 0.8*2.00) = 0.60`.

Three structural consequences that are not obvious from the formulas but follow
immediately once they are read carefully:

1. **FN_w is the complement of TP_w.** Both sums are taken over the *same*
   truth pixels and the *same* inner maximum, so `TP_w + FN_w = |G|` exactly.
   The metric becomes `DTI = T / (0.2*(T+F) + 0.8*K)` with `K = |G|`.
2. **FP_w is distance-weighted, not binary.** A prediction pixel *d* metres from
   the nearest truth pixel is charged `0.2 * (d/R)` — a prediction inside 300 m
   of a truth fault is charged proportionally, not fully.
3. **One prediction pixel can serve many truth pixels**, and one truth pixel is
   served by its single best prediction within 300 m. Coverage is therefore a
   *max*, not a sum: packing predictions closer than 300 m buys less than it
   looks like it should.

## The masking rule

> "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded
> from evaluation, so they do not count towards penalty terms." — chrisk-dd

Operationally: prediction mass on a known-fault pixel is not charged to `FP_w`,
and known-fault pixels are not part of `G` (so they are not `FN_w` either).

**Consequence — the free carpet is weakly dominant.** Adding mass `v = 1` to a
known-fault pixel contributes `dF = 0` and `dT >= 0`. Then
`d(DTI) = dT * D / (D + 0.2 * dT)` when `dF = 0`… and since `D >= 0`, this is
never negative. Turning every known-fault pixel on cannot lower the score and
can raise it wherever a *new* fault lies within 300 m of a mapped one.

## Break-even rule for charged mass

With `D = 0.2*(T+F) + 0.8*K`, `s = T/D`, and one unit of mass whose realised
kernel credit is `k` and whose FP charge is `u` (so `u = 1 - k` off the mask,
`u = 0` on it):

    d(DTI) > 0   <=>   k*(D - T*(0.2 - 0.8)) > 0.2*T*u
                 <=>   k > 0.2*s*u / (1 - 0.2*s + 0.8*s)

At `s = 0.28` this is `k > 0.0479` for a charged pixel and `k > 0` for a free
one. `src/gems34/metric.py::marginal_bar` implements exactly this, and
`tests/test_metric.py` verifies it against a brute-force perturbation rather
than against a re-derivation.

## What this implies for an emission

* Emit the free carpet — it is free and it is sometimes worth a lot.
* Everywhere else, emit only where the *expected* kernel credit exceeds
  `marginal_bar(s)`. A candidate location with a 10 % chance of a new fault
  within 300 m at an average kernel weight of 0.5 has expected credit 0.05,
  which is *at* the bar for `s = 0.28` — so a location needs roughly a
  one-in-ten chance of hosting a real fault to be worth a charged pixel.
* Spacing: because coverage is a max over a 300 m disk, predictions packed
  closer than ~300 m do not add independent coverage; the useful packing is
  approximately one prediction per 300 m of target structure.

## Where the collapse came from

`docs/data/collapse-diagnosis.json` measures it: the three artifacts that
scored 0.1563 are two copies of one file plus a strict superset of it whose
54,533 extra pixels lie **100.00 % on the free mask**. Because free-mask mass is
metrically inert, the "improvement" step of the pipeline could not change the
score — and indeed it did not. The gate in `src/gems34/registry.py` therefore
compares the **payload** (support minus free mask), not the whole file: Dice
over the non-free support, plus the support-restricted Pearson correlation of
the raw surfaces, plus exact-duplicate checks on both the values and the
support.
