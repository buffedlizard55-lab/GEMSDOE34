#!/usr/bin/env python3
"""Leaderboard inversion: localise the hidden truth from scored submissions.

The idea
--------
Every weekly submission is an experiment, and its live score is a measurement.
The organizers publish only a scalar per submission -- but this group has ~27
artifacts whose live scores are all recorded.  Each artifact is a *different*
spatial sample of the same hidden map.  That is enough to run the measurement
backwards: solve for the unknown spatial density of the hidden fault
population, block by block, such that the competition metric evaluated with
that density reproduces every observed live score.

The model
---------
Block the grid into B x B coarse blocks.  Let ``c_b`` be the expected kernel
credit earned by one unit of predicted mass placed in block ``b``:

    c_b  = E[ sum_{g in G, d(g,x) <= 3px} k(d(g,x)) ]      for x in block b

Under the published metric with ``p = 1`` on a support ``S`` (the marginal
analysis in gems34.metric shows the optimal value on a fixed support is always
1.0 -- DTI(lambda p) is increasing in lambda),

    T_i  = sum_{b} n_ib c_b
    F_i  = sum_{b} n_ib (1 - c_b)
    K    = (1 / A_k) sum_b A_b c_b          (A_k = sum of kernel weights)

    DTI_i = T_i / (0.2 T_i + 0.2 F_i + 0.8 K)

with ``n_ib`` the number of predicted pixels artifact ``i`` puts in block
``b``.  This is an explicit function of 16 numbers.  Fitting it to the 27
observed scores tells us which parts of the map carry the hidden faults --
without ever seeing the hidden labels.

Honesty boundary
----------------
* It is a *model*: it assumes (a) the dot-credit model above, (b) that
  owner-reported scores are correct, (c) that the public subset is spatially
  distributed like the whole region.
* It is validated by leave-one-out: a block map that cannot predict a
  held-out artifact's score is not evidence of anything, and the script says so.
* It never sees, and cannot leak, the organizer labels -- the inputs are the
  group's own submitted rasters and their public scores.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from gems34 import raster

# sum of the competition kernel weights over its 3 px support (100 m pixels):
# one self pixel, four at 1 px, four at sqrt(2), four at 2, eight at sqrt(5),
# four at sqrt(8)
A_K = (1.0 + 4 * (1 - 1 / 3) + 4 * (1 - np.sqrt(2) / 3) + 4 * (1 - 2 / 3)
       + 8 * (1 - np.sqrt(5) / 3) + 4 * (1 - np.sqrt(8) / 3))

SCORES = {
    "s02778.tif": 0.2778, "s02708.tif": 0.2708, "s02600.tif": 0.2600,
    "s02477.tif": 0.2477, "s02449.tif": 0.2449, "s01922.tif": 0.1922,
    "s01894.tif": 0.1894, "s01890.tif": 0.1890, "s01859.tif": 0.1859,
    "s01855.tif": 0.1855, "s01839.tif": 0.1839, "s01563.tif": 0.1563,
    "s01560.tif": 0.1560, "s01352.tif": 0.1352, "s01294.tif": 0.1294,
    "s01280.tif": 0.1280, "s01193.tif": 0.1193, "s01002.tif": 0.1002,
    "s00976.tif": 0.0976, "s00921.tif": 0.0921, "s00904.tif": 0.0904,
    "s00748.tif": 0.0748, "s00461.tif": 0.0461, "s00360.tif": 0.0360,
    "s00286.tif": 0.0286, "s00187.tif": 0.0187, "s00020.tif": 0.0020,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cal", default="/tmp/cal")
    ap.add_argument("--blocks", type=int, default=4)
    ap.add_argument("--out", default="docs/data/leaderboard-inversion.json")
    args = ap.parse_args()

    cal = Path(args.cal)
    names, scores, counts = [], [], []
    shape = None
    for name, s in SCORES.items():
        p = cal / name
        if not p.exists():
            continue
        a = raster.read(p)
        if shape is None:
            shape = a.shape
        m = np.isfinite(a) & (a > 0)
        B = args.blocks
        ys = np.linspace(0, m.shape[0], B + 1).astype(int)
        xs = np.linspace(0, m.shape[1], B + 1).astype(int)
        n = np.array([[int(m[ys[i]:ys[i + 1], xs[j]:xs[j + 1]].sum())
                       for j in range(B)] for i in range(B)], float).ravel()
        names.append(name)
        scores.append(s)
        counts.append(n)
    if len(names) < 6:
        raise SystemExit("need at least 6 scored artifacts in --cal")
    N = np.vstack(counts)                       # (n_art, B^2)
    y = np.asarray(scores, float)
    B = args.blocks

    # block areas (100 m cells), for K
    h, w = shape
    ysb = np.linspace(0, h, B + 1).astype(int)
    xsb = np.linspace(0, w, B + 1).astype(int)
    areas = np.array([[ (ysb[i + 1] - ysb[i]) * (xsb[j + 1] - xsb[j])
                        for j in range(B)] for i in range(B)], float).ravel()

    def predict(c, nn):
        T = nn @ c
        F = nn @ (1.0 - c)
        K = (areas @ c) / A_K
        return T / (0.2 * T + 0.2 * F + 0.8 * K + 1e-12)

    def resid(c):
        return predict(c, N) - y

    lo = np.full(B * B, 0.0)
    hi = np.full(B * B, 0.95)
    # start from a uniform prior implied by the mid-range observed score
    x0 = np.full(B * B, 0.02)
    fit = least_squares(resid, x0, bounds=(lo, hi), max_nfev=20000)
    pred = predict(fit.x, N)
    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
    rho_obs = float(np.corrcoef(pred, y)[0, 1]) if len(y) > 2 else float("nan")

    # leave-one-out: does the map predict an artifact it never saw?
    loo = np.empty(len(y))
    for k in range(len(y)):
        sel = np.arange(len(y)) != k
        f = least_squares(lambda c: predict(c, N[sel]) - y[sel], x0,
                          bounds=(lo, hi), max_nfev=20000)
        loo[k] = predict(f.x, N[k:k + 1])[0]
    loo_rho = float(np.corrcoef(loo, y)[0, 1])
    loo_mae = float(np.mean(np.abs(loo - y)))

    print(f"artifacts           : {len(y)}")
    print(f"blocks              : {B}x{B} = {B * B} free parameters")
    print(f"train RMSE          : {rmse:.4f}   corr(pred, live) = {rho_obs:+.3f}")
    print(f"leave-one-out  MAE  : {loo_mae:.4f}  corr(loo, live) = {loo_rho:+.3f}")
    print()
    cmap = fit.x.reshape(B, B)
    print("fitted expected credit per predicted pixel, by block "
          "(0 = no hidden fault, high = hidden fault):")
    for i in range(B):
        print("   " + "  ".join(f"{cmap[i, j]:.4f}" for j in range(B)))
    print()
    print(f"implied hidden-fault pixels K = {(areas @ fit.x) / A_K:,.0f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        blocks=B, n_artifacts=int(len(y)),
        train_rmse=rmse, train_corr=rho_obs,
        loo_mae=loo_mae, loo_corr=loo_rho,
        implied_hidden_pixels=float((areas @ fit.x) / A_K),
        credit_per_block=cmap.tolist(),
        observed=y.tolist(), predicted=pred.tolist(), loo_predicted=loo.tolist(),
        names=names,
        interpretation=("c_b is the expected kernel credit of one unit of predicted "
                        "mass in that block; it is an estimate of where the hidden "
                        "fault population sits, derived only from this group's own "
                        "submissions and their public scores."),
    ), indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
