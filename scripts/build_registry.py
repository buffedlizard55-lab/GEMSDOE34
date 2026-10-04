"""Build registry/history.json from the on-disk artifact corpus.

The corpus is not committed (it is ~18 MB of GeoTIFFs held by the sibling
repositories).  This script rebuilds it from those checkouts, fingerprints every
artifact, and writes the committable registry.  Run:

    python scripts/build_registry.py --corpus /tmp/work/history

A registry entry records: the artifact name, its owner-stated label, its score
with an explicit evidence class, the measured SHA-256 of its values and of its
support, the pixel count, the fraction of its pixels that lie on the known-fault
mask, and the fraction outside the mask (the *payload* -- the only part of an
emission that can change a score under the organizers' masking rule).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems34 import geology, raster, registry  # noqa: E402

# Scores are dated leaderboard snapshots or owner claims.  They are never
# presented as organizer receipts; there is no hash-to-score crosswalk.
CLAIMS = {
    "gemsdoe1-ens12-7f00890a.tif": (0.1563, "claim"),
    "gemsdoe-ens12-adopted-7f00890a.tif": (0.1563, "claim (same file as gemsdoe1-ens12)"),
    "8GEMSDOE_Hedge-v2_submission.tif": (0.1563, "claim"),
    "8GEMSDOE-Apex-Geothermal-V1.tif": (None, "unscored"),
    "gemsdoe2-dual-family-union-f68e590f.tif": (0.1560, "claim"),
    "gemsdoe2-dual-union-f68e590f.tif": (0.1560, "claim (same file)"),
    "gemsdoe2-extension-arm-ad5ba911.tif": (None, "unscored"),
    "gemsdoe2-precision-arm-8bce5dfe.tif": (None, "unscored"),
    "gemsdoe1-ens12-floor0.1.tif": (None, "unscored (same pixels as gemsdoe1-ens12)"),
    "gemsdoe3-pindrop-nodes-f347b70daa.tif": (0.1193, "claim"),
    "gemsdoe3-pindrop-discovery-37f9d5b855.tif": (0.0830, "claim"),
    "gemsdoe3-pindrop-ridge-4e03fc9705.tif": (0.1152, "claim"),
    "gemsdoe3-sgmc-gap-7251c22bb4.tif": (None, "unscored"),
    "gemsdoe4-combined-237f0063.tif": (0.0343, "claim"),
    "gems6-hgb88-topk03-33cec71ff0.tif": (0.0286, "claim"),
    "gemsdoe31-h27-4-solo-d28-20261004-8acb75e1-nan.tif": (0.2708, "claim"),
    "gemsdoe31-h27-4-solo-d28-20261004-8acb75e1-allfinite.tif": (None, "unscored (same support)"),
    "gemsdoe31-add-arm-d28-20261004-8acb75e1-nan.tif": (None, "unscored"),
    "gemsdoe31-union-b-p060-20261004-8acb75e1-nan.tif": (None, "unscored"),
    "gemsdoe31-reference-d28-offcat-44090-20261004-nan.tif": (None, "unscored"),
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif": (0.2600, "claim (owner page disputes)"),
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif": (None, "unscored (same support)"),
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif": (
        0.2778, "claim (= public #13 extradr19); the sibling's own .zip for this "
                "file is 0 bytes, so the only copy is this .tif"),
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-nan.tif": (0.2778, "claim (same artifact, nan variant)"),
    "gems32-h19-5-smoothmaxcov-44090.tif": (0.2600, "claim (44090-dot reference)"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="/tmp/work/history")
    ap.add_argument("--extra", nargs="*", default=[], help="additional TIFs to include")
    ap.add_argument("--labels", default="/tmp/work/data/labels.tif")
    ap.add_argument("--out", default="registry/history.json")
    args = ap.parse_args()

    cat = raster.read(args.labels) == 1
    dcat = geology.distance_to(cat).astype(np.float32)      # computed once, not per artifact
    paths = sorted(Path(args.corpus).glob("*.tif")) + [Path(p) for p in args.extra]
    entries = []
    for p in paths:
        score, cls = CLAIMS.get(p.name, (None, "unscored"))
        try:
            fp = registry.fingerprint(p)
        except Exception as e:                                  # noqa: BLE001
            print("skip", p.name, e)
            continue
        a = raster.read(p)
        m = np.isfinite(a) & (a > 0)
        on_cat = int((m & cat).sum())
        d = dcat[m] if m.any() else np.array([np.inf])
        entries.append(dict(
            name=p.name, label=cls, score=score, evidence_class=cls,
            sha256_canonical=fp["sha256_canonical"], sha256_support=fp["sha256_support"],
            n_positive=int(m.sum()), is_binary=fp["is_binary"],
            pct_on_catalogue=round(100.0 * on_cat / max(int(m.sum()), 1), 3),
            pct_within_300m=round(100.0 * float((d <= 3).mean()), 3),
            payload_pixels=int(m.sum()) - on_cat,
        ))
        print(f"{p.name:64s} n={int(m.sum()):7d} on-cat={entries[-1]['pct_on_catalogue']:6.2f}%")
    registry.save_registry(entries, args.out)
    print(f"\nwrote {args.out} with {len(entries)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
