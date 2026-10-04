#!/usr/bin/env python3
"""The group's score ledger, mapped onto the fetched corpus.

Every score here is a **user-reported claim** copied verbatim from the standing
brief (the list of GEMSDOE sites and their scores).  No score in this file is an
organizer receipt.  ``match`` resolves each claim to the raster bytes that the
sibling repository publishes under that name, so downstream analysis can be
traced to a sha256.

Source of the claims (as given in the standing brief):
    https://buffedlizard55-lab.github.io/<REPO>/docs/index.html
"""

from __future__ import annotations

import hashlib
import json
import os

# (repo, claim-name as printed on the site, score, glob substring in corpus filename)
LEDGER = [
    ("GEMSDOE",  "gems-submission-20260925T001403Z-7f00890a", 0.1563, "7f00890a"),
    ("5GEMSDOE", "gems-submission-20260926T175114Z-7f00890a", 0.1563, "7f00890a"),
    ("8GEMSDOE", "Hedge-v2_submission",                       0.1563, "Hedge-v2"),
    ("GEMSDOE2", "gemsdoe2-dual-family-union-…-f68e590f",     0.1560, "dual-family-union"),
    ("6GEMSDOE", "gems6_hgb88-topk03_33cec71ff0",             0.0286, "hgb88-topk03"),
    ("GEMSDOE3", "pindrop-v4-nodes-…-f347b70daa",             0.1193, "pindrop-nodes"),
    ("GEMSDOE3", "pindrop-v4-discovery-…-37f9d5b855",         0.0830, "pindrop-discovery"),
    ("GEMSDOE3", "pindrop-v4-ridge-…-4e03fc9705",             0.1152, "pindrop-ridge"),
    ("GEMSDOE4", "gems-submission-20260926T163915Z-237f0063", 0.0343, "237f0063"),
    ("7GEMSDOE", "lidarscarp-ridge-top2pct-36c3a3f341c8",     0.1461, "lidarscarp-ridge"),
    ("GEMSDOE9", "2314b599",                                  0.0107, "2314b599"),
    ("11GEMSDOE","gems-structural-area06-v1",                 0.0202, "area06-v1"),
    ("12GEMSDOE","r7-nms3-dem10-scarp_0c9199f14e62",          0.1294, "r7-nms3-dem10-scarp_0c9199f14e62.tif"),
    ("15GEMSDOE","gems-tso1-20260929T005627Z-conj_alteration_mag", 0.0782, "005627Z-conj_alteration_mag"),
    ("14GEMSDOE","GEMS_r5-geom-horse-ensemble_…",             0.0020, "horse-ensemble"),
    ("17GEMSDOE","17GEMSDOE_F-ensemble-2pct_20260930T050626Z",0.0187, "F-ensemble-2pct"),
    ("18GEMSDOE","H19-C_20260930T212401Z_c11e495e",           0.0297, "H19-C"),
    ("19GEMSDOE","h19-4-multiline-corroborated-openness-thermal-pop-…", 0.1894, "h19-4-multiline"),
    ("19GEMSDOE","h19-5-powerlaw-budget-multiline-corroborated-…",      0.1922, "h19-5-powerlaw"),
    ("GEMSDOE10","h16-continuation-20260927T065521…",         0.0461, "h16-continuation"),
    ("GEMSDOE10","h20-dem10-scarp-thin-20260927T155223…",     0.0921, "h20-dem10-scarp-thin"),
    ("GEMSDOE10","H25-ctx-ridge-20260927T232947…",            0.1280, "h25-ctx-ridge"),
    ("GEMSDOE10","h28-dotted-ridge-20260928T020256…",         0.1839, "h28-dotted-ridge"),
    ("13GEMSDOE","20261001_r13-lattice-s5_v2_nan-outside",    0.0904, "r13-lattice-s5_v2_nan-outside"),
    ("16GEMSDOE","h16-1-topo-geophys-baseline-ridges-…",      0.1855, "h16-1-topo-geophys"),
    ("16GEMSDOE","h18-3a-topo-geophys-x-complexity-prior-…",  0.0976, "h18-3a"),
    ("16GEMSDOE","h18-4-usgs-geologic-map-faults-gap-…",      0.0360, "h18-4"),
    ("GEMSDOE21","h19-4-reference-20260930-691e4dfa",         0.1894, "h19-4-reference"),
    ("20GEMSDOE","h20-1-sarnnpu-powerlaw-pi0363-tilt-wingcrack-…", 0.1890, "h20-1-sarnnpu"),
    ("20GEMSDOE","h20-5-continuous-pu-proxy-unverified-…",    0.1859, "h20-5-continuous"),
    ("GEMSDOE22","h23-a-dti-optimal-emission-6pct-…",         0.1002, "h23-a"),
    ("GEMSDOE22","h23-b-dti-optimal-emission-10pct-…",        0.0748, "h23-b"),
    ("GEMSDOE23","h30-arrangement-matched-habitat-…",         0.1352, "h30-arrangement"),
    ("GEMSDOE24","h25-1-dotted-h19-5-d1-5-…",                 0.2477, "dotted-h19-5-d1-5"),
    ("GEMSDOE25","dotted-h19-5-d2-8-20261002-e56ea318af89",   0.2600, "GEMSDOE25__docs_downloads_gems25-dotted-h19-5-d2-8"),
    ("GEMSDOE26","dilcond-oof-v1-20261003-47629f496133",      0.1223, "dilcond-oof"),
    ("GEMSDOE27","topo-gap-closure-t-v2-on-d1-5-…",           0.2449, "topo-gap-closure-t-v2-on-d1-5"),
    ("GEMSDOE28","h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc",  0.2708, "h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc"),
    ("GEMSDOE29","efd28-repro-20261003-1cc7dc534d51",         0.2600, "refd28-repro"),
    ("GEMSDOE30","d28-poisson300m-offcat-44090-…",            0.2600, "d28-poisson300m-offcat-44090"),
    ("GEMSDOE31","h27-4-solo-d28-20261004-8acb75e1-nan",      0.2708, "h27-4-solo-d28-20261004-8acb75e1-nan"),
    ("GEMSDOE32","h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros", 0.2778, "h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros"),
]


