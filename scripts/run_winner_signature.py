#!/usr/bin/env python3
"""What does the group's best-scoring emission actually key on?

The 0.2778 artifact (``h33-h33-2-b2``, 37,654 isolated off-catalogue dots) is the
group's best claimed score.  Its generating field is not published, but its
*output* is.  So this script measures, for every band in the feature stack, how
the value distribution at the winner's dots differs from a size-matched random
off-catalogue sample: mean percentile shift, Mann-Whitney style rank lift, and
the fraction of dots in the band's top decile.

A band with a large positive lift is a band the winning field was using.  That
is the only way to learn from the artifact without copying it.

Usage
-----
    python scripts/run_winner_signature.py --data data --ext /tmp/ext \
        --corpus /tmp/corpus --out docs/data/winner-signature.json
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
from gems34 import fields34 as F  # noqa: E402

WINNER = ("GEMSDOE32__docs_downloads_gemsdoe32-h33-h33-2-b2-"
          "20261004T220000Z-e5eb6e7e-zeros.tif")
RUNNER = ("GEMSDOE28__docs_downloads_gems28-h27-4-r1-solo-d2-8-"
          "20261003-8acb75e1f2cc-nan.tif")
LOW = "14GEMSDOE__docs_downloads_GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0_site_e96e942f.tif"


def pct_rank(a, m):
    a = np.asarray(a, np.float64)
    idx = np.flatnonzero(m.ravel())
    v = a.ravel()[idx]
    order = np.argsort(v, kind="stable")
    r = np.empty(v.size, np.float64)
    r[order] = np.arange(v.size, dtype=np.float64) / max(v.size - 1, 1)
    out = np.full(a.size, np.nan)
    out[idx] = r
    return out.reshape(a.shape)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--ext", default="/tmp/ext")
    ap.add_argument("--corpus", default="/tmp/corpus")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    st = F.load_stack(a.data, a.ext if os.path.isdir(a.ext) else None)
    inside, cat = st.inside, st.cat
    dcat = ndi.distance_transform_edt(~cat)
    eligible = inside & ~cat

    sets = {}
    for tag, fn in (("winner_0.2778", WINNER), ("runner_0.2708", RUNNER),
                    ("worst_0.0020", LOW)):
        p = os.path.join(a.corpus, fn)
        if not os.path.exists(p):
            print("missing", fn)
            continue
        arr = rasterio.open(p).read(1)
        sets[tag] = (np.nan_to_num(arr, nan=0.0) > 0) & eligible
        print(f"{tag:16s} n={int(sets[tag].sum()):7d}")

    rng = np.random.default_rng(7)
    n_ref = int(sets["winner_0.2778"].sum())
    pool = np.flatnonzero(eligible.ravel())
    sets["random_matched"] = np.zeros(eligible.shape, bool)
    sets["random_matched"].ravel()[rng.choice(pool, n_ref, replace=False)] = True

    rows = []
    for name, band in sorted(st.bands.items()):
        pr = pct_rank(band, inside)
        base = np.nanmean(pr[inside])
        row = dict(band=name, percentile_in_footprint=round(float(base), 4))
        for tag, m in sets.items():
            v = pr[m]
            v = v[np.isfinite(v)]
            row[tag] = dict(mean_percentile=round(float(v.mean()), 4),
                            lift=round(float(v.mean() - base), 4),
                            pct_in_top_decile=round(100.0 * float((v > 0.9).mean()), 2),
                            pct_in_top_1pct=round(100.0 * float((v > 0.99).mean()), 2))
        rows.append(row)

    # distance-to-catalogue profile of each set
    prof = {}
    for tag, m in sets.items():
        d = dcat[m]
        prof[tag] = dict(p10=round(float(np.percentile(d, 10)), 1),
                         p50=round(float(np.median(d)), 1),
                         p90=round(float(np.percentile(d, 90)), 1),
                         pct_le_3px=round(100 * float((d <= 3).mean()), 2),
                         pct_le_10px=round(100 * float((d <= 10).mean()), 2))

    rows.sort(key=lambda r: -r["winner_0.2778"]["lift"])
    print(f"\n{'band':26s} {'winner lift':>12} {'runner lift':>12} {'worst lift':>11} "
          f"{'rand lift':>10} {'win top1%':>10}")
    print("-" * 88)
    for r in rows:
        print(f"{r['band'][:26]:26s} {r['winner_0.2778']['lift']:+12.4f} "
              f"{r['runner_0.2708']['lift']:+12.4f} {r['worst_0.0020']['lift']:+11.4f} "
              f"{r['random_matched']['lift']:+10.4f} "
              f"{r['winner_0.2778']['pct_in_top_1pct']:10.2f}")
    print("\ndistance-to-catalogue profile (px):")
    for tag, p in prof.items():
        print(f"  {tag:16s} p10={p['p10']:6.1f} p50={p['p50']:6.1f} p90={p['p90']:7.1f} "
              f"<=3px={p['pct_le_3px']:5.2f}%  <=10px={p['pct_le_10px']:5.2f}%")

    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump(dict(generated_utc=datetime.now(timezone.utc).isoformat(),
                       n_sets={k: int(v.sum()) for k, v in sets.items()},
                       distance_profile=prof, bands=rows),
                  open(a.out, "w"), indent=1)
        print("\nwrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
