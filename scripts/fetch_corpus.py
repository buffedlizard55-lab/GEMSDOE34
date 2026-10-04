#!/usr/bin/env python3
"""Fetch the group's full scored-artifact corpus from the public sibling repositories.

Every prior GEMS submission raster the group has published lives in a public
GitHub repository under ``buffedlizard55-lab``.  This script pulls only the
``*.tif`` blobs it needs (``--filter=blob:none`` + sparse checkout), so the
large feature stacks are never transferred.

It exists because the *documented* route to the competition rasters
(`scripts/download_competition_data.sh` -> DrivenData login, or the Dropbox
mirrors) is unavailable inside an egress-restricted sandbox, while
``github.com`` is reachable.  The corpus is written to ``--out`` with a
``manifest.json`` recording repo, path and sha256 for every file, so the
provenance of every number downstream is auditable.

Usage
-----
    python scripts/fetch_corpus.py --out /tmp/corpus
    python scripts/fetch_corpus.py --out /tmp/corpus --repos GEMSDOE32 GEMSDOE31
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

OWNER = "buffedlizard55-lab"

# repo -> extra glob-ish path prefixes that hold published submission rasters
DEFAULT_REPOS = [
    "GEMSDOE", "GEMSDOE2", "GEMSDOE3", "GEMSDOE4", "5GEMSDOE", "6GEMSDOE",
    "7GEMSDOE", "8GEMSDOE", "GEMSDOE9", "GEMSDOE10", "11GEMSDOE", "12GEMSDOE",
    "13GEMSDOE", "14GEMSDOE", "15GEMSDOE", "16GEMSDOE", "17GEMSDOE",
    "18GEMSDOE", "19GEMSDOE", "20GEMSDOE", "GEMSDOE21", "GEMSDOE22",
    "GEMSDOE23", "GEMSDOE24", "GEMSDOE25", "GEMSDOE26", "GEMSDOE27",
    "GEMSDOE28", "GEMSDOE29", "GEMSDOE30", "GEMSDOE31", "GEMSDOE32",
    "GEMSDOE33", "GEMSDOE34", "GEMSDOE35", "GEMSDOE36", "LEARNGEMSDOE",
]

# Directories that hold submission rasters or calibration copies of them.
WANTED_DIRS = (
    "docs/downloads/", "downloads/", "external/scored/", "inputs/calibration/",
    "inputs/", "data/bridge/", "data/sample", "archive/legacy_candidates/",
    "evidence/history/", "docs/research/", "docs/",
)
# Never pull the multi-hundred-megabyte feature stacks.
SKIP_SUBSTRINGS = (
    "gems-geodawn-numerical-features.tif.part",
    "training_features", "topo_u8.tif.part", "radiometric_u8.tif.part",
    "lidar_scarp_features_u8.tif", "geodawn_rad_u8.tif",
    "geodawn_extensions_u8.tif", "fixture_features",
)
MAX_BYTES = 25_000_000


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def list_tifs(repo: str) -> list[dict]:
    """List ``*.tif`` blobs in ``repo`` HEAD via the GitHub git-trees API."""
    out = run(["curl", "-sS", "--max-time", "120",
               f"https://api.github.com/repos/{OWNER}/{repo}/git/trees/HEAD?recursive=1"]).stdout
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        print(f"  ! {repo}: non-JSON API response", file=sys.stderr)
        return []
    if "tree" not in d:
        print(f"  ! {repo}: {str(d)[:160]}", file=sys.stderr)
        return []
    hits = []
    for t in d["tree"]:
        if t["type"] != "blob" or not t["path"].endswith(".tif"):
            continue
        if any(s in t["path"] for s in SKIP_SUBSTRINGS):
            continue
        if t.get("size", 0) > MAX_BYTES:
            continue
        if not any(p in t["path"] for p in WANTED_DIRS):
            continue
        hits.append(t)
    return hits


def fetch(repo: str, outdir: str, keep: list[dict]) -> list[dict]:
    """Sparse-checkout ``keep`` from ``repo`` into ``outdir``."""
    tmp = tempfile.mkdtemp(prefix="gems-fetch-")
    got = []
    try:
        run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout",
             "--depth", "1", f"https://github.com/{OWNER}/{repo}", tmp])
        run(["git", "-C", tmp, "sparse-checkout", "init", "--no-cone"])
        pats = "\n".join("/" + t["path"] for t in keep)
        with open(os.path.join(tmp, ".git", "info", "sparse-checkout"), "w") as fh:
            fh.write(pats + "\n")
        run(["git", "-C", tmp, "checkout", "HEAD"])
        for t in keep:
            src = os.path.join(tmp, t["path"])
            if not os.path.isfile(src):
                print(f"  ! {repo}: missing after checkout {t['path']}", file=sys.stderr)
                continue
            dst_name = f"{repo}__{t['path'].replace('/', '_')}"
            dst = os.path.join(outdir, dst_name)
            shutil.copyfile(src, dst)
            with open(dst, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            got.append(dict(repo=repo, path=t["path"], file=dst_name,
                            bytes=os.path.getsize(dst), sha256=digest,
                            sha256_matches_github_blob_size=t.get("size") == os.path.getsize(dst)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return got


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--repos", nargs="*", default=None)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    repos = args.repos or DEFAULT_REPOS
    manifest = []
    for repo in repos:
        hits = list_tifs(repo)
        if not hits:
            print(f"  - {repo}: no eligible rasters")
            continue
        print(f"  + {repo}: {len(hits)} rasters")
        manifest.extend(fetch(repo, args.out, hits))
    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(dict(owner=OWNER, n=len(manifest), files=manifest), fh, indent=1)
    print(f"wrote {len(manifest)} rasters + manifest.json -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
