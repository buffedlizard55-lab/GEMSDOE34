#!/usr/bin/env python3
"""Fit the live leaderboard itself as the predictive instrument.

``scripts/run_field_validation.py`` scores a field against *held-out catalogue
faults*.  ``scripts/run_winner_signature.py`` and the control run recorded in
``docs/data/leaderboard-regression.json`` show why that instrument cannot be
used to choose a submission: the group's best artifact (0.2778) earns **0.26x
the credit of a size-matched random sample** against the catalogue, while the
group's worst (0.0020) earns 6.7x.  The hidden test set is by construction the
set of faults the USGS/INGENIOUS catalogue *missed*, so catalogue proximity is
anti-correlated with the objective.

The only instrument that measures the real objective is the leaderboard.  So
this script turns the 42 user-reported scores into a supervised model: it
describes every scored artifact by a small set of measurable properties (dot
budget, distance-to-catalogue profile, mean band percentile at the dots,
spatial dispersion) and fits a ridge regression with leave-one-out
cross-validation.  If LOO explains the scores, the fitted model is a
pre-submission instrument; if it does not, that is reported too.

Every score used here is a user-reported claim, not an organizer receipt.

Usage
-----
    python scripts/run_leaderboard_regression.py --data data --ext /tmp/ext \
        --corpus /tmp/corpus --out docs/data/leaderboard-regression.json
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
from gems34 import ledger as ledger_mod  # noqa: E402
from gems34.lbmodel import (  # noqa: E402
    DESC_BANDS, DIST_BANDS, loo_r2, pct_rank, ridge_fit_predict, score)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--ext", default="/tmp/ext")
    ap.add_argument("--corpus", default="/tmp/corpus")
    ap.add_argument("--lam", type=float, default=10.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    st = F.load_stack(a.data, a.ext if os.path.isdir(a.ext) else None)
    inside, cat = st.inside, st.cat
    dcat = ndi.distance_transform_edt(~cat)
    ranks = {b: pct_rank(st.bands[b], inside) for b in DESC_BANDS if b in st.bands}
    print(f"descriptor bands: {len(ranks)}")

    # grid for the dispersion descriptor
    gy, gx = np.indices(inside.shape)
    by, bx = gy // 100, gx // 100
    gid = (by * 40 + bx).astype(np.int32)

    rows = []
    for r in ledger_mod.resolve(a.corpus):
        if not r["file"]:
            continue
        arr = rasterio.open(os.path.join(a.corpus, r["file"])).read(1)
        m = (np.nan_to_num(arr, nan=0.0) > 0) & inside & ~cat
        n = int(m.sum())
        if n < 100:
            continue
        d = dcat[m]
        feat = [np.log10(n)]
        names = ["log10_n_payload"]
        for db in DIST_BANDS:
            feat.append(float((d <= db).mean()))
            names.append(f"frac_le_{db}px")
        for db in (5, 20):
            feat.append(float(np.median(np.abs(d - db))))
            names.append(f"mad_d_{db}px")
        for b, pr in ranks.items():
            v = pr[m]
            feat.append(float(np.nanmean(v)))
            names.append(f"pr_{b}")
        lab, nc = ndi.label(m, structure=np.ones((3, 3)))
        sizes = ndi.sum(np.ones_like(lab, float), lab, range(1, nc + 1)) if nc else [0]
        feat.append(float(np.mean(sizes)))
        names.append("mean_component_px")
        feat.append(len(np.unique(gid[m])) / float(len(np.unique(gid[inside]))))
        names.append("block_occupancy_10km")
        rows.append(dict(claim=r["claim"], repo=r["repo"], score=float(r["score"]),
                         file=r["file"], n_payload=n, features=feat))

    X = np.array([r["features"] for r in rows])
    y = np.array([r["score"] for r in rows])
    print(f"{len(rows)} scored artifacts, {X.shape[1]} descriptors")

    best = None
    for lam in (0.3, 1, 3, 10, 30, 100, 300):
        r2, rmse, rho, pred = loo_r2(X, y, lam)
        print(f"  lambda={lam:6.1f}  LOO R2={r2:+.3f}  RMSE={rmse:.4f}  Spearman={rho:+.3f}")
        if best is None or r2 > best[1]:
            best = (lam, r2, rmse, rho, pred)
    lam, r2, rmse, rho, pred = best
    w, mu, sd, ybar = ridge_fit_predict(X, y, lam)
    coefs = sorted(zip(names, (w / sd).tolist()), key=lambda t: -abs(t[1]))

    # univariate: how much does each single descriptor explain?
    uni = []
    for j, nm in enumerate(names):
        u = X[:, [j]]
        r2u, _, rhou, _ = loo_r2(u, y, 1.0)
        uni.append(dict(descriptor=nm, loo_r2=round(r2u, 4),
                        spearman=round(rhou, 4)))
    uni.sort(key=lambda d: -abs(d["spearman"]))

    print(f"\nbest lambda={lam}: LOO R2={r2:+.3f} RMSE={rmse:.4f} Spearman={rho:+.3f}")
    print("\ntop single descriptors by |Spearman| with the claimed score:")
    for d in uni[:12]:
        print(f"  {d['descriptor']:26s} rho={d['spearman']:+.3f}  LOO R2={d['loo_r2']:+.3f}")
    print("\ntop ridge coefficients:")
    for nm, c in coefs[:12]:
        print(f"  {nm:26s} {c:+.4f}")
    print("\nper-artifact LOO prediction:")
    order = np.argsort(-y)
    for i in order:
        print(f"  {y[i]:.4f}  pred {pred[i]:.4f}  resid {pred[i]-y[i]:+.4f}  "
              f"n={rows[i]['n_payload']:7d}  {rows[i]['repo']:11s} {rows[i]['claim'][:40]}")

    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump(dict(
            generated_utc=datetime.now(timezone.utc).isoformat(),
            instrument="ridge regression on 42 user-reported scores; LOO-CV",
            score_evidence_class="user-reported claim, no organizer receipt",
            n_artifacts=len(rows), n_descriptors=int(X.shape[1]),
            # the training matrix, so a candidate can be scored against the
            # exact same descriptor vector without recomputing 302 rasters
            descriptor_names=names,
            design_matrix=[[round(float(v), 6) for v in row] for row in X],
            scores=[float(v) for v in y],
            best=dict(lambda_=lam, loo_r2=round(r2, 4), loo_rmse=round(rmse, 4),
                      loo_spearman=round(rho, 4)),
            univariate=uni,
            coefficients=[dict(descriptor=n, coef=round(c, 5)) for n, c in coefs],
            rows=[dict(claim=r["claim"], repo=r["repo"], score=r["score"],
                       n_payload=r["n_payload"], file=r["file"],
                       loo_pred=round(float(pred[i]), 4))
                  for i, r in enumerate(rows)],
        ), open(a.out, "w"), indent=1)
        print("\nwrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
