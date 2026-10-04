"""Official DOE GEMS Prize metric (distance-weighted Tversky index).

Transcribed on 2026-10-04 from the organizer's problem description,
"Performance metric" section:

    https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/

The published equations are:

    k(d)  = max(1 - d/R, 0)                      triangular kernel, R = 300 m
    TP_w  = sum_{g in G} max_{x: d(x,g)<=R} p(x) k(d(x,g))
    FP_w  = sum_{x: p(x)>0} p(x) [1 - max_{g in G} k(d(x,g))]
    FN_w  = sum_{g in G} [1 - max_{x: d(x,g)<=R} p(x) k(d(x,g))]
    DTI   = TP_w / (TP_w + alpha FP_w + beta FN_w + eps),   alpha=0.2, beta=0.8

At 100 m raster resolution R = 3 px.

Two independent code paths are provided:

``dti_literal``  - a direct, slow, O(|G| * |P|) loop over the published sums.
                   Used as the oracle in the test-suite.
``components``   - the fast path (explicit kernel shifts + a Euclidean distance
                   transform). It is accepted only because ``tests/test_metric.py``
                   proves the two agree on random rasters.

Known-fault masking
-------------------
The organizers confirmed on the official forum that pixels corresponding to
known USGS/INGENIOUS faults are masked out of evaluation and therefore do not
count towards the penalty terms:

    chrisk-dd (DrivenData Staff), 2026-09-16, post 2 of
    https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516

    "1. Pixels corresponding to known USGS/INGENIOUS faults are masked /
     excluded from evaluation, so they do not count towards penalty terms.
     2. Re-evaluation will also mask/exclude the existing USGS/INGENIOUS faults."

``free`` below is that mask: prediction mass on a free pixel is not charged to
FP_w.  The *literature* reading of the mask (exact catalogue pixels only) is
``mode="exact"``; the conservative reading (a 3 px neighbourhood is also free)
is ``mode="dilate3"``.  Every decision in this repository is taken under both.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA: float = 0.2
BETA: float = 0.8
R_M: float = 300.0          # kernel support, metres (published)
RES_M: float = 100.0        # published raster resolution
R_PX: float = R_M / RES_M   # = 3.0
EPS: float = 1e-12

_KERNEL_OFFSETS: tuple[tuple[int, int, float], ...] = tuple(
    (dy, dx, max(1.0 - float(np.hypot(dy, dx)) / R_PX, 0.0))
    for dy in range(-3, 4)
    for dx in range(-3, 4)
    if max(1.0 - float(np.hypot(dy, dx)) / R_PX, 0.0) > 0.0
)


def kernel(d):
    """k(d) = max(1 - d/R, 0). ``d`` is in pixels."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / R_PX, 0.0)


# ---------------------------------------------------------------------------
# oracle: literal transcription of the published equations
# ---------------------------------------------------------------------------
def dti_literal(pred, truth, free=None, alpha=ALPHA, beta=BETA):
    p = np.asarray(pred, dtype=np.float64)
    p = np.where(np.isfinite(p), p, 0.0)
    t = np.asarray(truth) > 0
    if free is not None:
        free = np.asarray(free, bool)
    gs = np.argwhere(t)
    xs = np.argwhere(p > 0)
    tp = fn = fp = 0.0
    for gy, gx in gs:
        best = 0.0
        for py, px in xs:
            d = float(np.hypot(py - gy, px - gx))
            if d <= R_PX:
                best = max(best, p[py, px] * (1.0 - d / R_PX))
        tp += best
        fn += 1.0 - best
    for py, px in xs:
        if free is not None and free[py, px]:
            continue
        kmax = 0.0
        for gy, gx in gs:
            d = float(np.hypot(py - gy, px - gx))
            if d <= R_PX:
                kmax = max(kmax, 1.0 - d / R_PX)
        fp += p[py, px] * (1.0 - kmax)
    return dict(tp=tp, fp=fp, fn=fn, n_truth=int(t.sum()),
                dti=tp / (tp + alpha * fp + beta * fn + EPS))


# ---------------------------------------------------------------------------
# fast exact path
# ---------------------------------------------------------------------------
def _neighbourhood_max(grid: np.ndarray) -> np.ndarray:
    """For each pixel, max over the 3 px disk of ``grid`` times the kernel.

    Implemented as explicit shifts so that no assumption is made about the
    geometry of the (non-separable) cone kernel.
    """
    out = np.zeros_like(grid)
    h, w = grid.shape
    for dy, dx, kk in _KERNEL_OFFSETS:
        if dy == 0 and dx == 0:
            ys = slice(0, h)
            xs = slice(0, w)
            np.maximum(out, grid * kk, out=out)
            continue
        ys = slice(max(0, -dy), h - max(0, dy))
        xs = slice(max(0, -dx), w - max(0, dx))
        yd = slice(max(0, dy), h - max(0, -dy))
        xd = slice(max(0, dx), w - max(0, -dx))
        np.maximum(out[yd, xd], grid[ys, xs] * kk, out=out[yd, xd])
    return out


