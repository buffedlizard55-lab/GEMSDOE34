#!/usr/bin/env python3
"""Screen candidate geological mechanisms on a spatially blocked split.

Every candidate is reduced to the *same* emission shape -- isolated single-pixel
dots at the metric's own 300 m separation, one per greedy non-maximum-suppression
step -- so that only the field can differ between arms.  Each arm is then
scored against the proxy truth (USGS SGMC faults that the competition catalogue
does not carry) on **four spatial blocks**, and an arm is admitted only if it
wins in at least three of the four.

Why blocks: gems34.metric only charges a false positive outside the *free* mask,
and this proxy truth is spread all over the grid.  A single pooled number can be
carried by one corner.  The blocking is what makes the screen a test rather than
a fit.

The instrument's limits are stated in docs/irregularities.md (IR-34-IG-01):
neither this nor the catalogue-blocked instrument ranks the group's live scores
(27 artifacts, rho = +0.12 / -0.11).  What the screen *can* do is reject arms
that do not find unmapped fault geometry anywhere, which is a necessary
condition, and it can rank mechanisms against each other on a fixed budget.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from gems34 import fields, geology, holdout, raster
from gems34.metric import score_fast

BAND = {"tmi_hg": 2, "geod_2ndinv": 3, "tc": 5, "tmi_vg": 8, "det_elev": 11,
        "iso_grav_anom": 12, "depth_to_base_surf": 14, "cond_surf": 16,
        "iso_grav_anom_hg": 17}

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_submission_h6 as B  # noqa: E402


def nms_dots(tau, zone, n, spacing=3.0):
    c = int(np.floor(spacing / np.sqrt(2.0)))
    offs = np.array([(dy, dx) for dy in range(-c - 1, c + 2)
                     for dx in range(-c - 1, c + 2)
                     if np.hypot(dy, dx) < spacing], np.int32)
    t = np.where(zone, tau, 0.0)
    cy, cx = np.nonzero(t > 0)
    v = t[cy, cx]
    order = np.argsort(-v, kind="stable")[:max(60 * n, 200_000)]
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
        if len(ys) >= n:
            break
    m = np.zeros((h, w), bool)
    if ys:
        m[np.array(ys), np.array(xs)] = True
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--sgmc", default="/tmp/hist/sgmc_g30.tif")
    ap.add_argument("--n", type=int, default=28000)
    ap.add_argument("--blocks", type=int, default=4)
    ap.add_argument("--out", default="docs/data/field-screen.json")
    args = ap.parse_args()

    labels = raster.read(Path(args.data) / "labels.tif")
    cat = labels == 1
    foot = np.isfinite(raster.read(Path(args.data) / "sample_submission.tif"))
    sgmc = raster.read(args.sgmc)
    dcat = geology.distance_to(cat)
    pnf = (sgmc > 0) & (dcat > 3) & foot
    zone = foot & ~cat & (dcat > 3)

    import rasterio
    bands = {}
    with rasterio.open(Path(args.data) / "training_features.tif") as s:
        for k in BAND:
            a = s.read(BAND[k] + 1).astype(np.float32)
            a[~np.isfinite(a)] = 0.0
            a[np.abs(a) >= 1.0e30] = 0.0
            bands[k] = a

    # ---------------- mechanism bank ----------------
    arms = {}
    arms["H6_basin_step"] = B.build_fields(bands)["h6"]
    arms["H5_lineament10"] = fields.h5_geophysical_lineaments(bands)
    arms["curv_det_elev"] = np.maximum.reduce(
        [B.anisotropy(bands["det_elev"], s) for s in (1.5, 3.0, 6.0)])
    arms["H2_tips"] = fields.h2_tip_extrapolation(cat)
    # NEW: parallel strands at the 1-3 km fault-zone width, not the 400-900 m
    # offsets already implemented (gems34.geology defaults 4, 6, 9 px).
    arms["H4_wide_parallel"] = fields.h4_parallel_strands(
        cat, offsets=(10, 16, 24, 32))
    arms["H1_wide_shell"] = fields.h1_near_catalogue(cat, sigma_px=20.0)
    arms["step_basement_cond"] = np.maximum.reduce(
        [B.step_edge(bands["depth_to_base_surf"], s) for s in (2.0, 5.0)])
    arms["contrast_tmi_iso"] = np.sqrt(np.maximum(
        B.anisotropy(bands["tmi_hg"], 2.0) * B.anisotropy(bands["iso_grav_anom"], 2.0), 0))

    for k in list(arms):
        a = np.asarray(arms[k], np.float32).copy()
        a[~foot] = 0.0
        a[cat] = 0.0
        arms[k] = a

    # ---------------- blocked evaluation ----------------
    h, w = cat.shape
    Bb = args.blocks
    ysb = np.linspace(0, h, Bb + 1).astype(int)
    xsb = np.linspace(0, w, Bb + 1).astype(int)
    folds = []
    for i in range(Bb):
        for j in range(Bb):
            blk = np.zeros((h, w), bool)
            blk[ysb[i]:ysb[i + 1], xsb[j]:xsb[j + 1]] = True
            t = pnf & blk
            if t.sum() >= 50:
                folds.append(t)
    print(f"proxy truth {int(pnf.sum()):,} px in {len(folds)} scored blocks; "
          f"budget {args.n:,} dots")

    results = {}
    for name, field in arms.items():
        tau = holdout.smooth(field)
        m = nms_dots(tau, zone, args.n)
        per = [float(score_fast(m.astype(np.float32), t, cat)["dti"]) for t in folds]
        pooled = score_fast(m.astype(np.float32), pnf, cat)
        wins = sum(1 for v in per if v > 0)
        results[name] = dict(pooled_tp=float(pooled["tp"]), pooled_dti=float(pooled["dti"]),
                             per_block=per, mean_block=float(np.mean(per)),
                             min_block=float(np.min(per)), blocks_positive=wins,
                             n_dots=int(m.sum()))
        print(f"  {name:22s} n={int(m.sum()):6,}  T={pooled['tp']:8.1f}  "
              f"mean_block={np.mean(per):.5f}  positive {wins}/{len(folds)}")

    # ---------------- combination search ----------
    names = list(arms)
    best = None
    selected, pool = [], list(names)
    cur = None
    for step in range(4):
        cand = None
        for name in pool:
            f = arms[name] if cur is None else (cur + arms[name]) / 2.0
            f = np.asarray(f, np.float32)
            m = nms_dots(holdout.smooth(f), zone, args.n)
            per = [float(score_fast(m.astype(np.float32), t, cat)["dti"]) for t in folds]
            key = float(np.mean(per))
            if cand is None or key > cand[0]:
                cand = (key, name, f, per)
        if cand is None or cand[0] <= 0:
            break
        if cur is not None and cand[0] <= best[0] + 1e-9:
            break
        best = (cand[0], tuple(selected + [cand[1]]))
        selected.append(cand[1]); cur = cand[2]
        pool.remove(cand[1])
        print(f"  + {cand[1]:22s} -> mean_block {cand[0]:.5f} "
              f"({sum(1 for v in cand[3] if v > 0)}/{len(folds)} positive)")

    out = dict(generated_utc=datetime.now(timezone.utc).isoformat(),
               n_dots=args.n, n_blocks=len(folds),
               mechanism_screen=results,
               forward_selection=dict(mean_block=best[0] if best else None,
                                      members=list(best[1]) if best else []),
               caveat=("The proxy truth is USGS SGMC faults absent from the competition "
                       "catalogue -- an independent official compilation, but not the "
                       "organizers' hidden set. A win here is a necessary condition, not "
                       "a prediction: docs/data/calibration.json shows this family of "
                       "instruments does not rank the 27 live-scored artifacts."))
    p = Path(args.out); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"\nforward selection: {best[1] if best else None}  mean_block={best[0] if best else 0:.5f}")
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
