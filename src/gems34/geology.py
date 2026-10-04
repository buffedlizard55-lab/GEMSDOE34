"""Structural primitives derived from the known-fault catalogue.

Why these primitives
--------------------
The organizers fixed the definition of the prediction target on the official
forum (post 2, 2026-09-23):

    "For the purposes of this competition, 'new fault' means 'any fault pixel
     not already captured by USGS/INGENIOUS' and can include newly mapped
     geometry of an existing fault system."

    https://community.drivendata.org/t/where-do-you-draw-the-line/11536

and separately fixed the scoring treatment of the catalogue (post 2, 2026-09-16):

    "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded
     from evaluation, so they do not count towards penalty terms."

    https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516

Taken together those two statements define the exploitable structure of the
problem:

  * mass placed *on* the catalogue is free (no FP charge);
  * the target population is *new geometry of existing systems* -- i.e. fault
    continuations, splays, parallel strands and linkage zones immediately
    around the mapped traces.

This module supplies the structural primitives that name those geometries:
skeleton, tips, local strike, tip extrapolation, gap bridging and parallel
strands.  Everything is derived from ``labels.tif`` only, so the tooling has no
external-data dependency and no unverified input.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt, label
from skimage.morphology import skeletonize


def skeleton(mask: np.ndarray) -> np.ndarray:
    return skeletonize(np.asarray(mask, bool))


def _neighbour_count(sk: np.ndarray) -> np.ndarray:
    from scipy.ndimage import convolve
    k = np.ones((3, 3), np.uint8)
    k[1, 1] = 0
    return convolve(sk.astype(np.uint8), k, mode="constant") * sk


def local_strike(sk: np.ndarray, sigma: float = 5.0
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Local trace direction at every skeleton pixel.

    Computed as the principal eigenvector of the structure tensor of the
    skeleton mask, i.e. the orientation along which skeleton mass is locally
    concentrated.  This is a fully vectorised, deterministic estimator (the
    earlier per-point KDTree/PCA loop was both slow and unnecessary for a
    1-px-wide input).

    Returns ``(cos, sin)`` in (row, col) = (y, x) index space, which is the
    space the competition metric lives in.
    """
    from scipy.ndimage import gaussian_filter, sobel
    if not sk.any():
        z = np.zeros(sk.shape, np.float64)
        return z, z
    f = sk.astype(np.float64)
    gy = sobel(f, axis=0)
    gx = sobel(f, axis=1)
    jxx = gaussian_filter(gx * gx, sigma)
    jyy = gaussian_filter(gy * gy, sigma)
    jxy = gaussian_filter(gx * gy, sigma)
    # principal direction of [[jxx, jxy], [jxy, jyy]]
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    cos = np.cos(theta)
    sin = np.sin(theta)
    cos[~sk] = 0.0
    sin[~sk] = 0.0
    return cos, sin


def tips(sk: np.ndarray) -> np.ndarray:
    """Skeleton pixels with exactly one skeleton neighbour."""
    return _neighbour_count(sk) == 1


def extrapolate_tips(shape, sk: np.ndarray, cos: np.ndarray, sin: np.ndarray,
                     length: int = 12, step: float = 1.0) -> np.ndarray:
    """Points obtained by walking each tip outward along its local strike."""
    out = np.zeros(shape, bool)
    ty, tx = np.nonzero(tips(sk))
    h, w = shape
    for y0, x0 in zip(ty, tx):
        dy, dx = cos[y0, x0], sin[y0, x0]
        if dy == 0 and dx == 0:
            continue
        for t in np.arange(step, length + step, step):
            y = int(round(y0 + dy * t)); x = int(round(x0 + dx * t))
            if 0 <= y < h and 0 <= x < w:
                out[y, x] = True
            else:
                break
    return out


def bridge_gaps(sk: np.ndarray, max_gap: int = 14, angle_tol_deg: float = 35.0,
                cos: np.ndarray | None = None, sin: np.ndarray | None = None) -> np.ndarray:
    """Straight-line links between tip pairs that are close and near-collinear.

    A gap between two mapped traces that is shorter than ``max_gap`` and whose
    ends point at each other is a linkage zone: exactly the class of "newly
    mapped geometry of an existing fault system" the organizers describe.
    """
    if cos is None or sin is None:
        cos, sin = local_strike(sk)
    out = np.zeros(sk.shape, bool)
    ty, tx = np.nonzero(tips(sk))
    if ty.size < 2:
        return out
    h, w = sk.shape
    from scipy.spatial import cKDTree
    pairs = cKDTree(np.c_[ty, tx]).query_pairs(r=float(max_gap))
    for i, j in pairs:
        dy = ty[j] - ty[i]; dx = tx[j] - tx[i]
        dist = float(np.hypot(dy, dx))
        if dist == 0:
            continue
        if True:
            uy, ux = dy / dist, dx / dist
            # both ends must point roughly at each other
            d1 = cos[ty[i], tx[i]] * uy + sin[ty[i], tx[i]] * ux
            d2 = -(cos[ty[j], tx[j]] * uy + sin[ty[j], tx[j]] * ux)
            ca = np.cos(np.deg2rad(angle_tol_deg))
            if d1 < ca or d2 < ca:
                continue
            n = int(np.ceil(dist))
            for t in np.linspace(0.0, 1.0, n + 1):
                y = int(round(ty[i] + dy * t)); x = int(round(tx[i] + dx * t))
                if 0 <= y < h and 0 <= x < w:
                    out[y, x] = True
    return out


def parallel_strands(cat: np.ndarray, offsets: tuple[int, ...] = (4, 6, 8),
                     min_component: int = 25,
                     sk: np.ndarray | None = None,
                     cos: np.ndarray | None = None,
                     sin: np.ndarray | None = None) -> np.ndarray:
    """Traces offset perpendicular to the catalogue, i.e. candidate splays.

    For every catalogue pixel the local normal is estimated from the skeleton
    orientation and the pixel is replicated at ``+/- offset`` along it.
    Isolated specks are dropped so the result is a set of strands rather than a
    field of noise.
    """
    if sk is None:
        sk = skeleton(cat)
    if cos is None or sin is None:
        cos, sin = local_strike(sk)
    h, w = sk.shape
    out = np.zeros((h, w), bool)
    ys, xs = np.nonzero(sk)
    # normal = (-sin, cos) in (y, x)
    for off in offsets:
        for sgn in (+1, -1):
            y = np.round(ys + sgn * off * (-sin[ys, xs])).astype(int)
            x = np.round(xs + sgn * off * (cos[ys, xs])).astype(int)
            ok = (y >= 0) & (y < h) & (x >= 0) & (x < w)
            out[y[ok], x[ok]] = True
        out &= ~cat
    if min_component > 0:
        lab, n = label(out)
        if n:
            sizes = np.bincount(lab.ravel())
            keep = sizes >= min_component
            keep[0] = False
            out = keep[lab]
    return out


def distance_to(mask: np.ndarray) -> np.ndarray:
    return distance_transform_edt(~np.asarray(mask, bool))


def annulus(mask: np.ndarray, lo: int, hi: int) -> np.ndarray:
    d = distance_to(mask)
    return (d > lo) & (d <= hi)


def dilate(mask: np.ndarray, r: int) -> np.ndarray:
    if r <= 0:
        return np.asarray(mask, bool)
    return binary_dilation(np.asarray(mask, bool), iterations=r)