def resolve(corpus_dir: str) -> list[dict]:
    """Attach ``file``/``sha256`` to every ledger row that the corpus holds."""
    names = sorted(f for f in os.listdir(corpus_dir) if f.endswith(".tif"))
    out = []
    for repo, claim, score, needle in LEDGER:
        pref = repo + "__"
        cands = [n for n in names if n.startswith(pref) and needle in n]
        if not cands:
            # the same raster is mirrored into several sibling repos
            # (e.g. 7GEMSDOE/external/scored, GEMSDOE24/inputs/calibration),
            # so fall back to a corpus-wide search before calling it missing.
            cands = [n for n in names if needle in n]
        # prefer the shortest (least suffixed) candidate: -nan/-zeros twins collide
        cands.sort(key=lambda n: (len(n), n))
        row = dict(repo=repo, claim=claim, score=score, needle=needle,
                   n_candidates=len(cands),
                   file=cands[0] if cands else None,
                   all_candidates=cands)
        if cands:
            with open(os.path.join(corpus_dir, cands[0]), "rb") as fh:
                row["sha256"] = hashlib.sha256(fh.read()).hexdigest()
        out.append(row)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="/tmp/corpus")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rows = resolve(a.corpus)
    missing = [r for r in rows if not r["file"]]
    for r in rows:
        flag = "OK " if r["file"] else "MISS"
        print(f"{flag} {r['score']:.4f}  {r['repo']:11s} {r['claim'][:52]:52s} "
              f"{(r['file'] or '-')[:78]}")
    print(f"\n{len(rows) - len(missing)}/{len(rows)} resolved; missing: "
          f"{[m['claim'] for m in missing]}")
    if a.out:
        json.dump(rows, open(a.out, "w"), indent=1)
