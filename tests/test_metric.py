"""Tests for the metric transcription and its decision theory.

The metric is the one part of this repository that must be exactly right: every
emission decision is derived from it.  The published equations, the published
worked example's components and two hand-computed cases are pinned here, and the
fast path is pinned against a literal loop over the published sums.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems34 import metric as M  # noqa: E402


def test_constants_match_the_published_values():
    assert M.ALPHA == 0.2 and M.BETA == 0.8 and M.R_PX == 3.0


def test_kernel_is_triangular_and_clipped():
    d = np.array([0.0, 1.0, 2.0, 3.0, 3.5])
    assert np.allclose(M.kernel(d), [1.0, 2 / 3, 1 / 3, 0.0, 0.0])


def test_published_worked_example_components_reproduce_0_60():
    """The organizers print TP_w=3.00, FP_w=1.89, FN_w=2.00 -> 0.60.

    These are the components, not a raster: the rasters live only in the two
    schematic PNGs on the problem page.  What this test pins is alpha, beta and
    the *shape* of the denominator.
    """
    dti = 3.00 / (3.00 + 0.2 * 1.89 + 0.8 * 2.00)
    assert round(dti, 2) == 0.60


def test_hand_computed_11x11_case():
    """A case worked out by hand from the published sums (see the docstring).

    truth: a 6 px vertical bar at column 4, rows 0-5.
    pred:  its top half (rows 0-2) plus one neighbouring pixel at (3, 3).
    tp = 1 + 1 + 1 + 2/3 + (1 - sqrt(2)/3) + (1 - sqrt(5)/3)
    fp = 1/3   (the one off-axis pixel, 1 px from truth)
    fn = 6 - tp
    """
    truth = np.zeros((11, 11), np.float32)
    truth[0:6, 4] = 1.0
    pred = np.zeros((11, 11), np.float32)
    pred[0:3, 4] = 1.0
    pred[3, 3] = 1.0
    got = M.score_fast(pred, truth)
    assert got["tp"] == pytest.approx(4.449906, abs=1e-6)
    assert got["fp"] == pytest.approx(1 / 3, abs=1e-9)
    assert got["fn"] == pytest.approx(1.550094, abs=1e-6)
    assert got["dti"] == pytest.approx(0.773003, abs=1e-6)


def test_literal_and_fast_agree_on_random_input():
    rng = np.random.default_rng(7)
    for _ in range(4):
        truth = rng.random((28, 28)) > 0.94
        pred = (rng.random((28, 28)) > 0.97).astype(np.float32)
        assert truth.any() and pred.any()
        assert M.score_fast(pred, truth)["dti"] == pytest.approx(
            M.dti_literal(pred, truth)["dti"], abs=1e-9)


def test_mass_on_known_faults_is_free_and_cannot_hurt():
    """The organizers' masking rule, as an executable claim.

    A prediction sitting on a *known* fault pixel contributes no FP_w, and the
    known pixel contributes no FN_w.  Two consequences are asserted: the carpet
    can never lower the score, and it raises it when a new fault lies within
    300 m of a mapped one.
    """
    known = np.zeros((40, 40), bool)
    known[10:30, 20] = True
    empty = np.zeros((40, 40), np.float32)
    carpet = np.zeros((40, 40), np.float32)
    carpet[known] = 1.0

    far = np.zeros((40, 40), bool)
    far[2:7, 20] = True        # a *new* fault whose nearest pixel is 4 px away
    a = M.score_fast(carpet, far, free=known)
    b = M.score_fast(empty, far, free=known)
    assert a["fp"] == pytest.approx(b["fp"]) == 0.0
    assert a["tp"] == pytest.approx(0.0)
    assert a["dti"] == pytest.approx(b["dti"]) == 0.0

    near = np.zeros((40, 40), bool)            # a *new* fault hugging the mask
    near[10:16, 21] = True                     # exactly 1 px from the mask
    c = M.score_fast(carpet, near, free=known)
    d = M.score_fast(empty, near, free=known)
    assert d["tp"] == 0.0
    assert c["tp"] == pytest.approx(6 * (2 / 3))     # k(1) = 1 - 1/3
    assert c["fp"] == pytest.approx(0.0)
    assert c["dti"] > d["dti"]


def test_marginal_bar_is_the_true_break_even():
    """`marginal_bar` must predict the *sign* of a brute-force perturbation.

    The rule is exact for the realised, marginal credit `dT` and charge `u` of
    the added pixel:  d(DTI) > 0  <=>  dT > marginal_bar(s, u).  The test
    computes dT and u by differencing the metric, so it cannot pass by
    re-deriving the same algebra.
    """
    rng = np.random.default_rng(11)
    truth = rng.random((80, 80)) > 0.985
    base = np.zeros((80, 80), np.float32)
    ys, xs = np.nonzero(rng.random((80, 80)) > 0.997)
    base[ys, xs] = 1.0
    s0 = M.score_fast(base, truth)["dti"]

    from scipy.ndimage import distance_transform_edt
    dg = distance_transform_edt(~truth)
    checked = 0
    for y, x in zip(*np.nonzero((dg > 0.2) & (dg < 3.0) & (base == 0))):
        if checked >= 6:
            break
        trial = base.copy()
        trial[y, x] = 1.0
        got = M.score_fast(trial, truth)
        dT = got["tp"] - M.score_fast(base, truth)["tp"]
        u = 1.0 - float(M.kernel(dg[y, x]))
        predicted_improves = dT > M.marginal_bar(s0, u=u)
        assert predicted_improves == (got["dti"] > s0), (dT, u, s0, got["dti"])
        checked += 1
    assert checked >= 4


def test_marginal_bar_is_zero_for_free_mass():
    assert M.marginal_bar(0.28, u=0.0) == 0.0
    assert M.marginal_bar(0.0, u=1.0) == 0.0
    # the beta correction: the naive alpha*s/(1-alpha*s) is strictly larger
    s = 0.28
    naive = M.ALPHA * s / (1 - M.ALPHA * s)
    assert M.marginal_bar(s) < naive
    assert M.marginal_bar(s) == pytest.approx(0.047946, abs=1e-6)


def test_required_coverage_inverts_the_metric():
    for s in (0.05, 0.2, 0.35):
        for rho in (0.0, 1.0, 4.0):
            t = M.required_coverage(s, rho)
            dti = t / (M.ALPHA * (t + rho) + M.BETA * (1.0 - t))
            assert dti == pytest.approx(s, abs=1e-12)


def test_dti_range_and_empty_cases():
    truth = np.zeros((20, 20), bool)
    truth[5, 5] = True
    assert M.score_fast(np.zeros((20, 20), np.float32), truth)["dti"] == 0.0
    assert M.score_fast(truth.astype(np.float32), truth)["dti"] == pytest.approx(1.0, abs=1e-6)
