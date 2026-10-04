"""Organizer-shaped spatially blocked holdout and the metric-aware emitter.

The instrument
--------------
Scoring in this competition is done against *new* faults, with the known
USGS/INGENIOUS fault pixels masked out of the penalty terms (both quotes are
transcribed in :mod:`gems34.metric` and :mod:`gems34.geology`).  A validation
instrument that is faithful to that statement must therefore:

  1. hold out a spatially blocked subset of the catalogue and call it the
     "new" population;
  2. declare everything *else* in the catalogue (and its 3 px neighbourhood)
     free, exactly as the organizers mask known faults;
  3. charge false positives only outside that free mask.

The instrument is deliberately built from the two verified official rasters
only (``training_features.tif`` and ``labels.tif``); it needs no external data,
so no number produced on it depends on an unverified source.

Its honesty boundary, stated up front: the held-out population is *catalogue*
faults, not the organizers' private new-fault list.  It measures whether an
emission rule finds fault geometry it has not been shown; it cannot prove that
the hidden faults look like catalogue faults.  Every claim that leaves this
repository is labelled accordingly.

The emitter
-----------
With a predicted hidden-fault field ``q`` (probability that a hidden fault pixel
sits at x), the expected kernel credit of putting one unit of mass at x is

    tau(x) = sum_o q(x+o) k(|o|)              (the kernel-smoothed field)

and the expected charge is ``u(x) = 1 - tau(x)`` for a non-free pixel, ``0`` for
a free one.  Substituting into the exact marginal condition
(:func:`gems34.metric.marginal_bar`) collapses to a single, very simple rule:

    free pixels      : emit wherever tau(x) > 0
    non-free pixels  : emit wherever tau(x) > 0.2 * s        (s = current DTI)

Adding mass on the free mask is *weakly dominant*: d(DTI) = tau*(0.8K + 0.2F) /
(D*(D + 0.2*tau)) >= 0 always, so the catalogue carpet can never hurt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import convolve, distance_transform_edt

from . import geology
from .metric import ALPHA, EPS, R_PX, _KERNEL_OFFSETS, kernel, score_fast

# separable-ish kernel stamp for convolution with a predicted field
_K = np.zeros((7, 7), dtype=np.float64)
for _dy, _dx, _kk in _KERNEL_OFFSETS:
    _K[_dy + 3, _dx + 3] = _kk


def smooth(field: np.ndarray) -> np.ndarray:
    """The kernel-smoothed predicted hidden-fault field tau = q (*) k."""
    return convolve(np.asarray(field, np.float32), _K.astype(np.float32),
                    mode="constant")


# ---------------------------------------------------------------------------
# holdout
# ---------------------------------------------------------------------------
@dataclass
class Fold:
    name: str
    truth: np.ndarray
    free: np.ndarray
    blocks: tuple


class Instrument:
    """Spatially blocked, mask-faithful holdout over the catalogue."""

    def __init__(self, labels: np.ndarray, n_blocks: int = 4, buffer_px: int = 3,
                 free_mode: str = "exact"):
        self.cat = np.asarray(labels) == 1
        self.h, self.w = self.cat.shape
        self.n_blocks = n_blocks
        self.buffer_px = buffer_px
        self.free_mode = free_mode
        self.folds: list[Fold] = []
        self._build()

    def _build(self):
        h, w = self.h, self.w
        ys = np.linspace(0, h, self.n_blocks + 1).astype(int)
        xs = np.linspace(0, w, self.n_blocks + 1).astype(int)
        for bi in range(self.n_blocks):
            for bj in range(self.n_blocks):
                blk = np.zeros((h, w), bool)
                blk[ys[bi]:ys[bi + 1], xs[bj]:xs[bj + 1]] = True
                truth = self.cat & blk
                if truth.sum() < 50:
                    continue
                known = self.cat & ~blk
                if self.free_mode == "exact":
                    free = known
                else:
                    free = geology.dilate(known, self.buffer_px)
                self.folds.append(Fold(f"b{bi}{bj}", truth, free, (bi, bj)))

    def score(self, emission: np.ndarray, fold: Fold | None = None) -> dict:
        """Score one emission array against one fold (or the pooled folds)."""
        folds = [fold] if fold is not None else self.folds
        out = []
        for f in folds:
            dt = distance_transform_edt(~f.truth).astype(np.float32)
            r = self.score_against(emission, f.truth, f.free, dt)
            del dt
            out.append(dict(fold=f.name, **r))
        return dict(mean_dti=float(np.mean([o["dti"] for o in out])), folds=out)

    def score_against(self, emission: np.ndarray, truth: np.ndarray,
                      free: np.ndarray, dt: np.ndarray | None = None,
                      fp_weight: np.ndarray | None = None) -> dict:
        """Score one emission against one truth/free pair.

        ``dt`` (distance to the nearest truth pixel) or ``fp_weight`` may be
        precomputed by the caller for fast evaluation.
        """
        p = np.clip(np.where(np.isfinite(emission), emission, 0.0), 0, 1).astype(np.float32)
        gy, gx = np.nonzero(truth)
        best = np.zeros(gy.size, dtype=np.float32)
        for dy, dx, kk in _KERNEL_OFFSETS:
            y = gy + dy; x = gx + dx
            ok = (y >= 0) & (y < self.h) & (x >= 0) & (x < self.w)
            vals = np.zeros(gy.size, dtype=np.float32)
            vals[ok] = p[y[ok], x[ok]] * np.float32(kk)
            np.maximum(best, vals, out=best)
        tp = float(best.sum()); n = int(gy.size)

        if fp_weight is not None:
            p_flat = p.ravel()
            pos = p_flat > 0
            fp = float((p_flat[pos] * fp_weight.ravel()[pos]).sum()) if pos.any() else 0.0
        else:
            if dt is None:
                dt = distance_transform_edt(~np.asarray(truth, bool)).astype(np.float32)
            charged = np.where(free, np.float32(0), p)
            k_dt = np.maximum(np.float32(1.0) - dt / np.float32(3.0), np.float32(0))
            fp = float((charged * (np.float32(1) - k_dt)).sum())
        return dict(dti=tp / (tp + ALPHA * fp + 0.8 * (n - tp) + EPS),
                    tp=tp, fp=fp, fn=n - tp, n_truth=n, emitted=float(p.sum()))

    # -- leakage-free fold geometry ----------------------------------------
    def fold_catalogue(self, f: Fold) -> np.ndarray:
        """The catalogue as the emitter is allowed to see it for fold ``f``."""
        return self.cat & ~_block_of(self.cat.shape, f.blocks, self.n_blocks)

    def fold_free(self, f: Fold) -> np.ndarray:
        """Free mask for fold ``f`` under the configured reading of the rule."""
        known = self.fold_catalogue(f)
        return known if self.free_mode == "exact" else geology.dilate(known, self.buffer_px)


def _block_of(shape, blocks, n_blocks):
    h, w = shape
    ys = np.linspace(0, h, n_blocks + 1).astype(int)
    xs = np.linspace(0, w, n_blocks + 1).astype(int)
    bi, bj = blocks
    m = np.zeros(shape, bool)
    m[ys[bi]:ys[bi + 1], xs[bj]:xs[bj + 1]] = True
    return m


# ---------------------------------------------------------------------------
# emission
# ---------------------------------------------------------------------------
def emission(catalogue: np.ndarray, tau: np.ndarray, bar: float, *,
             use_free: bool = True, spacing: int = 1,
             free_mask: np.ndarray | None = None) -> np.ndarray:
    """Build an emission raster from a smoothed predicted field ``tau``.

    ``catalogue`` marks the known faults: mass is placed on their pixels (free,
    weakly dominant) and, separately, on every non-free pixel whose expected
    kernel credit clears ``bar``.

    ``spacing`` implements greedy packing as a *tiled* arg-max: the grid is cut
    into ``spacing x spacing`` tiles and the highest-``tau`` pixel of each tile is
    emitted if it clears the bar.  That is the vectorised equivalent of the usual
    greedy non-maximum suppression (it guarantees one emission per tile instead
    of suppressing a disk, which is what the metric's 3 px kernel wants) and it
    runs in a single reshape/arg-max rather than a Python loop over candidates.
    ``spacing=1`` disables packing and emits every pixel above the bar.
    """
    cat = np.asarray(catalogue, bool)
    free = cat if free_mask is None else np.asarray(free_mask, bool)
    tau = np.asarray(tau, dtype=np.float32)
    out = np.zeros(cat.shape, np.float32)
    if use_free:
        out[free & (tau > 0)] = 1.0
    cand = (~free) & (tau > bar)
    if not cand.any():
        return out
    if spacing <= 1:
        out[cand] = 1.0
        return out
    h, w = cat.shape
    s = int(spacing)
    ph, pw = (-h) % s, (-w) % s
    tc = np.where(cand, tau, np.float32(0.0))
    if ph or pw:
        tc = np.pad(tc, ((0, ph), (0, pw)), mode="constant")
    H, W = tc.shape
    blocks = tc.reshape(H // s, s, W // s, s).transpose(0, 2, 1, 3).reshape(-1, s * s)
    k = blocks.argmax(axis=1)
    vals = blocks[np.arange(blocks.shape[0]), k]
    keep = vals > bar
    if keep.any():
        rows = (np.nonzero(keep)[0] // (W // s)) * s + (k[keep] // s)
        cols = (np.nonzero(keep)[0] % (W // s)) * s + (k[keep] % s)
        ok = (rows < h) & (cols < w)
        out[rows[ok], cols[ok]] = 1.0
    return out


def coverage_gain(tau: np.ndarray, taken: np.ndarray) -> float:
    """Total expected credit of an emitted set, for reporting."""
    return float(tau[taken].sum())
