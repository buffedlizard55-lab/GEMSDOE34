#!/usr/bin/env python3
"""Spatially-blocked validation of the candidate fields, and the budget law.

Two questions are answered here, both before any weekly slot is touched.

**1. Which physical signature actually finds faults?**
The competition labels are a rasterised USGS/INGENIOUS catalogue and the hidden
test set is *new* faults of the same kind.  So the honest instrument is: hold
the catalogue out block by block, build each field from features alone (none of
the candidates uses catalogue proximity, so there is nothing to leak), emit it
as isolated dots at a fixed budget, and score with the organizer's own metric
against the held-out catalogue.

**2. How much does credit fall when the budget is cut?**
This is the number that decides the submission.  The metric identity gives
``T = s(0.2n + 0.8M)/(1 - 0.2s)``; ``scripts/run_mass_and_elasticity.py`` bounds
the hidden truth mass at ``M in [8355, 11153]`` from nesting alone and measures
the credit elasticity *above* 37,654 dots.  Cutting *below* 37,654 is
extrapolation -- so the credit-vs-budget curve is measured here directly on real
faults and rescaled by the truth-mass ratio.

Usage
-----
    python scripts/run_field_validation.py --data data --ext /tmp/ext --side 5 \
        --budgets 2000,4000,8000,12000,16000,20000,28000,37654,50000,80000 \
        --out docs/data/field-validation.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from gems34 import fields34 as F  # noqa: E402

R_PX = 3.0
OFFS = [(dy, dx, max(1.0 - float(np.hypot(dy, dx)) / R_PX, 0.0))
        for dy in range(-3, 4) for dx in range(-3, 4)]
OFFS = [o for o in OFFS if o[2] > 0.0]


def gather_credit(dots_val, coords, h, w):
    """For each truth pixel, max over its 3 px disk of ``dots_val * k``."""
    gy, gx = coords[:, 0], coords[:, 1]
    best = np.zeros(len(gy), np.float64)
    for dy, dx, kk in OFFS:
        y, x = gy + dy, gx + dx
        ok = (y >= 0) & (y < h) & (x >= 0) & (x < w)
        if not ok.any():
            continue
        v = np.zeros(len(gy), np.float64)
        v[ok] = dots_val[y[ok], x[ok]] * kk
        np.maximum(best, v, out=best)
    return best


def reach_array(mask):
    """max_{x in mask} k(d(x, .)) over the whole array."""
    out = np.zeros(mask.shape, np.float64)
    h, w = mask.shape
    m = mask.astype(np.float64)
    for dy, dx, kk in OFFS:
        ys, xs = slice(max(0, -dy), h - max(0, dy)), slice(max(0, -dx), w - max(0, dx))
        yd, xd = slice(max(0, dy), h - max(0, -dy)), slice(max(0, dx), w - max(0, -dx))
        np.maximum(out[yd, xd], m[ys, xs] * kk, out=out[yd, xd])
    return out


def nms_rank(field, eligible):
    """Rank eligible pixels by value with >= 3 px separation.  1 = best."""
    f = np.where(eligible, field, -np.inf)
    loc = ndi.maximum_filter(f, size=7, mode="constant", cval=-np.inf)
    peaks = eligible & (f >= loc)
    vals = f[peaks]
    order = np.argsort(-vals)
    rank = np.zeros(field.shape, np.int32)
    ys, xs = np.nonzero(peaks)
    rank[ys[order], xs[order]] = np.arange(1, int(peaks.sum()) + 1, dtype=np.int32)
    return rank


def bbox(mask, pad=6):
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return None
    return (int(max(ys.min() - pad, 0)), int(min(ys.max() + pad + 1, mask.shape[0])),
            int(max(xs.min() - pad, 0)), int(min(xs.max() + pad + 1, mask.shape[1])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--ext", default="/tmp/ext")
    ap.add_argument("--side", type=int, default=5, help="blocks per axis (side^2 folds)")
    ap.add_argument("--budgets",
                    default="2000,4000,8000,12000,16000,20000,28000,37654,50000,80000")
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", default=None,
                    help="comma-separated substrings; keep only matching fields")
    a = ap.parse_args()
    budgets = [int(x) for x in a.budgets.split(",")]

    st = F.load_stack(a.data, a.ext if os.path.isdir(a.ext) else None)
    inside, cat = st.inside, st.cat
    H, W = inside.shape
    print(f"footprint {int(inside.sum()):,} px, catalogue {int(cat.sum()):,} px, "
          f"{len(st.bands)} bands", flush=True)

    k = a.side
    by = np.arange(H)[:, None] // ((H + k - 1) // k)
    bx = np.arange(W)[None, :] // ((W + k - 1) // k)
    blk = (by * k + bx).astype(np.int16)
    folds = []
    for i in range(k * k):
        fm = blk == i
        if (fm & cat).sum() > 100:
            bb = bbox(fm & inside)
            if bb:
                folds.append((i, fm, bb))
    print(f"{len(folds)} spatial blocks with >100 catalogue px", flush=True)

    fields = F.field_candidates(st)
    if a.only:
        keep = [k for k in fields
                if any(t.strip().lower() in k.lower() for t in a.only.split(","))]
        for k in list(fields):
            if k not in keep:
                del fields[k]
        print("validating:", list(fields), flush=True)
    results = []
    for name, fld in fields.items():
        fld = np.where(inside, fld, 0.0).astype(np.float32)
        per_fold, shares = [], []
        agg = {n: {"T": [], "F": [], "n": []} for n in budgets}
        for fi, fm, (y0, y1, x0, x1) in folds:
            sub_in = inside[y0:y1, x0:x1]
            sub_cat = cat[y0:y1, x0:x1]
            sub_fm = fm[y0:y1, x0:x1]
            truth = sub_cat & sub_fm            # the held-out catalogue
            known = sub_cat & ~sub_fm           # a submission may not use these
            elig = sub_in & ~known
            if truth.sum() == 0 or elig.sum() == 0:
                continue
            h, w = sub_in.shape
            share = (h * w) / float(H * W)
            shares.append(share)
            tcoords = np.argwhere(truth)
            reach_t = reach_array(truth)
            rank = nms_rank(fld[y0:y1, x0:x1], elig)
            row = {"fold": fi, "n_truth": int(truth.sum()), "budgets": {}}
            for n in budgets:
                nloc = max(1, int(round(n * share)))
                dots = (rank > 0) & (rank <= nloc)
                nd = int(dots.sum())
                T = float(gather_credit(dots.astype(np.float64), tcoords, h, w).sum())
                Fp = float((1.0 - reach_t[dots]).sum())
                row["budgets"][str(n)] = dict(n=nd, n_target=n, T=round(T, 1),
                                              F=round(Fp, 1),
                                              credit_per_dot=round(T / max(nd, 1), 4))
                agg[n]["T"].append(T)
                agg[n]["F"].append(Fp)
                agg[n]["n"].append(nd)
            per_fold.append(row)
        mshare = float(np.mean(shares))
        curve = {str(n): dict(n_mean=round(float(np.mean(agg[n]["n"])) / mshare, 1),
                              T_mean=round(float(np.mean(agg[n]["T"])), 2),
                              F_mean=round(float(np.mean(agg[n]["F"])), 2),
                              credit_per_dot_mean=round(
                                  float(np.mean(agg[n]["T"])) / max(float(np.mean(agg[n]["n"])), 1), 4))
                 for n in budgets if agg[n]["T"]}
        nn = np.array([curve[str(n)]["n_mean"] for n in budgets], float)
        TT = np.array([curve[str(n)]["T_mean"] for n in budgets], float)
        dn = np.diff(nn)
        dTdn = np.where(dn > 0, np.diff(TT) / np.maximum(dn, 1e-9), np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            elas = np.where((dn > 0) & (TT[:-1] > 0),
                            np.diff(np.log(np.maximum(TT, 1e-9))) /
                            np.where(dn > 0, np.log(nn[1:] / nn[:-1]), np.nan), np.nan)
        ivs = [f"{budgets[i]}->{budgets[i+1]}" for i in range(len(budgets) - 1)]
        results.append(dict(field=name, curve=curve,
                            marginal_credit=[None if not np.isfinite(x) else round(float(x), 4)
                                             for x in dTdn],
                            elasticity=[None if not np.isfinite(x) else round(float(x), 4)
                                        for x in elas],
                            budget_intervals=ivs, folds=per_fold))
        lab = " ".join(f"T@{n}={curve[str(n)]['T_mean']:.0f}" for n in budgets)
        bl = " ".join(f"b[{iv}]={e:+.3f}" for iv, e in zip(ivs, elas) if np.isfinite(e))
        print(f"  {name[:42]:42s} {lab}  {bl}", flush=True)

    key = "28000" if "28000" in curve else str(budgets[len(budgets) // 2])
    results.sort(key=lambda r: -(r["curve"].get(key, {}).get("T_mean") or 0))
    out = dict(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        instrument=("spatially-blocked catalogue holdout; fields are feature-only "
                    "so there is no catalogue leakage"),
        truth_mass_instrument=int(cat.sum()),
        hidden_truth_mass_bound=[8355.4, 11153.3],
        truth_mass_ratio=round(9754.0 / int(cat.sum()), 4),
        n_folds=len(folds), budgets=budgets, sort_key=key,
        ranking_by_T_at_key=[r["field"] for r in results],
        results=results,
    )
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump(out, open(a.out, "w"), indent=1)
        print("\nwrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
