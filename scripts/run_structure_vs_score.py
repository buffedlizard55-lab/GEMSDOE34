#!/usr/bin/env python3
"""Measure what the group's own live scores say about *where* winning mass goes.

For every artifact in the score ledger this computes, against the official
``labels.tif`` (the USGS/INGENIOUS catalogue that the organizers confirmed is
masked out of the penalty terms):

* ``n_positive`` / ``n_payload``   total mass and mass off the free mask
* ``pct_payload_on_catalogue``     mass inside 3 px of a catalogue pixel
* distance-to-catalogue deciles of the payload
* component statistics (is it dots or blobs?)
* footprint compliance

and then reports the rank correlation of each structural statistic with the
claimed score.  Nothing here assumes a model of the hidden truth: it is a
descriptive instrument over 36 live-scored artifacts.

Usage
-----
    python scripts/run_structure_vs_score.py --corpus /tmp/corpus \
        --data data --out docs/data/structure-vs-score.json
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from gems34 import ledger as ledger_mod  # noqa: E402

RING_PX = 3            # 300 m kernel support at 100 m resolution
DECILES = [0, 1, 3, 5, 10, 20, 50, 100, 1e9]


def spearman(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return float("nan")
    xr = np.argsort(np.argsort(x[ok])).astype(float)
    yr = np.argsort(np.argsort(y[ok])).astype(float)
    if xr.std() == 0 or yr.std() == 0:
        return float("nan")
    return float(np.corrcoef(xr, yr)[0, 1])


def pearson(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3 or x[ok].std() == 0 or y[ok].std() == 0:
        return float("nan")
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="/tmp/corpus")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    with rasterio.open(os.path.join(a.data, "labels.tif")) as ds:
        lab = ds.read(1)
    inside = lab != -1                      # 5,167,373 valid cells (measured)
    cat = lab > 0                           # 60,988 catalogue cells (measured)
    # distance (px) from every cell to the nearest catalogue cell
    dcat = ndi.distance_transform_edt(~cat)

    rows = []
    for r in ledger_mod.resolve(a.corpus):
        if not r["file"]:
            continue
        with rasterio.open(os.path.join(a.corpus, r["file"])) as ds:
            arr = ds.read(1)
            shape_ok = (ds.width, ds.height) == (3292, 3730)
            crs_ok = str(ds.crs) == "EPSG:32611"
        p = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        pos = p > 0
        pay = pos & ~cat                    # mass the metric can actually charge
        npos, npay = int(pos.sum()), int(pay.sum())
        if npay == 0:
            continue
        d = dcat[pay]
        hist = {}
        for lo, hi in zip(DECILES[:-1], DECILES[1:]):
            hist[f"{int(lo)}-{int(hi) if hi < 1e9 else 'inf'}px"] = round(
                100.0 * float(((d >= lo) & (d < hi)).mean()), 2)
        lab_arr, ncomp = ndi.label(pos, structure=np.ones((3, 3)))
        sizes = ndi.sum(np.ones_like(lab_arr), lab_arr, range(1, ncomp + 1)) if ncomp else np.array([0])
        rows.append(dict(
            repo=r["repo"], claim=r["claim"], score=r["score"], file=r["file"],
            sha256=r["sha256"], shape_ok=bool(shape_ok), crs_ok=bool(crs_ok),
            nodata=(None if not np.isnan(np.asarray(arr, float)).any() else "nan"),
            n_positive=npos, n_payload=npay,
            pct_on_catalogue=round(100.0 * (npos - npay) / npos, 2),
            pct_payload_outside_footprint=round(100.0 * float((~inside[pos]).mean()), 2),
            dcat_payload_p50=round(float(np.median(d)), 2),
            dcat_payload_p10=round(float(np.percentile(d, 10)), 2),
            dcat_payload_p90=round(float(np.percentile(d, 90)), 2),
            pct_payload_within_100m=round(100.0 * float((d <= 1).mean()), 2),
            pct_payload_within_300m=round(100.0 * float((d <= 3).mean()), 2),
            pct_payload_within_1km=round(100.0 * float((d <= 10).mean()), 2),
            pct_payload_within_5km=round(100.0 * float((d <= 50).mean()), 2),
            dist_hist_pct=hist,
            n_components=int(ncomp),
            mean_comp_px=round(float(sizes.mean()), 3),
            pct_mass_in_single_px_comp=round(
                100.0 * float((sizes == 1).sum()) / max(ncomp, 1), 2),
        ))

    keys = ["n_positive", "n_payload", "pct_on_catalogue", "dcat_payload_p50",
            "pct_payload_within_300m", "pct_payload_within_1km",
            "pct_payload_within_5km", "n_components", "mean_comp_px",
            "pct_mass_in_single_px_comp"]
    sc = [r["score"] for r in rows]
    corr = {}
    for k in keys:
        v = [r[k] for r in rows]
        corr[k] = dict(pearson=round(pearson(v, sc), 4), spearman=round(spearman(v, sc), 4))
    # credit-per-pixel is the quantity the metric actually rewards
    cpx = [r["score"] / max(r["n_payload"], 1) for r in rows]
    corr["_score_per_payload_px (ref)"] = dict(
        pearson=None, spearman=None,
        note="score / n_payload; reported for the fitted model, not correlated")

    out = dict(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        labels_sha256="7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
        n_artifacts=len(rows),
        score_evidence_class="user-reported claim (no organizer receipt exists)",
        correlation_with_claimed_score=corr,
        rows=sorted(rows, key=lambda r: -r["score"]),
    )
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump(out, open(a.out, "w"), indent=1)
        print("wrote", a.out)

    print(f"\n{len(rows)} live-scored artifacts, structure vs claimed score\n")
    hdr = f"{'score':>7} {'repo':11} {'n_pos':>7} {'n_pay':>7} {'%cat':>6} {'d50':>6} {'%<=3px':>7} {'%<=1km':>7} {'ncomp':>7} {'mean':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in sorted(rows, key=lambda r: -r["score"]):
        print(f"{r['score']:7.4f} {r['repo']:11} {r['n_positive']:7d} {r['n_payload']:7d} "
              f"{r['pct_on_catalogue']:6.1f} {r['dcat_payload_p50']:6.1f} "
              f"{r['pct_payload_within_300m']:7.1f} {r['pct_payload_within_1km']:7.1f} "
              f"{r['n_components']:7d} {r['mean_comp_px']:7.2f}")
    print("\nSpearman(statistic, claimed score):")
    for k, v in corr.items():
        if v.get("spearman") is not None:
            print(f"  {k:34s} rho={v['spearman']:+.3f}  r={v['pearson']:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
