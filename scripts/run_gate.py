#!/usr/bin/env python3
"""Re-run the mandatory pre-submission gate on an already-built candidate.

The brief makes this gate mandatory before any weekly slot is spent: a candidate
must be a *new hypothesis*, not a re-emission of one that has already been
scored.  Because free-mask mass cannot change a score (the organizers mask
known USGS/INGENIOUS faults out of the penalty terms), whole-file comparison is
not enough -- this script compares the **payload** as well.

    python scripts/run_gate.py docs/downloads/<name>.tif \
        --history /tmp/work/history docs/downloads --labels /tmp/work/data/labels.tif

Exit status is 0 when the gate allows the candidate and 1 when it refuses, so it
can be used directly in a release check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems34 import raster, registry  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--history", nargs="+", default=["/tmp/work/history"])
    ap.add_argument("--labels", default="/tmp/work/data/labels.tif")
    ap.add_argument("--out", default=None, help="write the gate report here")
    args = ap.parse_args()

    cand = Path(args.candidate)
    free = raster.read(args.labels) == 1 if Path(args.labels).exists() else None
    entries = []
    for h in args.history:
        if not Path(h).exists():
            continue
        for q in sorted(Path(h).glob("*.tif")):
            if q.name == cand.name or q.resolve() == cand.resolve():
                continue
            fp = registry.fingerprint(q)
            entries.append(dict(name=q.name, _path=str(q),
                                **{k: fp[k] for k in
                                   ("sha256_canonical", "sha256_support", "n_positive")}))
    print(f"{len(entries)} artifacts in the comparison corpus; "
          f"free mask = {'catalogue' if free is not None else 'unavailable'}")
    gate = registry.gate(cand, entries, free_mask=free)
    if args.out:
        Path(args.out).write_text(json.dumps(gate, indent=2) + "\n")

    print(f"\ncandidate      : {cand.name}")
    print(f"n_positive     : {gate['fingerprint']['n_positive']}")
    print(f"max Dice vs history : {gate['max_dice_vs_history']:.4f} "
          f"({gate['max_dice_against']})")
    if gate["payload_gate_used"]:
        rows = [r for r in gate["rows"] if "payload_dice" in r]
        rows.sort(key=lambda r: -(r["payload_dice"] if np.isfinite(r["payload_dice"]) else -1))
        print("\nclosest payloads (the criterion that actually matters):")
        for r in rows[:6]:
            print(f"  {r['against'][:56]:56s} payload_dice={r['payload_dice']:.4f} "
                  f"containment={r['payload_containment_a_in_b']:.4f}")
    print(f"\nGATE: {'ALLOWED' if gate['allowed'] else 'REFUSED'}")
    if gate["blocking_rules"]:
        print("blocking rules:", ", ".join(gate["blocking_rules"]))
        for r in gate["rows"]:
            if r.get("against") in (gate["duplicates"] + gate["near_duplicate_raw"]
                                    + gate["near_duplicate_final"] + gate["near_duplicate_payload"]):
                print("  ->", json.dumps({k: v for k, v in r.items()
                                          if k in ("against", "dice", "payload_dice",
                                                   "pearson_support", "exact_duplicate",
                                                   "support_duplicate")}))
    return 0 if gate["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
