"""Diagnose the 0.1563 coincidence: same hypothesis, or collapsed post-processing?

Writes ``docs/data/collapse-diagnosis.json`` and a human-readable markdown
report.  Run:  python scripts/run_collapse_diagnosis.py --corpus DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems34 import raster, registry  # noqa: E402

# Score ledger.  Every row is either an official leaderboard snapshot (fetched
# by this session, URL recorded) or a group claim.  Nothing here is invented.
CLAIMS = [
    ("gemsdoe1-ens12-7f00890a.tif", 0.1563, "claim", "GEMSDOE   (2026-09-25)"),
    ("gemsdoe-ens12-adopted-7f00890a.tif", 0.1563, "claim", "5GEMSDOE  (2026-09-26)"),
    ("8GEMSDOE_Hedge-v2_submission.tif", 0.1563, "claim", "8GEMSDOE  Hedge-v2"),
    ("8GEMSDOE-Apex-Geothermal-V1.tif", None, "unscored", "8GEMSDOE  Apex V1"),
    ("gemsdoe2-dual-family-union-f68e590f.tif", 0.1560, "claim", "GEMSDOE2  dual-family union"),
    ("gemsdoe2-extension-arm-ad5ba911.tif", None, "unscored", "GEMSDOE2  extension arm"),
    ("gemsdoe2-precision-arm-8bce5dfe.tif", None, "unscored", "GEMSDOE2  precision arm"),
    ("gemsdoe2-recall-union-v1.tif", None, "unscored", "GEMSDOE2  recall-union v1"),
    ("gemsdoe1-ens12-floor0.1.tif", None, "unscored", "GEMSDOE   ens12 floor0.1"),
    ("gemsdoe3-pindrop-nodes-f347b70daa.tif", 0.1193, "claim", "GEMSDOE3  pindrop nodes"),
    ("gemsdoe3-pindrop-discovery-37f9d5b855.tif", 0.0830, "claim", "GEMSDOE3  pindrop discovery"),
    ("gemsdoe3-pindrop-ridge-4e03fc9705.tif", 0.1152, "claim", "GEMSDOE3  pindrop ridge"),
    ("gemsdoe3-sgmc-gap-7251c22bb4.tif", None, "unscored", "GEMSDOE3  sgmc gap"),
    ("gemsdoe4-combined-237f0063.tif", 0.0343, "claim", "GEMSDOE4  combined"),
    ("gems6-hgb88-topk03-33cec71ff0.tif", 0.0286, "claim", "6GEMSDOE  hgb88 top-3%"),
    ("gemsdoe31-h27-4-solo-d28-20261004-8acb75e1-nan.tif", 0.2708, "claim",
     "GEMSDOE31 h27-4 solo d28 (= official lb 0.2708 row, attribution unverified)"),
    ("gemsdoe31-h27-4-solo-d28-20261004-8acb75e1-allfinite.tif", None, "unscored",
     "GEMSDOE31 same pixels, all-finite twin"),
    ("gemsdoe31-add-arm-d28-20261004-8acb75e1-nan.tif", None, "unscored", "GEMSDOE31 add-arm"),
    ("gemsdoe31-union-b-p060-20261004-8acb75e1-nan.tif", None, "unscored", "GEMSDOE31 union-b"),
    ("gemsdoe31-reference-d28-offcat-44090-20261004-nan.tif", None, "unscored",
     "GEMSDOE31 d2.8 off-catalogue reference"),
    ("gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif", 0.2600, "claim",
     "GEMSDOE25 dotted h19-5 d2.8"),
    ("gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif", None, "unscored",
     "GEMSDOE25 all-finite twin"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, help="directory of historical TIFs")
    ap.add_argument("--out", default="docs/data")
    ap.add_argument("--labels", default="/tmp/work/data/labels.tif")
    args = ap.parse_args()

    corpus = Path(args.corpus)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    names = {p.name for p in corpus.glob("*.tif")}
    entries, missing = [], []
    for fname, score, cls, note in CLAIMS:
        if fname not in names:
            missing.append(fname)
            continue
        p = corpus / fname
        fp = registry.fingerprint(p)
        e = dict(name=fname, label=note, score=score, evidence_class=cls, _path=str(p))
        e.update({k: v for k, v in fp.items() if k in
                  ("sha256_file", "sha256_canonical", "sha256_support", "n_positive",
                   "n_finite", "min", "max", "is_binary")})
        entries.append(e)

    # ---------- 1. are the three 0.1563 artifacts the same bytes? ----------
    trio = [e for e in entries if e["score"] == 0.1563]
    trio_canon = {e["sha256_canonical"] for e in trio}
    trio_support = {e["sha256_support"] for e in trio}
    identical_files = len(trio_canon) == 1
    identical_support = len(trio_support) == 1

    # ---------- 2. pairwise raw-surface and final-mask comparison ----------
    pairs = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i], entries[j]
            raw = registry.raw_correlation(a["_path"], b["_path"])
            fin = registry.final_agreement(a["_path"], b["_path"])
            pairs.append(dict(a=a["name"], b=b["name"], score_a=a["score"],
                              score_b=b["score"], **raw, **fin))

    # ---------- 3. where do the extra pixels go? (the mechanism) ----------
    fm = free_mask_analysis([e["_path"] for e in entries], args.labels, pairs)

    # ---------- 4. verdict ----------
    verdict = classify(entries, trio, identical_files, identical_support, pairs)
    if any(r["payload_identical"] and r["added_on_mask_pct"] >= 99.0 for r in fm["pairs"]):
        verdict = dict(
            mechanism="FREE-MASK SATURATION (metrically inert additions)",
            collapses_in_postprocessing=True,
            detail=("At least one pair of artifacts has an identical *non-mask payload*: the "
                    "larger file is the smaller file plus pixels that all lie on the known-fault "
                    "mask. Under the organizers' masking rule that extra mass is inert, so the "
                    "two artifacts are the same submission under evaluation -- which is exactly "
                    "what the equal score shows. Additions that were *not* inside the mask did "
                    "move the score, which is the control that pins the mechanism."),
            evidence=("measured: containment 100 %, added pixels 100 % on the free mask, "
                      "non-mask payload sets byte-identical"),
            action=("Gate on the non-free payload: src/gems34/registry.py "
                    "`gate(..., free_mask=...)`, driven by scripts/run_gate.py. Never let the "
                    "placement step dump the remainder onto the mask, and never spend a slot on "
                    "a candidate whose payload is unchanged."))
    report = dict(
        corpus=str(corpus), n_entries=len(entries), missing=missing,
        trio_identical_bytes=identical_files, trio_identical_support=identical_support,
        trio=[{k: v for k, v in e.items() if not k.startswith("_")} for e in trio],
        free_mask=fm, pairs=pairs, verdict=verdict,
    )
    (out / "collapse-diagnosis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "pairs"}, indent=2))
    print(f"\nwrote {out/'collapse-diagnosis.json'}  ({len(pairs)} pairs)")
    return 0


def free_mask_analysis(paths, labels_path, pairs) -> dict:
    """Measure the mechanism the brief asked about: where do the extra pixels go?

    The organizers mask known USGS/INGENIOUS faults out of the penalty terms, so
    a prediction on a known-fault pixel is metrically inert: it is not charged to
    FP_w, and (per "it should not matter whether these known faults are included
    with predictions or not") it cannot be counted on to earn TP_w either.
    Therefore two artifacts whose non-mask payloads are identical are the *same
    submission* under evaluation, whatever their upstream hypotheses were.

    This routine finds every containment pair in the corpus, and for the added
    pixels reports how many lie on the mask, how many are charged, and how far
    the added pixels sit from the catalogue.  The scores next to it are the
    user-reported claims -- this measurement is about geometry, not about score.
    """
    from gems34 import geology, raster as _raster
    cat = _raster.read(labels_path) == 1
    dcat = geology.distance_to(cat).astype("float32")
    S = {p: (_raster.read(p) > 0) for p in paths}
    rows = []
    for p in pairs:
        a = next((q for q in paths if q.endswith(p["a"])), None)
        b = next((q for q in paths if q.endswith(p["b"])), None)
        if a is None or b is None:
            continue
        A, B = S[a], S[b]
        if p.get("containment_a_in_b", 0.0) >= 0.999 and int(A.sum()) < int(B.sum()):
            lo, hi = a, b
        elif p.get("containment_b_in_a", 0.0) >= 0.999 and int(B.sum()) < int(A.sum()):
            lo, hi = b, a
        else:
            continue
        added = S[hi] & ~S[lo]
        n = int(added.sum())
        if n == 0:
            continue
        on = int((added & cat).sum())
        d = dcat[added]
        rows.append(dict(
            smaller=lo.split("/")[-1], larger=hi.split("/")[-1], added_px=n,
            added_on_mask=on, added_on_mask_pct=round(100.0 * on / n, 2),
            added_charged=n - on, spared_fp_charge=round(0.2 * (n - on), 1),
            median_dcat_added=round(float(np.median(d)), 2),
            pct_added_within_300m=round(100.0 * float((d <= 3).mean()), 2),
            payload_smaller=int((S[lo] & ~cat).sum()),
            payload_larger=int((S[hi] & ~cat).sum()),
            payload_identical=bool(((S[hi] & ~cat) == (S[lo] & ~cat)).all()),
            score_smaller=p.get("score_a"), score_larger=p.get("score_b")))
    return dict(labels=str(labels_path), pairs=rows)


def classify(entries, trio, identical_files, identical_support, pairs) -> dict:
    """Apply the brief's decision rule to the three 0.1563 artifacts."""
    if len(trio) < 2:
        return dict(mechanism="INSUFFICIENT EVIDENCE",
                    detail="fewer than two of the 0.1563 artifacts were available")
    if identical_files:
        return dict(
            mechanism="LITERAL FILE REUSE (byte-identical artifacts)",
            collapses_in_postprocessing=False,
            detail=("All artifacts reporting 0.1563 have the same canonical float32 "
                    "payload. The identical score is fully explained by resubmitting "
                    "the same file; it is not evidence of a placement-step collapse."),
            evidence="sha256_canonical equal across the trio",
            action="Registry now refuses any candidate whose canonical support matches a "
                   "scored artifact. The 0.1563 row can never be re-spent.")
    if identical_support:
        return dict(
            mechanism="SAME EMITTED PIXEL SET, DIFFERENT ENCODING",
            collapses_in_postprocessing=False,
            detail=("The trio differs byte-wise but emits exactly the same pixels; the "
                    "0.1563 equality is again explained before the metric is reached."),
            evidence="sha256_support equal across the trio",
            action="Gate on the support hash, not only on the file hash.")
    # compare raw vs final for the trio
    raw_vals, dice_vals = [], []
    for p in pairs:
        if p["score_a"] == 0.1563 and p["score_b"] == 0.1563:
            if np.isfinite(p.get("pearson_support", float("nan"))):
                raw_vals.append(p["pearson_support"])
            if np.isfinite(p.get("dice", float("nan"))):
                dice_vals.append(p["dice"])
    lo = float(np.mean(raw_vals)) if raw_vals else float("nan")
    di = float(np.mean(dice_vals)) if dice_vals else float("nan")
    if np.isfinite(lo) and np.isfinite(di) and lo < 0.9 and di > 0.95:
        return dict(mechanism="PLACEMENT-STEP COLLAPSE (raw surfaces differ, final "
                              "outputs agree)",
                    collapses_in_postprocessing=True,
                    detail=f"mean support-restricted raw r = {lo:.4f}, mean final Dice = {di:.4f}",
                    evidence="low raw correlation with high final agreement",
                    action="Fix the metric-aware placement step (spacing/thresholding), "
                           "not the upstream model.")
    return dict(mechanism="DISTINCT ARTIFACTS",
                collapses_in_postprocessing=False,
                detail=f"mean support-restricted raw r = {lo:.4f}, mean final Dice = {di:.4f}",
                evidence="raw surfaces and final supports both differ",
                action="Treat the equal score as a coarse-score coincidence; the gate "
                       "still blocks support duplicates.")


if __name__ == "__main__":
    raise SystemExit(main())