def components(pred, truth, free=None, alpha=ALPHA, beta=BETA) -> dict:
    """Exact TP_w / FP_w / FN_w and the metric. Soft predictions allowed."""
    p = np.asarray(pred, dtype=np.float64).copy()
    p[~np.isfinite(p)] = 0.0
    p = np.clip(p, 0.0, 1.0)
    g = np.asarray(truth, bool)
    n = int(g.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, dti=0.0,
                    coverage=0.0, mass=float(p.sum()))
    mass = float(p.sum())
    credit = _neighbourhood_max(p)
    tp = float(credit[g].sum())
    fn = float(n) - tp
    if free is not None:
        p = np.where(np.asarray(free, bool), 0.0, p)
    dg = distance_transform_edt(~g)
    fp = float((p * (1.0 - kernel(dg))).sum())
    dti = tp / (tp + alpha * fp + beta * fn + EPS)
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, dti=float(dti),
                coverage=tp / n, mass=mass)


def dti(pred, truth, free=None, **kw) -> float:
    return score_fast(pred, truth, free, **kw)["dti"]


def score_fast(pred, truth, free=None, alpha=ALPHA, beta=BETA) -> dict:
    """Fast exact scorer: gather-based TP_w, distance-transform FP_w.

    Equivalent to :func:`dti_literal`; equality is asserted in the test-suite.
    The gather formulation is ~5 orders of magnitude cheaper than the literal
    double loop and is what makes a parameter sweep tractable on CPU.
    """
    p = np.asarray(pred, dtype=np.float64)
    p = np.where(np.isfinite(p), p, 0.0)
    p = np.clip(p, 0.0, 1.0)
    g = np.asarray(truth, bool)
    n = int(g.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, dti=0.0, coverage=0.0)
    gy, gx = np.nonzero(g)
    h, w = p.shape
    best = np.zeros(n, dtype=np.float64)
    for dy, dx, kk in _KERNEL_OFFSETS:
        y = gy + dy
        x = gx + dx
        ok = (y >= 0) & (y < h) & (x >= 0) & (x < w)
        if not ok.any():
            continue
        vals = np.zeros(n, dtype=np.float64)
        vals[ok] = p[y[ok], x[ok]] * kk
        np.maximum(best, vals, out=best)
    tp = float(best.sum())
    fn = float(n) - tp
    charged = p if free is None else np.where(np.asarray(free, bool), 0.0, p)
    dg = distance_transform_edt(~g)
    fp = float((charged * (1.0 - kernel(dg))).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, coverage=tp / n,
                dti=tp / (tp + alpha * fp + beta * fn + EPS))


# ---------------------------------------------------------------------------
# decision theory
# ---------------------------------------------------------------------------
def marginal_bar(s: float, u: float = 1.0, alpha: float = ALPHA,
                 beta: float = BETA) -> float:
    """Minimum kernel credit k for one extra unit of mass to improve DTI at ``s``.

    Write the metric as DTI = T/D with D = alpha*(T+F) + beta*(K-T), where T is
    the weighted truth credit, F the false-positive charge and K the truth mass
    (so that FN_w = K - T exactly).  One extra unit of mass with realised kernel
    credit k and FP charge u contributes dT = k, dF = u, hence

        dD = alpha*(k + u) - beta*k = k*(alpha - beta) + alpha*u

    and d(DTI) > 0  <=>  k*D > T*dD.  With D = T/s this reduces to

        k > alpha*s*u / (1 - alpha*s + beta*s)

    Both correction terms matter: the beta term comes from the truth pixels a
    *hit* also removes from FN_w, and dropping it (as this function did before
    the Pass-2 review) overstates the bar by alpha*s/beta*s ~ 25 % at s = 0.3.

    For a free pixel u = 0 and any positive k improves the score, so saturating
    the known-fault mask with mass is weakly dominant -- the free carpet.

    Sanity check at s = 0.28 (the group's best claimed score): the bar is
    alpha*s/(1 - alpha*s + beta*s) = 0.0560/(0.944 + 0.224) = 0.0479, i.e. a
    candidate pixel needs an expected kernel credit above ~4.8 %.
    """
    return alpha * s * u / (1.0 - alpha * s + beta * s)


def required_coverage(s: float, rho: float, alpha: float = ALPHA,
                      beta: float = BETA) -> float:
    """Weighted truth coverage T/K required for score ``s`` at FP ratio rho = F/K.

    DTI = T / (alpha*(T+F) + beta*(K-T)); solve for T/K.  Used to state what a
    claimed score implies about coverage and FP mass, without needing the truth.
    """
    return s * (alpha * rho + beta) / (1.0 - alpha * s + beta * s)


@dataclass(frozen=True)
class Verdict:
    dti: float
    tp: float
    fp: float
    fn: float
    n_truth: int
    coverage: float

    @classmethod
    def make(cls, c: dict) -> "Verdict":
        return cls(c["dti"], c["tp"], c["fp"], c["fn"], c["n_truth"], c.get("coverage", 0.0))
