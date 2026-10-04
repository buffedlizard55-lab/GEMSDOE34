"""Submission registry, uniqueness fingerprints and the pre-submission gate.

Motivation (project brief)
--------------------------
Three earlier submissions from this group were reported at *identical* scores:

    GEMSDOE    gems-submission-20260925T001403Z-7f00890a   0.1563
    5GEMSDOE   gems-submission-20260926T175114Z-7f00890a   0.1563
    8GEMSDOE   Hedge-v2_submission                          0.1563

A four-decimal coincidence across three supposedly independent attempts is a
testable claim, not a curiosity.  The mandated test is:

    correlate the *raw* (pre-postprocessing) probability surface of a candidate
    against every prior submission's raw surface -- and, separately, measure the
    pixel-agreement rate between their *final* thresholded outputs.

    low raw correlation  + near-100 % final agreement  => the collapse happened
                                                          in post-processing /
                                                          placement (fix there)
    high raw correlation                               => it was never a
                                                          different hypothesis

This module implements that gate so that no future weekly slot is spent on a
near-duplicate.  ``fingerprint`` is deliberately cheap (hash + fixed-sample +
block-density) so the registry stays small enough to commit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from . import raster

# 8192 fixed sample sites drawn once, deterministically, over the whole grid.
_N_SAMPLE = 8192
_BLOCK = 32          # 3292x3730 -> 103 x 117 block-density grid

_fp = np.random.RandomState(3400)
_YS = _fp.randint(0, raster.GRID["height"], _N_SAMPLE)
_XS = _fp.randint(0, raster.GRID["width"], _N_SAMPLE)


def _block_density(mask: np.ndarray) -> list[float]:
    h, w = mask.shape
    out = []
    for y in range(0, h, _BLOCK):
        for x in range(0, w, _BLOCK):
            blk = mask[y:y + _BLOCK, x:x + _BLOCK]
            if blk.size:
                out.append(round(float(blk.mean()), 6))
    return out


def fingerprint(path) -> dict:
    """Compact, committable fingerprint of one submission raster."""
    a = np.asarray(raster.read(path), dtype=np.float32)
    fin = np.isfinite(a)
    m = (a > 0) & fin
    sample = np.zeros(_N_SAMPLE, dtype=np.float32)
    sample[fin[_YS, _XS]] = a[_YS, _XS][fin[_YS, _XS]]
    pos = np.nonzero(m)
    return dict(
        file=str(path),
        sha256_file=raster.sha256_file(path),
        sha256_canonical=raster.sha256_canonical(path),
        sha256_support=raster.sha256_mask(path),
        n_positive=int(m.sum()),
        n_finite=int(fin.sum()),
        min=float(a[fin].min()), max=float(a[fin].max()),
        is_binary=bool(np.isin(a[fin], (0.0, 1.0)).all()),
        sample=[round(float(v), 6) for v in sample],
        sample_hash=hashlib.sha256(sample.astype("<f4").tobytes()).hexdigest(),
        block_density=_block_density(m),
        centroid=[float(pos[0].mean()), float(pos[1].mean())] if m.any() else [None, None],
    )


# ---------------------------------------------------------------------------
# comparison statistics
# ---------------------------------------------------------------------------
def raw_correlation(a_path, b_path, footprint_mask=None) -> dict:
    """Correlation between two raw surfaces, three different ways.

    whole-footprint Pearson is reported but is dominated by the shared field of
    exact zeros; the support-restricted statistics are the ones that answer the
    question "were these the same hypothesis?".
    """
    a = np.asarray(raster.read(a_path), dtype=np.float64)
    b = np.asarray(raster.read(b_path), dtype=np.float64)
    a[~np.isfinite(a)] = 0.0
    b[~np.isfinite(b)] = 0.0
    if footprint_mask is not None:
        a = np.where(footprint_mask, a, 0.0)
        b = np.where(footprint_mask, b, 0.0)
    a = a.ravel(); b = b.ravel()
    flat = dict(pearson_full=float(np.corrcoef(a, b)[0, 1]))
    sup = (a > 0) | (b > 0)
    if sup.sum() > 8:
        aa, bb = a[sup], b[sup]
        if aa.std() > 0 and bb.std() > 0:
            flat["pearson_support"] = float(np.corrcoef(aa, bb)[0, 1])
            ra = np.argsort(np.argsort(aa)).astype(np.float64)
            rb = np.argsort(np.argsort(bb)).astype(np.float64)
            flat["spearman_support"] = float(np.corrcoef(ra, rb)[0, 1])
        else:
            flat["pearson_support"] = flat["spearman_support"] = float("nan")
    else:
        flat["pearson_support"] = flat["spearman_support"] = float("nan")
    return flat


def final_agreement(a_path, b_path) -> dict:
    """Pixel-agreement statistics between two *final* outputs."""
    a = np.asarray(raster.read(a_path)) > 0
    b = np.asarray(raster.read(b_path)) > 0
    inter = int((a & b).sum()); ua = int(a.sum()); ub = int(b.sum())
    union = int((a | b).sum())
    return dict(
        n_a=ua, n_b=ub, intersection=inter, union=union,
        dice=2.0 * inter / (ua + ub) if (ua + ub) else float("nan"),
        jaccard=inter / union if union else float("nan"),
        containment_a_in_b=inter / ua if ua else float("nan"),
        containment_b_in_a=inter / ub if ub else float("nan"),
    )


def payload_agreement(a_path, b_path, free) -> dict:
    """Agreement between the **payloads**: the part of the support that is not free.

    This is the statistic that answers the question the 0.1563 collapse raised.
    Under the organizers' masking rule a prediction on a known-fault pixel is
    never charged to FP_w, so free-mask mass is metrically inert: two candidates
    that differ only there are the *same* submission whatever their upstream
    hypotheses were.  Whole-file Dice therefore cannot detect a duplicated
    hypothesis, while ``payload_dice`` -- the Dice of the non-free supports --
    can.
    """
    f = np.asarray(free, bool)
    a = (np.asarray(raster.read(a_path)) > 0) & ~f
    b = (np.asarray(raster.read(b_path)) > 0) & ~f
    inter = int((a & b).sum()); ua = int(a.sum()); ub = int(b.sum())
    union = int((a | b).sum())
    return dict(
        payload_a=ua, payload_b=ub, payload_intersection=inter,
        payload_dice=2.0 * inter / (ua + ub) if (ua + ub) else float("nan"),
        payload_jaccard=inter / union if union else float("nan"),
        payload_containment_a_in_b=inter / ua if ua else float("nan"),
        payload_containment_b_in_a=inter / ub if ub else float("nan"),
    )


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------
GATE_RULES = {
    "exact_duplicate": "sha256_canonical equals a registry entry",
    "support_duplicate": "sha256_support equals a registry entry",
    "near_duplicate_raw": "support-restricted Pearson >= 0.98 vs any entry",
    "near_duplicate_final": "Dice of final supports >= 0.95 vs any entry",
    "near_duplicate_payload": (
        "Dice of *non-free* supports >= 0.95 vs any entry -- the criterion that "
        "actually detects a duplicated hypothesis, because free-mask mass cannot "
        "change a score (see docs/data/collapse-diagnosis.json)"),
}


def gate(candidate_path, registry: list[dict], footprint_mask=None,
         free_mask=None) -> dict:
    """Decide whether a candidate may be allowed to consume a weekly slot.

    Returns ``allowed`` plus the full evidence table.  ``allowed`` is False for
    any exact duplicate, and for any candidate that is a near-duplicate of a
    previously *scored* artifact under either the raw-surface or the final-mask
    criterion.  A near-duplicate is not automatically worthless -- it is simply
    not a *new hypothesis*, and the brief requires that a slot be spent on a new
    hypothesis.
    """
    fp = fingerprint(candidate_path)
    rows = []
    worst = dict(raw=1.0, dice=0.0, which=None)
    for e in registry:
        row = dict(against=e.get("name"), score=e.get("score"),
                   exact_duplicate=fp["sha256_canonical"] == e.get("sha256_canonical"),
                   support_duplicate=fp["sha256_support"] == e.get("sha256_support"))
        if e.get("_path"):
            row.update(raw_correlation(candidate_path, e["_path"], footprint_mask))
            row.update(final_agreement(candidate_path, e["_path"]))
            if free_mask is not None:
                row.update(payload_agreement(candidate_path, e["_path"], free_mask))
        rows.append(row)
        if not np.isnan(row.get("pearson_support", float("nan"))):
            if row["pearson_support"] < worst["raw"] or row["pearson_support"] >= 0.98:
                pass
        if row.get("dice", 0.0) > worst["dice"]:
            worst = dict(raw=row.get("pearson_support"), dice=row["dice"], which=e.get("name"))
    dup = [r["against"] for r in rows if r["exact_duplicate"] or r["support_duplicate"]]
    near_raw = [r["against"] for r in rows
                if r.get("pearson_support") is not None
                and np.isfinite(r.get("pearson_support", float("nan")))
                and r["pearson_support"] >= 0.98]
    near_final = [r["against"] for r in rows
                  if np.isfinite(r.get("dice", float("nan"))) and r["dice"] >= 0.95]
    near_payload = [r["against"] for r in rows
                    if np.isfinite(r.get("payload_dice", float("nan")))
                    and r["payload_dice"] >= 0.95]
    # When the free mask is known, the whole-support Dice rule must NOT block a
    # candidate: a shared free carpet pushes whole-file Dice above 0.95 for two
    # completely different payloads (measured: two candidates sharing a 2,000 px
    # carpet and holding disjoint 50 px payloads reach Dice 0.976).  That false
    # positive is precisely how three different upstream hypotheses ended up as
    # the same submission, so the payload rule replaces it.
    payload_gate_used = free_mask is not None
    blocking_final = [] if payload_gate_used else near_final
    return dict(
        candidate=str(candidate_path), fingerprint={k: v for k, v in fp.items()
                                                    if k not in ("sample", "block_density")},
        rows=rows, duplicates=dup, near_duplicate_raw=near_raw,
        near_duplicate_final=near_final, near_duplicate_payload=near_payload,
        payload_gate_used=payload_gate_used,
        final_rule_superseded_by_payload=payload_gate_used,
        blocking_rules=[name for name, hit in (
            ("exact/support_duplicate", dup),
            ("near_duplicate_raw", near_raw),
            ("near_duplicate_final", blocking_final),
            ("near_duplicate_payload", near_payload)) if hit],
        max_dice_vs_history=worst["dice"], max_dice_against=worst["which"],
        allowed=not (dup or near_raw or blocking_final or near_payload),
        rules=GATE_RULES,
    )


def load_registry(path) -> list[dict]:
    return json.loads(Path(path).read_text())["entries"]


def save_registry(entries: list[dict], path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(
        {"generated_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
         "n_entries": len(entries), "entries": entries}, indent=2) + "\n")
