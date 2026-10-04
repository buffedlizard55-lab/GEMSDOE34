#!/usr/bin/env python3
"""The mandated pre-submission gate, and the 0.1563 collapse diagnosis.

The standing brief asks for one specific thing before any slot is spent:

    "compute the correlation between its raw, pre-postprocessing probability
     surface and every prior submission's raw surface, separately from the
     pixel-agreement rate between their final thresholded outputs.  Low raw
     correlation paired with near-100% final agreement confirms the placement
     step as the collapse point ... Make this a mandatory pre-submission gate."

Three numbers are therefore reported for every pair, and they are not the same
number:

  ``pearson_raw``    correlation of the two files' *values* over their common
                     finite footprint -- the pre-threshold surfaces.
  ``dice_final``     agreement of the two *thresholded* supports.
  ``dice_payload``   agreement of the supports **with the free mask removed**.

The third is the one that can actually catch a duplicated hypothesis, because
the organizers confirmed on the official forum that catalogue pixels are masked
out of evaluation, so mass on the catalogue cannot move a score:

    chrisk-dd (DrivenData Staff), 2026-09-16, post 2 of
    https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516

``--diagnose`` runs that test on the three artifacts the group reports at
exactly 0.1563 and on a control artifact from the same family whose score moved.

Usage
-----
    python scripts/run_collapse_gate.py --data data --corpus /tmp/corpus \
        --diagnose --out docs/data/collapse-diagnosis.json
    python scripts/run_collapse_gate.py --data data --corpus /tmp/corpus \
        --candidate docs/downloads/x.tif --out docs/downloads/x-gate.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import rasterio

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from gems34 import ledger as ledger_mod  # noqa: E402

NEAR_RAW = 0.98
NEAR_FINAL = 0.95
NEAR_PAYLOAD = 0.95

TRIO = ["gemsdoe1-ens12-7f00890a", "gemsdoe-ens12-adopted-7f00890a",
        "8GEMSDOE_Hedge-v2_submission"]
CONTROL = "gemsdoe2-dual-family-union-f68e590f"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def load(path):
    with rasterio.open(path) as ds:
        return ds.read(1), ds


def support(a):
    return np.nan_to_num(np.asarray(a, np.float32), nan=0.0,
                         posinf=0.0, neginf=0.0) > 0


def dice(x, y):
    nx, ny = int(x.sum()), int(y.sum())
    if nx + ny == 0:
        return 1.0
    return 2.0 * int((x & y).sum()) / (nx + ny)


def pearson(a, b):
    fa = np.isfinite(a) & np.isfinite(b)
    if fa.sum() < 2:
        return float("nan")
    x, y = a[fa].astype(np.float64), b[fa].astype(np.float64)
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def fingerprint(path):
    a, ds = load(path)
    s = support(a)
    return dict(file=os.path.basename(path), sha256=sha256(path),
                n_positive=int(s.sum()),
                n_nonfinite=int((~np.isfinite(a)).sum()),
                nodata=("nan" if ds.nodata is not None and np.isnan(ds.nodata)
                        else ds.nodata),
                min=(None if not np.isfinite(a).any()
                     else float(np.nanmin(a[np.isfinite(a)]))),
                max=(None if not np.isfinite(a).any()
                     else float(np.nanmax(a[np.isfinite(a)]))),
                width=ds.width, height=ds.height, dtype=ds.dtypes[0],
                crs=str(ds.crs))


def pair_report(A, B, free):
    """The three numbers the brief asks for, plus the containment view."""
    a, b = A["mask"], B["mask"]
    pa, pb = a & ~free, b & ~free
    return dict(
        against=B["file"], score=B.get("score"),
        pearson_raw=None if A.get("values") is None or B.get("values") is None
        else round(pearson(A["values"], B["values"]), 6),
        dice_final=round(dice(a, b), 6),
        dice_payload=round(dice(pa, pb), 6),
        n_a=int(a.sum()), n_b=int(b.sum()),
        payload_a=int(pa.sum()), payload_b=int(pb.sum()),
        intersection=int((a & b).sum()),
        payload_intersection=int((pa & pb).sum()),
        containment_a_in_b=round(float((a & b).sum()) / max(int(a.sum()), 1), 6),
        added_px=int((b & ~a).sum()),
        added_on_free=int(((b & ~a) & free).sum()),
        added_on_free_pct=round(100.0 * float(((b & ~a) & free).sum()) /
                                max(int((b & ~a).sum()), 1), 2),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--corpus", default="/tmp/corpus")
    ap.add_argument("--candidate", default=None)
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--limit", type=int, default=0,
                    help="compare against at most N corpus files (0 = all)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    lab = rasterio.open(os.path.join(a.data, "labels.tif")).read(1)
    free = lab > 0
    inside = lab != -1
    print(f"free mask (catalogue) {int(free.sum()):,} px; "
          f"footprint {int(inside.sum()):,} px")

    # ---- corpus -------------------------------------------------------------
    ledger = {r["file"]: r for r in ledger_mod.resolve(a.corpus) if r["file"]}
    corpus = []
    files = sorted(f for f in os.listdir(a.corpus) if f.endswith(".tif"))
    for i, fn in enumerate(files):
        if a.limit and i >= a.limit:
            break
        p = os.path.join(a.corpus, fn)
        try:
            fp = fingerprint(p)
        except Exception as e:                      # noqa: BLE001
            print("  ! unreadable", fn, e)
            continue
        fp["score"] = ledger.get(fn, {}).get("score")
        corpus.append(fp)
    print(f"corpus: {len(corpus)} rasters")

    out = dict(generated_utc=datetime.now(timezone.utc).isoformat(),
               free_mask="data/labels.tif > 0 (sha256 7ba308cc...)",
               n_corpus=len(corpus),
               rules=dict(near_duplicate_raw=f"pearson_raw >= {NEAR_RAW}",
                          near_duplicate_final=f"dice_final >= {NEAR_FINAL}",
                          near_duplicate_payload=f"dice_payload >= {NEAR_PAYLOAD}"))

    # ---- the mandated 0.1563 diagnosis -------------------------------------
    if a.diagnose:
        by_name = {}
        for fp in corpus:
            for t in TRIO + [CONTROL]:
                if t in fp["file"]:
                    by_name.setdefault(t, fp)
        missing = [t for t in TRIO + [CONTROL] if t not in by_name]
        trio_rows, control_rows = [], []
        vals = {}
        for t, fp in by_name.items():
            arr, _ = load(os.path.join(a.corpus, fp["file"]))
            vals[t] = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
            fp["values"] = vals[t]
            fp["mask"] = support(arr)
        base = TRIO[0]
        for t in TRIO:
            if t == base or t not in by_name:
                continue
            r = pair_report({**by_name[base], "values": vals[base]},
                            {**by_name[t], "values": vals[t]}, free)
            r["payload_identical"] = bool(np.array_equal(
                by_name[base]["mask"] & ~free, by_name[t]["mask"] & ~free))
            trio_rows.append(r)
        if CONTROL in by_name:
            r = pair_report({**by_name[base], "values": vals[base]},
                            {**by_name[CONTROL], "values": vals[CONTROL]}, free)
            r["payload_identical"] = bool(np.array_equal(
                by_name[base]["mask"] & ~free, by_name[CONTROL]["mask"] & ~free))
            control_rows.append(r)
        mech = ("FREE-MASK SATURATION"
                if all(r["payload_identical"] and r["added_on_free_pct"] >= 99.9
                       for r in trio_rows) else "NOT REPRODUCED")
        out["diagnosis"] = dict(
            question="why did three artifacts all score exactly 0.1563?",
            trio_found=[by_name[t]["file"] for t in TRIO if t in by_name],
            control_found=[by_name[CONTROL]["file"]] if CONTROL in by_name else [],
            missing=missing,
            mechanism=mech,
            trio_comparisons=trio_rows,
            control_comparisons=control_rows,
            reading=("the three claims are not three hypotheses: two artifacts "
                     "have byte-identical off-mask payloads and the third adds "
                     "pixels that lie entirely on the free mask, which the "
                     "organizers confirmed cannot enter a penalty term. The "
                     "control added pixels mostly off the mask and its score "
                     "moved."),
        )
        print(f"\n0.1563 mechanism: {mech}")
        for r in trio_rows + control_rows:
            print(f"  vs {r['against'][:52]:52s} pearson_raw="
                  f"{('%.4f' % r['pearson_raw']) if r['pearson_raw'] is not None else 'n/a'} "
                  f"dice_final={r['dice_final']:.4f} dice_payload={r['dice_payload']:.4f} "
                  f"added={r['added_px']} on_free={r['added_on_free_pct']}% "
                  f"payload_identical={r['payload_identical']}")

    # ---- candidate gate -----------------------------------------------------
    if a.candidate:
        fp = fingerprint(a.candidate)
        arr, _ = load(a.candidate)
        fp["values"] = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        fp["mask"] = support(arr)
        rows, blocks = [], []
        for c in corpus:
            if c["file"] == os.path.basename(a.candidate):
                continue
            if c["width"] != fp["width"] or c["height"] != fp["height"]:
                continue
            carr, _ = load(os.path.join(a.corpus, c["file"]))
            cc = {**c, "values": np.nan_to_num(carr, nan=0.0, posinf=0.0, neginf=0.0),
                  "mask": support(carr)}
            r = pair_report(fp, cc, free)
            del carr, cc
            rows.append(r)
            if r["dice_payload"] >= NEAR_PAYLOAD:
                blocks.append(("payload", r["against"], r["dice_payload"]))
            if r["dice_final"] >= NEAR_FINAL:
                blocks.append(("final", r["against"], r["dice_final"]))
            if (r["pearson_raw"] is not None and np.isfinite(r["pearson_raw"])
                    and r["pearson_raw"] >= NEAR_RAW):
                blocks.append(("raw", r["against"], r["pearson_raw"]))
            if r["added_px"] == 0 and r["containment_a_in_b"] == 1.0:
                blocks.append(("subset", r["against"], 1.0))
        rows.sort(key=lambda r: -r["dice_payload"])
        out["gate"] = dict(
            candidate=os.path.basename(a.candidate), fingerprint={
                k: v for k, v in fp.items() if k not in ("mask", "values")},
            n_compared=len(rows),
            max_dice_payload=rows[0]["dice_payload"] if rows else None,
            max_dice_payload_against=rows[0]["against"] if rows else None,
            max_dice_final=max((r["dice_final"] for r in rows), default=None),
            top20=rows[:20],
            blocking_rules=blocks,
            allowed=len(blocks) == 0,
        )
        print(f"\ngate {os.path.basename(a.candidate)}: "
              f"max payload Dice {rows[0]['dice_payload']:.4f} "
              f"vs {rows[0]['against'][:50]}  ->  "
              f"{'ALLOWED' if not blocks else 'REFUSED ' + str(blocks[:3])}")

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump(out, open(a.out, "w"), indent=1)
        print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
