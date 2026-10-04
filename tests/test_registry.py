"""Tests for the fingerprint, the payload comparison and the pre-submission gate."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems34 import raster, registry  # noqa: E402

H, W = raster.GRID["height"], raster.GRID["width"]


def _carpet_plus(payload_px: int, seed: int, free=None):
    v = np.zeros((H, W), np.float32)
    v[free] = 1.0
    rng = np.random.default_rng(seed)
    cy, cx = rng.integers(500, H - 500, payload_px), rng.integers(500, W - 500, payload_px)
    v[cy, cx] = 1.0
    return v


@pytest.fixture(scope="module")
def stage(tmp_path_factory):
    d = tmp_path_factory.mktemp("reg")
    free = np.zeros((H, W), bool)
    free[1000:1050, 1000:1040] = True          # a toy "known fault mask" (2000 px)
    a = d / "a.tif"
    b = d / "b.tif"
    c = d / "c.tif"
    raster.write_submission(a, _carpet_plus(50, 1, free), outside="zero")
    raster.write_submission(b, _carpet_plus(50, 2, free), outside="zero")   # different payload
    raster.write_submission(c, raster.read(a), outside="zero")              # same content, new file
    same = registry.fingerprint(a)["sha256_canonical"]
    return dict(a=a, b=b, c=c, free=free, d=d, sha_a=same)


def test_fingerprint_is_deterministic_and_content_addressed(stage):
    f1 = registry.fingerprint(stage["a"])
    f2 = registry.fingerprint(stage["a"])
    assert f1["sha256_canonical"] == f2["sha256_canonical"] == stage["sha_a"]
    assert f1["n_positive"] == 50 + 2000 and f1["is_binary"] is True
    assert f1["sha256_support"] and f1["sample_hash"]


def test_identical_content_in_two_files_shares_the_canonical_hash(stage):
    assert (registry.fingerprint(stage["c"])["sha256_canonical"]
            == registry.fingerprint(stage["a"])["sha256_canonical"])


def test_payload_agreement_separates_carpet_from_payload(stage):
    """Two files sharing a whole free carpet are still different payloads."""
    whole = registry.final_agreement(stage["a"], stage["b"])
    payload = registry.payload_agreement(stage["a"], stage["b"], stage["free"])
    assert whole["dice"] > 0.9                 # nearly the same file by support
    assert payload["payload_dice"] == 0.0      # and completely different hypotheses
    assert payload["payload_a"] == payload["payload_b"] == 50


def test_payload_agreement_detects_a_duplicated_payload(stage):
    p = registry.payload_agreement(stage["a"], stage["c"], stage["free"])
    assert p["payload_dice"] == pytest.approx(1.0)


def test_gate_refuses_an_exact_duplicate_and_allows_a_new_payload(stage):
    entries = [dict(name="a.tif", _path=str(stage["a"]), score=0.1,
                    **{k: v for k, v in registry.fingerprint(stage["a"]).items()
                       if k in ("sha256_canonical", "sha256_support")})]
    refused = registry.gate(stage["c"], entries, free_mask=stage["free"])
    allowed = registry.gate(stage["b"], entries, free_mask=stage["free"])
    assert refused["duplicates"] == ["a.tif"] and refused["allowed"] is False
    assert allowed["allowed"] is True
    assert allowed["near_duplicate_payload"] == []
    assert allowed["payload_gate_used"] is True


def test_gate_rules_document_the_payload_criterion():
    assert "near_duplicate_payload" in registry.GATE_RULES
    assert registry.GATE_RULES["near_duplicate_payload"].startswith("Dice of *non-free* supports")
