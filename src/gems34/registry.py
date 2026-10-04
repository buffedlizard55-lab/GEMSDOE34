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
    path = Path(path)
    raw_bytes = path.read_bytes()
    h_file = hashlib.sha256(raw_bytes).hexdigest()

    a = np.asarray(raster.read(path), dtype=np.float32)
    h_canonical = hashlib.sha256(a.tobytes()).hexdigest()

    fin = np.isfinite(a)
    m = (a > 0) & fin
    h_support = hashlib.sha256(m.astype(np.uint8).tobytes()).hexdigest()

    sample = np.zeros(_N_SAMPLE, dtype=np.float32)
    if a.shape == (raster.GRID["height"], raster.GRID["width"]):
        sample[fin[_YS, _XS]] = a[_YS, _XS][fin[_YS, _XS]]
        density = _block_density(m)
    else:
        density = []
    pos = np.nonzero(m)
    return dict(
        file=str(path),
        sha256_file=h_file,
        sha256_canonical=h_canonical,
        sha256_support=h_support,
        n_positive=int(m.sum()),
        n_finite=int(fin.sum()),
        min=float(a[fin].min()) if fin.any() else None,
        max=float(a[fin].max()) if fin.any() else None,
        is_binary=bool(np.isin(a[fin], (0.0, 1.0)).all()),
        sample=[round(float(v), 6) for v in sample],
        sample_hash=hashlib.sha256(sample.astype("<f4").tobytes()).hexdigest(),
        block_density=density,
        centroid=[float(pos[0].mean()), float(pos[1].mean())] if m.any() else [None, None],
    )


# ---------------------------------------------------------------------------
# comparison statistics
# ---------------------------------------------------------------------------
def _to_arr(x, dtype=None):
    if isinstance(x, np.ndarray):
        return x if dtype is None else x.astype(dtype)
    arr = raster.read(x)
    return arr if dtype is None else arr.astype(dtype)


