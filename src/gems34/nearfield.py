"""Near-field instrument: contiguous-run holdout of mapped fault traces.

Why a second instrument is needed
---------------------------------
The blocked/geographic instrument in :mod:`gems34.holdout` holds out whole
4x4 blocks, so the truth population sits hundreds to thousands of metres from
the visible catalogue.  That instrument therefore tests *far-field*
generalisation, and it systematically under-rates the one population the
organizers actually describe:

    chrisk-dd, 2026-09-23: "'new fault' means 'any fault pixel not already
    captured by USGS/INGENIOUS' and can include newly mapped geometry of an
    existing fault system."
    https://community.drivendata.org/t/where-do-you-draw-the-line/11536

New geometry of an existing system lies *within* a few hundred metres of the
mapped trace.  The near-field instrument reproduces that geometry exactly: it
removes contiguous runs of mapped trace (the "unmapped" parts), leaves the rest
of the catalogue visible, and asks a rule to recover the removed runs under the
organizers' masking rule.  Runs are cut from the skeleton so they follow the
real fault geometry, and the removed population is, by construction, adjacent to
visible catalogue -- the same relationship the organizers describe.

Honesty boundary: the removed runs are catalogue geometry, not the organizers'
private new-fault list.  A rule that wins here has demonstrated that it can
recover unmapped geometry adjacent to mapped traces under the real metric; it
has not demonstrated that the hidden faults are of that kind.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt
from scipy.spatial import cKDTree

from . import geology
from .metric import ALPHA, EPS, _KERNEL_OFFSETS, kernel


def cut_runs(cat: np.ndarray, n_seeds: int = 400, run_radius: float = 6.0,
             line_halfwidth: int = 2, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(truth, visible)`` -- contiguous removed runs and what is left."""
    cat = np.asarray(cat, bool)
    sk = geology.skeleton(cat)
    ys, xs = np.nonzero(sk)
    if ys.size == 0:
        return np.zeros_like(cat), cat.copy()
    rng = np.random.default_rng(seed)
    n = min(n_seeds, ys.size)
    pick = rng.choice(ys.size, size=n, replace=False)
    tree = cKDTree(np.c_[ys, xs])
    chosen = set()
    for i in pick:
        for j in tree.query_ball_point((ys[i], xs[i]), r=run_radius):
            chosen.add(j)
    m = np.zeros(cat.shape, bool)
    idx = np.fromiter(chosen, dtype=np.int64)
    m[ys[idx], xs[idx]] = True
    truth = binary_dilation(m, iterations=line_halfwidth) & cat
    visible = cat & ~truth
    return truth, visible


def score(emission: np.ndarray, truth: np.ndarray, free: np.ndarray) -> dict:
    """Metric score of one emission against a near-field run holdout."""
    truth = np.asarray(truth, bool)
    free = np.asarray(free, bool)
    p = np.clip(np.where(np.isfinite(emission), emission, 0.0), 0, 1).astype(np.float32)
    h, w = p.shape
    gy, gx = np.nonzero(truth)
    n = int(gy.size)
    best = np.zeros(n, dtype=np.float32)
    for dy, dx, kk in _KERNEL_OFFSETS:
        y = gy + dy; x = gx + dx
        ok = (y >= 0) & (y < h) & (x >= 0) & (x < w)
        vals = np.zeros(n, dtype=np.float32)
        vals[ok] = p[y[ok], x[ok]] * np.float32(kk)
        np.maximum(best, vals, out=best)
    tp = float(best.sum())
    dt = distance_transform_edt(~truth).astype(np.float32)
    fp = float((np.where(free, np.float32(0), p) *
                (np.float32(1) - kernel(dt).astype(np.float32))).sum())
    del dt
    return dict(dti=tp / (tp + ALPHA * fp + 0.8 * (n - tp) + EPS), tp=tp, fp=fp,
                fn=n - tp, n_truth=n, emitted=float((p > 0).sum()))


def carpet(free: np.ndarray) -> np.ndarray:
    out = np.zeros(free.shape, np.float32)
    out[np.asarray(free, bool)] = 1.0
    return out
