"""Descriptor vector and ridge machinery for the leaderboard-regression model.

Shared by ``scripts/run_leaderboard_regression.py`` (fits the model to the 42
live leaderboard scores) and ``scripts/run_candidate_selection.py`` (scores a
candidate with the fitted model).  Keeping one definition matters: a candidate
described with even slightly different features than the training set is
silently extrapolating.
"""
from __future__ import annotations

import numpy as np

# bands whose mean percentile at the emitted dots is used as a descriptor
DESC_BANDS = ["det_elev_slope", "det_elev", "tmi_hg", "iso_grav_anom",
              "geod_2ndinv", "geod_dilaterate", "depth_to_base_surf",
              "cond_surf", "tc", "tmi_vg", "rad_K", "rad_Th", "rad_U", "rad_TC",
              "ext_UK", "ext_UTh", "lid_ex_max", "lid_relief", "lid_upface_max",
              "lid_step_max", "lid_coh100"]
DIST_BANDS = [1, 2, 3, 5, 10, 20, 40, 80]


def pct_rank(a, m):
    """Empirical rank transform over the valid mask, in [0, 1]."""
    a = np.asarray(a, np.float64)
    idx = np.flatnonzero(m.ravel())
    v = a.ravel()[idx]
    order = np.argsort(v, kind="stable")
    r = np.empty(v.size, np.float64)
    r[order] = np.arange(v.size, dtype=np.float64) / max(v.size - 1, 1)
    out = np.full(a.size, np.nan)
    out[idx] = r
    return out.reshape(a.shape).astype(np.float32)


def ridge_fit_predict(X, y, lam):
    """Standardised ridge with intercept.  Returns (weights, mean, sd, ybar)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    mu, sd = X.mean(0), X.std(0) + 1e-12
    Z = (X - mu) / sd
    yc = y - y.mean()
    A = Z.T @ Z + lam * np.eye(Z.shape[1])
    w = np.linalg.solve(A, Z.T @ yc)
    return w, mu, sd, float(y.mean())


def score(feat, w, mu, sd, ybar):
    return float(ybar + ((np.asarray(feat, float) - mu) / sd) @ w)


def loo_r2(X, y, lam):
    """Leave-one-out R^2, RMSE and Spearman for a given ridge penalty."""
    y = np.asarray(y, float)
    n = len(y)
    pred = np.zeros(n)
    for i in range(n):
        tr = [j for j in range(n) if j != i]
        w, mu, sd, ybar = ridge_fit_predict(X[tr], y[tr], lam)
        pred[i] = score(X[i], w, mu, sd, ybar)
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    rx = np.argsort(np.argsort(pred)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    return (1 - ss_res / ss_tot, float(np.sqrt(ss_res / n)),
            float(np.corrcoef(rx, ry)[0, 1]), pred)
