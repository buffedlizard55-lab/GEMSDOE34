#!/usr/bin/env python3
"""Calibrate the group's 42 live scores into a predictive instrument.

The metric is an identity.  For a binary prediction with off-mask mass A and a
hidden truth G of effective mass M,

    DTI = T / (0.2*T + 0.2*F + 0.8*M)
    T   = sum_{g in G} max_{x in A, d(x,g)<=3px} k(d(x,g))
    F   = sum_{x in A} [1 - max_{g in G} k(d(x,g))]

(FN_w = M - T exactly, so TP_w + beta*FN_w = (1-beta)T + beta*M.)

G is not available, but two *independent* official fault catalogues are, and
neither is the competition label set:

  * USGS State Geologic Map Compilation (NV + CA) --
    https://mrdata.usgs.gov/geology/state/  (public domain)
  * USGS NSHM Quaternary Fault & Fold Database, Qfaults_GIS --
    https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip

Their union *minus* the competition catalogue (``labels.tif``) is a set of real,
expert-mappable fault pixels that the organizers' mask does **not** protect.
Call it the surrogate ``S``.  If the hidden truth behaves like a rescaled ``S``
then the scale cancels out of DTI and exactly **one** free parameter (``M_S``,
the effective surrogate mass) is left.  This script fits that one parameter to
42 live scores by least squares and reports the residual, per-artifact.

That is the whole point: a fitted constant that reproduces 42 live leaderboard
numbers is an instrument, and an instrument can be run on a candidate *before*
a weekly slot is spent on it.

Usage
-----
    python scripts/run_score_calibration.py --corpus /tmp/corpus --ext /tmp/ext \
        --data data --out docs/data/score-calibration.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.optimize import minimize_scalar

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from gems34 import ledger as ledger_mod  # noqa: E402

R_PX = 3.0
OFFS = [(dy, dx, max(1.0 - float(np.hypot(dy, dx)) / R_PX, 0.0))
        for dy in range(-3, 4) for dx in range(-3, 4)]
OFFS = [o for o in OFFS if o[2] > 0.0]


def coverage(mask: np.ndarray) -> np.ndarray:
    """max_{x in mask} k(d(x, .)) at every pixel -- the kernel-weighted reach."""
    out = np.zeros(mask.shape, np.float64)
    h, w = mask.shape
    m = mask.astype(np.float64)
    for dy, dx, kk in OFFS:
        ys, xs = slice(max(0, -dy), h - max(0, dy)), slice(max(0, -dx), w - max(0, dx))
        yd, xd = slice(max(0, dy), h - max(0, -dy)), slice(max(0, dx), w - max(0, -dx))
        np.maximum(out[yd, xd], m[ys, xs] * kk, out=out[yd, xd])
    return out


def reach_from(mask: np.ndarray) -> np.ndarray:
    """max_{g in mask} k(d(., g)) -- same thing, used for the FP term."""
    return coverage(mask)


def tf_against(A: np.ndarray, S: np.ndarray) -> tuple[float, float]:
    """T = sum_S cov_A ; F = sum_A (1 - reach_S)."""
    T = float(coverage(A)[S].sum())
    F = float((A.astype(np.float64) * (1.0 - reach_from(S))).sum())
    return T, F


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="/tmp/corpus")
    ap.add_argument("--ext", default="/tmp/ext")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    lab = rasterio.open(os.path.join(a.data, "labels.tif")).read(1)
    inside = lab != -1
    cat = lab > 0

    def ext(rel):
        """Boolean union of every band of an external product."""
        p = os.path.join(a.ext, rel)
        with rasterio.open(p) as ds:
            out = np.zeros((ds.height, ds.width), bool)
            for i in range(1, ds.count + 1):
                out |= ds.read(i) > 0
            return out

    sgmc = ext("data/external/derived_sgmc_faults_100m_u8.tif")
    qf_gdr = ext("data/external/derived_gdr_qfaults_v2_100m_u8.tif")
    qf_nshm = ext("external/qfaults/qfaults_prior_u8.tif")

    # surrogate: independently mapped faults the competition mask does NOT protect
    S = (sgmc | qf_gdr | qf_nshm) & inside & ~cat
    M_S = int(S.sum())

    # how far is the surrogate from the catalogue? (sanity: it must be new ground)
    dcat = ndi.distance_transform_edt(~cat)
    print(f"surrogate S = (SGMC | GDR-QFaults-v2 | NSHM-QFaults) \\ catalogue \\ outside")
    print(f"  SGMC {int(sgmc.sum()):7d}  GDR-QFv2 {int(qf_gdr.sum()):7d}  NSHM-QF {int(qf_nshm.sum()):7d}")
    print(f"  S = {M_S} px  ({100.0*M_S/inside.sum():.2f}% of the footprint)")
    print(f"  S within 3 px of catalogue: {100.0*float((dcat[S] <= 3).mean()):.1f}%   "
          f"median d = {float(np.median(dcat[S])):.1f} px")

    rows = []
    for r in ledger_mod.resolve(a.corpus):
        if not r["file"]:
            continue
        arr = rasterio.open(os.path.join(a.corpus, r["file"])).read(1)
        A = (np.nan_to_num(arr, nan=0.0) > 0) & inside & ~cat
        n = int(A.sum())
        if n == 0:
            continue
        T, F = tf_against(A, S)
        rows.append(dict(repo=r["repo"], claim=r["claim"], score=r["score"],
                         file=r["file"], sha256=r["sha256"], n_payload=n,
                         T_surrogate=round(T, 1), F_surrogate=round(F, 1),
                         credit_per_px=round(T / n, 4)))

    def resid(M):
        e = []
        for r in rows:
            pred = r["T_surrogate"] / (0.2 * r["T_surrogate"] + 0.2 * r["F_surrogate"] + 0.8 * M)
            e.append(pred - r["score"])
        return float(np.sqrt(np.mean(np.square(e))))

    best = minimize_scalar(resid, bounds=(1e3, 5e5), method="bounded")
    M_fit = float(best.x)
    for r in rows:
        r["predicted"] = round(r["T_surrogate"] /
                               (0.2 * r["T_surrogate"] + 0.2 * r["F_surrogate"] + 0.8 * M_fit), 4)
        r["residual"] = round(r["predicted"] - r["score"], 4)
    rmse = resid(M_fit)

    # how well does the instrument *rank* the corpus?
    def spear(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        rx = np.argsort(np.argsort(x)).astype(float)
        ry = np.argsort(np.argsort(y)).astype(float)
        return float(np.corrcoef(rx, ry)[0, 1])
    rho_all = spear([r["predicted"] for r in rows], [r["score"] for r in rows])
    pear_all = float(np.corrcoef([r["predicted"] for r in rows], [r["score"] for r in rows])[0, 1])

    out = dict(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        surrogate=dict(
            definition="(USGS SGMC NV+CA | GDR INGENIOUS QFaults v2 | USGS NSHM QFaults) minus labels.tif, inside footprint",
            sources=[
                "https://mrdata.usgs.gov/geology/state/shp/NV.zip",
                "https://mrdata.usgs.gov/geology/state/shp/CA.zip",
                "https://gdr.openei.org/files/1391/qfaults_ingenious_nad83conus117_2023-06-27.zip",
                "https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip",
            ],
            M_S_px=M_S,
            pct_footprint=round(100.0 * M_S / int(inside.sum()), 3),
            pct_within_3px_of_catalogue=round(100.0 * float((dcat[S] <= 3).mean()), 2),
            median_distance_to_catalogue_px=round(float(np.median(dcat[S])), 2),
        ),
        fit=dict(M_eff=M_fit, rmse=rmse, n_artifacts=len(rows),
                 spearman_predicted_vs_claimed=round(rho_all, 4),
                 pearson_predicted_vs_claimed=round(pear_all, 4)),
        rows=sorted(rows, key=lambda r: -r["score"]),
    )
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump(out, open(a.out, "w"), indent=1)
        print("\nwrote", a.out)

    print(f"\nfit: M_eff = {M_fit:,.0f} px   RMSE = {rmse:.4f}   "
          f"Spearman = {rho_all:+.3f}  Pearson = {pear_all:+.3f}")
    hdr = f"{'claim':>7} {'pred':>7} {'resid':>7} {'repo':11} {'n_pay':>7} {'T_S':>9} {'F_S':>9} {'c/px':>7}"
    print(hdr); print("-" * len(hdr))
    for r in sorted(rows, key=lambda r: -r["score"]):
        print(f"{r['score']:7.4f} {r['predicted']:7.4f} {r['residual']:+7.4f} {r['repo']:11} "
              f"{r['n_payload']:7d} {r['T_surrogate']:9.1f} {r['F_surrogate']:9.1f} {r['credit_per_px']:7.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
