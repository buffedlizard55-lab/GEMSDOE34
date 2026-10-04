"""Candidate predictors of the hidden ("not yet mapped") fault population.

Each generator returns a float field in [0, 1] on the competition grid that is
read as ``q(x) = P(a hidden fault pixel sits at x)``.  The emitter then scores
``tau = q (*) k`` and applies the decision rule derived in :mod:`gems34.holdout`.

The generators are grouped by the geological hypothesis they encode; the
hypothesis register in the repository README names the layer set, the physical
signature and the reason each one should catch faults that are *not* in the
USGS/INGENIOUS catalogue.

All generators are functions of the two verified official rasters only
(``labels.tif`` -> catalogue, ``training_features.tif`` -> the 19 published
layers).  No external dataset is required, so nothing here rests on an
unverified source; where an external source *would* help, the repository says so
explicitly rather than quietly substituting a proxy.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, sobel

from . import geology

BAND = {
    "mag_anom": 0, "rtp": 1, "tmi_hg": 2, "geod_2ndinv": 3,
    "iso_grav_anom_slope": 4, "tc": 5, "geod_shearrate": 6, "geod_dilaterate": 7,
    "tmi_vg": 8, "deq_n100a15": 9, "iso_grav_anom_vg": 10, "det_elev": 11,
    "iso_grav_anom": 12, "tmi": 13, "depth_to_base_surf": 14, "ieq_n100a15": 15,
    "cond_surf": 16, "iso_grav_anom_hg": 17, "det_elev_slope": 18,
}


def _norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, np.float32)
    sample = x[::8, ::8].ravel()
    sample = sample[np.isfinite(sample)]
    if sample.size > 0:
        lo, hi = float(np.percentile(sample, 1)), float(np.percentile(sample, 99))
    else:
        lo, hi = 0.0, 1.0
    if hi <= lo + 1e-7:
        return np.zeros_like(x)
    out = np.clip((x - np.float32(lo)) / np.float32(hi - lo), 0.0, 1.0)
    out[~np.isfinite(out)] = 0.0
    return out.astype(np.float32)


def _fill(x: np.ndarray) -> np.ndarray:
    return np.nan_to_num(np.asarray(x, np.float32), nan=0.0, posinf=0.0, neginf=0.0)


# ---------------------------------------------------------------------------
# H1  near-catalogue geometry (the organizers' own definition of the target)
# ---------------------------------------------------------------------------
def h1_near_catalogue(cat: np.ndarray, sigma_px: float = 6.0) -> np.ndarray:
    """P(hidden geometry close to mapped geometry).

    Mechanism: the organizers define a new fault as including "newly mapped
    geometry of an existing fault system", so the hidden population is
    concentrated within a few pixels of the mapped traces (splays, parallel
    strands, continuations).  The field is a distance-decayed shell around the
    catalogue, deliberately *not* including the catalogue pixels themselves
    (those are free mass and are added separately by the emitter).
    """
    d = geology.distance_to(cat).astype(np.float32)
    q = np.exp(-(d / np.float32(sigma_px)) ** 2).astype(np.float32)
    q[cat] = 0.0
    return q


# ---------------------------------------------------------------------------
# H2  strike extrapolation of fault tips
# ---------------------------------------------------------------------------
def h2_tip_extrapolation(cat: np.ndarray, length: int = 14,
                         sigma_px: float = 2.0) -> np.ndarray:
    """P(a mapped trace continues beyond its mapped tip).

    Mechanism: catalogue compilation stops where a mapper stopped, not where the
    structure stops.  A fault tip in the catalogue is the single most likely
    place for unmapped continuation, and continuation is explicitly inside the
    organizers' definition of a new fault.
    """
    sk = geology.skeleton(cat)
    cos, sin = geology.local_strike(sk)
    ext = geology.extrapolate_tips(cat.shape, sk, cos, sin, length=length)
    ext &= ~cat
    return gaussian_filter(ext.astype(np.float32), sigma_px)


# ---------------------------------------------------------------------------
# H3  linkage / relay zones between near-collinear tips
# ---------------------------------------------------------------------------
def h3_gap_linkage(cat: np.ndarray, max_gap: int = 16,
                   sigma_px: float = 2.0) -> np.ndarray:
    """P(a gap between two near-collinear mapped traces is bridged).

    Mechanism: relay ramps and step-overs are systematically simplified out of
    regional compilations; the linking fault between two overlapping strands is
    real geology that the compilation omits.
    """
    sk = geology.skeleton(cat)
    br = geology.bridge_gaps(sk, max_gap=max_gap)
    br &= ~cat
    return gaussian_filter(br.astype(np.float32), sigma_px)


# ---------------------------------------------------------------------------
# H4  parallel strands / splays
# ---------------------------------------------------------------------------
def h4_parallel_strands(cat: np.ndarray, offsets=(4, 6, 9),
                        sigma_px: float = 2.0,
                        sk: np.ndarray | None = None,
                        cos: np.ndarray | None = None,
                        sin: np.ndarray | None = None) -> np.ndarray:
    """P(a splay or parallel strand runs beside a mapped trace).

    Mechanism: Basin-and-Range normal-fault zones are arrays of sub-parallel
    strands; compilations typically carry the dominant trace only.
    """
    st = geology.parallel_strands(cat, offsets=offsets, sk=sk, cos=cos, sin=sin)
    st &= ~cat
    return gaussian_filter(st.astype(np.float32), sigma_px)


# ---------------------------------------------------------------------------
# H5  geophysical lineament saliency (unsupervised, no catalogue training)
# ---------------------------------------------------------------------------
def _lineament(gray: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """Structure-tensor lineament energy: |lambda1 - lambda2| of the smoothed
    gradient outer product -- i.e. ridge/edge anisotropy, complement-invariant
    to bright-vs-dark contrast (a fault is an edge but a scarp is a ridge).
    """
    g = _norm(gray)
    gy = sobel(g, axis=0); gx = sobel(g, axis=1)
    jxx = gaussian_filter(gx * gx, sigma)
    jyy = gaussian_filter(gy * gy, sigma)
    jxy = gaussian_filter(gx * gy, sigma)
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    return _norm((l1 - l2).astype(np.float32))


def h5_geophysical_lineaments(feats: dict[str, np.ndarray],
                              weights: dict[str, float] | None = None,
                              sigma: float = 2.0) -> np.ndarray:
    """P(a geophysical lineament is a fault not carried by the catalogue).

    Mechanism: magnetic tilt/vertical gradients, isostatic-gravity horizontal
    gradient, detrended-elevation curvature and the geodetic strain-rate
    invariants all localise structure at depth, including beneath basin fill
    where no surface scarp exists.  Combining independent physical channels by
    multi-scale lineament energy suppresses single-channel artefacts.
    """
    if weights is None:
        weights = {"tc": 1.0, "tmi_hg": 0.8, "iso_grav_anom_hg": 0.8,
                   "iso_grav_anom_vg": 0.6, "tmi_vg": 0.6,
                   "geod_2ndinv": 0.7, "geod_shearrate": 0.5,
                   "geod_dilaterate": 0.5, "det_elev": 0.5,
                   "cond_surf": 0.4}
    acc = None
    for k, w in weights.items():
        if k not in feats:
            continue
        e = _lineament(feats[k], sigma)
        acc = w * e if acc is None else acc + w * e
    if acc is None:
        raise KeyError("no usable bands")
    return _norm(acc)


def mask_to_zero_outside(field: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    f = np.array(field, copy=True)
    f[~footprint] = 0.0
    return f


# ---------------------------------------------------------------------------
# composites
# ---------------------------------------------------------------------------
def composite(*fields_and_weights) -> np.ndarray:
    acc = None
    for f, w in fields_and_weights:
        acc = w * _norm(f) if acc is None else acc + w * _norm(f)
    return _norm(acc) if acc is not None else None