def raw_correlation(a_path, b_path, footprint_mask=None,
                    a_arr=None, b_arr=None) -> dict:
    """Correlation between two raw surfaces, three different ways."""
    a = a_arr if a_arr is not None else _to_arr(a_path, np.float32)
    b = b_arr if b_arr is not None else _to_arr(b_path, np.float32)
    if footprint_mask is not None:
        a = np.where(footprint_mask, a, np.float32(0.0))
        b = np.where(footprint_mask, b, np.float32(0.0))
    af = np.nan_to_num(a.ravel(), copy=False, nan=0.0, posinf=0.0, neginf=0.0)
    bf = np.nan_to_num(b.ravel(), copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    N = af.size
    sa = float(af.sum(dtype=np.float64))
    sb = float(bf.sum(dtype=np.float64))
    ma = sa / N
    mb = sb / N
    vara = float(np.dot(af, af)) - N * (ma ** 2)
    varb = float(np.dot(bf, bf)) - N * (mb ** 2)

    if vara > 0 and varb > 0:
        dot = float(np.dot(af, bf))
        cov = dot - N * ma * mb
        p_full = cov / np.sqrt(vara * varb)
    else:
        p_full = 1.0 if (vara == 0 and varb == 0) else 0.0

    flat = dict(pearson_full=float(p_full))
    sup = (af > 0) | (bf > 0)
    n_sup = int(sup.sum())
    if n_sup > 8:
        aa = af[sup].astype(np.float64)
        bb = bf[sup].astype(np.float64)
        std_a = float(aa.std())
        std_b = float(bb.std())
        if std_a > 1e-12 and std_b > 1e-12:
            cov_sup = float(np.dot(aa - aa.mean(), bb - bb.mean())) / n_sup
            p_sup = float(cov_sup / (std_a * std_b))
            flat["pearson_support"] = p_sup
            if p_sup >= 0.90:
                is_bin_a = np.isin(aa, (0.0, 1.0)).all()
                is_bin_b = np.isin(bb, (0.0, 1.0)).all()
                if is_bin_a and is_bin_b:
                    flat["spearman_support"] = p_sup
                else:
                    from scipy.stats import rankdata
                    flat["spearman_support"] = float(np.corrcoef(rankdata(aa), rankdata(bb))[0, 1])
            else:
                flat["spearman_support"] = p_sup
        else:
            flat["pearson_support"] = flat["spearman_support"] = float("nan")
    else:
        flat["pearson_support"] = flat["spearman_support"] = float("nan")
    return flat


def final_agreement(a_path, b_path) -> dict:
    """Pixel-agreement statistics between two *final* outputs."""
    a = _to_arr(a_path) > 0
    b = _to_arr(b_path) > 0
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
    a = (_to_arr(a_path) > 0) & ~f
    b = (_to_arr(b_path) > 0) & ~f
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
    """Decide whether a candidate may be allowed to consume a weekly slot."""
    cand = _to_arr(candidate_path)
    fp = fingerprint(cand if isinstance(candidate_path, np.ndarray) else candidate_path)
    rows = []
    worst = dict(raw=1.0, dice=0.0, which=None)
    f_mask = np.asarray(free_mask, bool) if free_mask is not None else None

    # Pre-extract candidate support and payload masks
    cand_fin = np.isfinite(cand)
    cand_bin = (cand > 0) & cand_fin
    cand_payload = cand_bin & ~f_mask if f_mask is not None else cand_bin
    n_cand_bin = int(cand_bin.sum())
    n_cand_payload = int(cand_payload.sum())

    for e in registry:
        row = dict(against=e.get("name"), score=e.get("score"),
                   exact_duplicate=fp["sha256_canonical"] == e.get("sha256_canonical"),
                   support_duplicate=fp["sha256_support"] == e.get("sha256_support"))
        if e.get("_path") and Path(e["_path"]).exists():
            b_pos = e.get("n_positive")
            # If positive counts are known and upper bound on Dice is below 0.80, and not scored:
            # max possible dice = 2 * min(a, b) / (a + b)
            needs_full_check = True
            if b_pos is not None and e.get("score") is None and not (row["exact_duplicate"] or row["support_duplicate"]):
                max_possible_dice = (2.0 * min(n_cand_bin, b_pos) / (n_cand_bin + b_pos)) if (n_cand_bin + b_pos) else 0.0
                if max_possible_dice < 0.75:
                    needs_full_check = False
                    row.update(dict(
                        n_a=n_cand_bin, n_b=b_pos, intersection=0, union=n_cand_bin + b_pos,
                        dice=0.0, jaccard=0.0, containment_a_in_b=0.0, containment_b_in_a=0.0,
                        pearson_full=0.0, pearson_support=0.0, spearman_support=0.0,
                    ))
                    if f_mask is not None:
                        row.update(dict(
                            payload_a=n_cand_payload, payload_b=b_pos, payload_intersection=0,
                            payload_dice=0.0, payload_jaccard=0.0,
                            payload_containment_a_in_b=0.0, payload_containment_b_in_a=0.0,
                        ))

            if needs_full_check:
                b_arr = _to_arr(e["_path"], np.float32)
                if b_arr.shape == cand.shape:
                    b_fin = np.isfinite(b_arr)
                    b_bin = (b_arr > 0) & b_fin
                    n_b_bin = int(b_bin.sum())

                    # final agreement
                    inter = int((cand_bin & b_bin).sum())
                    union = int((cand_bin | b_bin).sum())
                    row.update(dict(
                        n_a=n_cand_bin, n_b=n_b_bin, intersection=inter, union=union,
                        dice=2.0 * inter / (n_cand_bin + n_b_bin) if (n_cand_bin + n_b_bin) else float("nan"),
                        jaccard=inter / union if union else float("nan"),
                        containment_a_in_b=inter / n_cand_bin if n_cand_bin else float("nan"),
                        containment_b_in_a=inter / n_b_bin if n_b_bin else float("nan"),
                    ))

                    # payload agreement
                    if f_mask is not None:
                        b_payload = b_bin & ~f_mask
                        n_b_payload = int(b_payload.sum())
                        p_inter = int((cand_payload & b_payload).sum())
                        p_union = int((cand_payload | b_payload).sum())
                        row.update(dict(
                            payload_a=n_cand_payload, payload_b=n_b_payload,
                            payload_intersection=p_inter,
                            payload_dice=2.0 * p_inter / (n_cand_payload + n_b_payload) if (n_cand_payload + n_b_payload) else float("nan"),
                            payload_jaccard=p_inter / p_union if p_union else float("nan"),
                            payload_containment_a_in_b=p_inter / n_cand_payload if n_cand_payload else float("nan"),
                            payload_containment_b_in_a=p_inter / n_b_payload if n_b_payload else float("nan"),
                        ))

                    # raw correlation (only if non-trivial overlap)
                    if inter > 0:
                        row.update(raw_correlation(None, None, footprint_mask, a_arr=cand, b_arr=b_arr))
                    else:
                        row.update(dict(pearson_full=0.0, pearson_support=0.0, spearman_support=0.0))

        rows.append(row)
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
