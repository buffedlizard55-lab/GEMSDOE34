#!/usr/bin/env python3
"""Reconstruct the two hash-pinned competition rasters into ``data/``.

The competition rasters are large (the feature stack is ~419 MB), so they are
not committed.  This script documents *exactly* how they were assembled and
verifies them by SHA-256 afterwards.  It never trusts a mirror: it checks the
digest of what it ends up with against the value recorded here, which was
measured in this workspace and (for the feature stack) also matches the pin in
the sibling bridge manifest.

    python scripts/assemble_data.py --src <dir-with-parts> [--dest data]

Expected layout of ``--src`` (this is what the sibling repositories carry):

    part files   gems-geodawn-numerical-features.tif.part-*   (concatenate in
                 lexicographic order -> training_features.tif)
    single files labels.tif, sample_submission.tif

If a file is already present and matches its digest, nothing is done.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

EXPECTED = {
    "training_features.tif":
        "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "labels.tif":
        "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif":
        "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}

ALIASES = {                       # names the sibling checkouts use
    "labels.tif": ["labels.tif", "existing_faults.tif"],
    "sample_submission.tif": ["sample_submission.tif", "example_submission.tif"],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def assemble_features(src: Path, dest: Path) -> None:
    parts = sorted(src.glob("gems-geodawn-numerical-features.tif.part-*"))
    if not parts:
        raise SystemExit(f"no part files under {src}")
    out = dest / "training_features.tif"
    with out.open("wb") as dst:
        for p in parts:
            print(f"  + {p.name} ({p.stat().st_size:,} B)")
            with p.open("rb") as fh:
                shutil.copyfileobj(fh, dst, 1 << 22)
    print(f"  = {out.name} ({out.stat().st_size:,} B)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True, help="directories holding the parts/files")
    ap.add_argument("--dest", default="data")
    args = ap.parse_args()

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    srcs = [Path(s) for s in args.src]

    for name, want in EXPECTED.items():
        target = dest / name
        if target.exists() and sha256(target) == want:
            print(f"ok      {name} (digest matches)")
            continue
        found = None
        for s in srcs:
            for cand in [s / name] + [s / a for a in ALIASES.get(name, [])]:
                if cand.exists():
                    found = cand
                    break
            if found:
                break
        if name == "training_features.tif" and found is None:
            for s in srcs:
                if any(s.glob("gems-geodawn-numerical-features.tif.part-*")):
                    print(f"build   {name} from parts in {s}")
                    assemble_features(s, dest)
                    found = target
                    break
        if found is None:
            print(f"MISSING {name} — no source found in {[str(s) for s in srcs]}")
            continue
        if found != target:
            shutil.copy2(found, target)
            print(f"copy    {name} <- {found}")
        got = sha256(target)
        status = "ok     " if got == want else "MISMATCH"
        print(f"{status} {name}\n        want {want}\n        got  {got}")
        if got != want:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
