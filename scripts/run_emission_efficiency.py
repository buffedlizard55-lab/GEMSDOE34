#!/usr/bin/env python3
"""How much hidden-fault credit does one emitted dot actually buy?

Under the published metric, with unit-valued predictions on a support ``S`` of
size ``n`` and total kernel credit ``T``, the Tversky index is *exactly*

    DTI = T / (0.2 n + 0.8 K)                       (derived in docs/method.md)

because TP_w = T, FN_w = K - T and FP_w = n - T.  So the score is:

  * linear in T at fixed n  -> raising the *credit per dot* is the whole game;
  * decreasing in n at fixed T -> never emit a dot that earns nothing;
  * optimised at the n where the marginal dot's credit equals 0.2 * DTI.

Neither T nor K is observable live, so this script measures the credit-per-dot
curve ``c(n) = T(n)/n`` against an *independent official fault catalogue*:
USGS SGMC, restricted to faults the competition catalogue does not carry.  The
absolute values are not the live values -- the hidden truth is not SGMC -- but
the comparison between two emissions on the same instrument is meaningful.

What it does
------------
1. Ranks candidate dots by the G34 composite field with greedy non-maximum
   suppression at the kernel radius (isolated single-pixel dots, >= 3 px apart).
2. Scores prefixes of that ranking against the proxy truth on a *spatially
   blocked* split of the proxy: the proxy is cut into 4 x 4 blocks and the
   credit curve is reported per fold, so a result cannot come from one corner.
3. Reports the same curve for the group's live-scored artifacts, for contrast.
4. Reports the elasticity p = d log T / d log n, which is the quantity that
   decides whether adding dots helps: adding helps iff p > 0.2n/(0.2n+0.8K).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from gems34 import raster

A_K = 9.38647751263546   # sum of kernel weights over the 3 px support


def greedy_rank(tau: np.ndarray, zone: np.ndarray, cap: int, spacing: float = 3.0):
    """Greedy NMS at ``spacing`` px; returns (ranked_y, ranked_x, values)."""
    c = int(np.floor(spacing / np.sqrt(2.0)))
    offs = np.array([(dy, dx) for dy in range(-c - 1, c + 2)
                     for dx in range(-c - 1, c + 2)
                     if np.hypot(dy, dx) < spacing], np.int32)
    t = np.where(zone, tau, 0.0)
    cy, cx = np.nonzero(t > 0)
    v = t[cy, cx]
    order = np.argsort(-v, kind="stable")[:cap]
    h, w = tau.shape
    blocked = np.zeros((h, w), bool)
    ys, xs = [], []
    oy, ox = offs[:, 0], offs[:, 1]
    for i in order:
        y, x = int(cy[i]), int(cx[i])
        if blocked[y, x]:
            continue
        ys.append(y); xs.append(x)
        yy, xx = y + oy, x + ox
        g = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
        blocked[yy[g], xx[g]] = True
    return np.array(ys, np.int32), np.array(xs, np.int32), v[order]


def prefix_dots(ys, xs, n, shape):
    m = np.zeros(shape, bool)
    m[ys[:n], xs[:n]] = True
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--sgmc", default="/tmp/hist/sgmc_g30.tif")
    ap.add_argument("--cal", default="/tmp/cal")
    ap.add_argument("--cap", type=int, default=300_000)
    ap.add_argument("--out", default="docs/data/emission-efficiency.json")
    args = ap.parse_args()

    from gems34 import geology
    from gems34.metric import score_fast
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_submission_h6 as B
    import rasterio

    labels = raster.read(Path(args.data) / "labels.tif")
    cat = labels == 1
    footprint = np.isfinite(raster.read(Path(args.data) / "sample_submission.tif"))
    sgmc = raster.read(args.sgmc)
    dcat = geology.distance_to(cat)
    pnf = (sgmc > 0) & (dcat > 3) & footprint
    print(f"proxy truth (SGMC off-catalogue): {int(pnf.sum()):,} px")

    bands = {}
    with rasterio.open(Path(args.data) / "training_features.tif") as s:
        for k in B.BAND:
            a = s.read(B.BAND[k] + 1).astype(np.float32)
            a[~np.isfinite(a)] = 0.0
            a[np.abs(a) >= 1.0e30] = 0.0
            bands[k] = a
    comp = B.build_fields(bands)["composite"]
    del bands
    comp[~footprint] = 0.0
    comp[cat] = 0.0
    from gems34 import holdout
    tau = holdout.smooth(comp)
    zone = footprint & ~cat & (dcat > 3)
    print("ranking candidate dots (greedy NMS at 3 px) ...", flush=True)
    ys, xs, vals = greedy_rank(tau, zone, args.cap)
    print(f"  ranked {ys.size:,} dots")

    # spatially blocked proxy folds: exclude the fold's own block from the truth
    h, w = cat.shape
    B4 = 4
    ysb = np.linspace(0, h, B4 + 1).astype(int)
    xsb = np.linspace(0, w, B4 + 1).astype(int)
    n_grid = [5000, 10000, 20000, 30000, 37654, 50000, 75000, 100000, 150000]
    out = {"grid": [h, w], "pixels_per_unit_credit": A_K,
           "proxy_pixels": int(pnf.sum()), "curve": []}
    print(f"{'n':>8} {'T_pnf':>10} {'c=T/n':>8} {'DTI_pnf':>8}")
    for n in n_grid:
        if n > ys.size:
            continue
        m = prefix_dots(ys, xs, n, cat.shape)
        c = score_fast(m.astype(np.float32), pnf, cat)
        # blocked variant: hold out one quadrant of the proxy truth at a time
        blocked = []
        for bi in range(B4):
            for bj in range(B4):
                blk = np.zeros_like(pnf)
                blk[ysb[bi]:ysb[bi + 1], xsb[bj]:xsb[bj + 1]] = True
                t = pnf & blk
                if t.sum() < 50:
                    continue
                blocked.append(float(score_fast(m.astype(np.float32), t, cat)["dti"]))
        out["curve"].append(dict(n=int(n), T=float(c["tp"]), c_per_dot=float(c["tp"] / n),
                                 dti_pnf=float(c["dti"]),
                                 blocked_mean=float(np.mean(blocked)) if blocked else None,
                                 blocked_min=float(np.min(blocked)) if blocked else None,
                                 blocked_positive_folds=int(sum(1 for b in blocked if b > 0))))
        print(f"{n:8d} {c['tp']:10.1f} {c['tp'] / n:8.4f} {c['dti']:8.5f}   "
              f"blocked mean {np.mean(blocked) if blocked else 0:.5f} "
              f"({sum(1 for b in blocked if b > 0)}/{len(blocked)} folds > 0)")

    # elasticity
    cs = [(r["n"], r["T"]) for r in out["curve"] if r["T"] > 0]
    if len(cs) >= 2:
        ln_n = np.log([a for a, _ in cs]); ln_T = np.log([b for _, b in cs])
        p = float(np.polyfit(ln_n, ln_T, 1)[0])
        out["elasticity_p"] = p
        out["note"] = ("adding dots helps iff p > 0.2n/(0.2n+0.8K); with the "
                       "K implied by the group's own live history (see "
                       "docs/method.md) the threshold is ~0.45 at n=37,654")
        print(f"\nelasticity p = d log T / d log n = {p:+.3f}")
        print("  threshold at n=37,654 (K~11.6k) = +0.449 -> "
              f"{'MORE dots help' if p > 0.449 else 'FEWER dots help'}")

    # contrast: the group's live-scored isolated-dot artifacts, same instrument
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parent))
    from run_calibration import CALIBRATION
    cal = Path(args.cal)
    out["reference_artifacts"] = []
    print("\nreference artifacts on the same instrument (T from their own rasters):")
    for name, (score, _prov) in CALIBRATION.items():
        p = cal / name
        if not p.exists():
            continue
        a = raster.read(p)
        m = np.isfinite(a) & (a > 0)
        c = score_fast(np.where(m, 1.0, 0.0).astype(np.float32), pnf, cat)
        out["reference_artifacts"].append(
            dict(name=name, live=score, n=int(m.sum()), T=float(c["tp"]),
                 c_per_dot=float(c["tp"] / max(m.sum(), 1)), dti_pnf=float(c["dti"])))
    for r in sorted(out["reference_artifacts"], key=lambda r: -r["live"])[:6]:
        print(f"  live {r['live']:.4f}  n={r['n']:7,}  T={r['T']:8.1f}  "
              f"c/dot={r['c_per_dot']:.4f}")

    pth = Path(args.out); pth.parent.mkdir(parents=True, exist_ok=True)
    out["generated_utc"] = datetime.now(timezone.utc).isoformat()
    pth.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {pth}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
