#!/usr/bin/env python3
"""Calibrate the offline instruments against the live leaderboard.

Why this exists
---------------
Every claim this group makes about "which file should go into a submission slot"
rests on an *offline* instrument, because the organizer truth (the private
new-fault set) is not available.  An offline instrument is only useful if it
ranks artifacts the way the live scorer does.  This script measures that
directly: it takes a directory of artifacts that carry an owner-reported live
score and reports the rank correlation between each candidate instrument and
the live score.

Instruments measured
--------------------
``catalogue_blocked``
    The repository's own holdout (:mod:`gems34.holdout`): a spatially blocked
    subset of the catalogue is called "new", everything else in the catalogue
    is declared free (the organizer's mask), and the prediction is charged
    outside it.  Measures *re-finding* fault geometry the emission was not
    shown.

``pnf`` (proxy new faults)
    An independent official fault compilation -- USGS SGMC, the State Geologic
    Map Compilation -- minus the competition catalogue and its 3 px
    neighbourhood.  Measures *finding faults that the catalogue does not
    carry*, which is what the organizers actually score.  SGMC is a different
    lineage from the Quaternary database: it carries faults mapped by state
    geologists at map scale, many of which never entered the Quaternary
    compilation.

Neither instrument is the organizer truth.  The *validated* instrument is the
one whose Spearman rho against the live scores is highest; the script prints
that number so a reader can judge how much weight it will bear.

Verified official sources (fetched and hash-pinned by the sibling repositories)
-------------------------------------------------------------------------------
* USGS SGMC Nevada  https://mrdata.usgs.gov/geology/state/shp/NV.zip
      sha256 3b333ac025e59aae7f0d827db45ba32c425cf867eb341561a788af1de186b76b
      landing https://mrdata.usgs.gov/geology/state/  (public domain)
* USGS SGMC California  https://mrdata.usgs.gov/geology/state/shp/CA.zip
      sha256 78765ba4428df9f25a84f86e0b2529bd0508fc8a2cf65d2f41a830e82bccfd58
* INGENIOUS Quaternary fault compilation v2 (provenance of the training
  catalogue)  https://gdr.openei.org/files/1391/qfaults_ingenious_nad83conus117_2023-06-27.zip
      sha256 c7b091c9ac8bca140ad89ee6bb2bd63dd3ac12e3013acbfd8373d11c9faee59d
      licence CC BY 4.0, DOI 10.15121/1881483
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from gems34 import geology, raster
from gems34.metric import score_fast

# ---------------------------------------------------------------------------
# The calibration set: artifact file name -> owner-reported live score.
#
# Provenance of every score is a public page owned by the same account; the
# score is a *claim* made by the owner (the account itself is the submitter),
# never an organizer-verified number.  Scores were read off the group's own
# published result pages on 2026-10-04.
# ---------------------------------------------------------------------------
CALIBRATION: dict[str, tuple[float, str]] = {
    "s02778.tif": (0.2778, "GEMSDOE32 h33-h33-2-b2 (owner page; public rank #13)"),
    "s02708.tif": (0.2708, "GEMSDOE31 h27-4-solo-d28 (owner page)"),
    "s02600.tif": (0.2600, "GEMSDOE25 dotted-h19-5-d2-8 (owner page)"),
    "s02477.tif": (0.2477, "GEMSDOE24 h25-1-dotted-h19-5-d1-5 (owner page)"),
    "s02449.tif": (0.2449, "GEMSDOE27 topo-gap-closure-t-v2-on-d1-5 (owner page)"),
    "s01922.tif": (0.1922, "GEMSDOE19 h19-5-powerlaw-budget (owner page)"),
    "s01894.tif": (0.1894, "GEMSDOE19 h19-4-multiline-corroborated (owner page)"),
    "s01890.tif": (0.1890, "20GEMSDOE h20-1-sarnnpu-powerlaw (owner page)"),
    "s01859.tif": (0.1859, "20GEMSDOE h20-5-continuous-pu-proxy (owner page)"),
    "s01855.tif": (0.1855, "16GEMSDOE h16-1-topo-geophys-baseline-ridges (owner page)"),
    "s01839.tif": (0.1839, "GEMSDOE10 h28-dotted-ridge (owner page)"),
    "s01563.tif": (0.1563, "8GEMSDOE Hedge-v2 / GEMSDOE1 ens12 / 5GEMSDOE (owner page)"),
    "s01560.tif": (0.1560, "GEMSDOE2 dual-family-union (owner page)"),
    "s01352.tif": (0.1352, "GEMSDOE23 h30-arrangement-matched-habitat (owner page)"),
    "s01294.tif": (0.1294, "12GEMSDOE r7-nms3-dem10-scarp (owner page)"),
    "s01280.tif": (0.1280, "GEMSDOE10 h25-ctx-ridge (owner page)"),
    "s01193.tif": (0.1193, "GEMSDOE3 pindrop-v4-nodes (owner page)"),
    "s01002.tif": (0.1002, "GEMSDOE22 h23-a-dti-optimal-emission-6pct (owner page)"),
    "s00976.tif": (0.0976, "16GEMSDOE h18-3a-topo-geophys-x-complexity-prior (owner page)"),
    "s00921.tif": (0.0921, "GEMSDOE10 h20-dem10-scarp-thin (owner page)"),
    "s00904.tif": (0.0904, "13GEMSDOE r13-lattice-s5_v2 (owner page)"),
    "s00748.tif": (0.0748, "GEMSDOE22 h23-b-dti-optimal-emission-10pct (owner page)"),
    "s00461.tif": (0.0461, "GEMSDOE10 h16-continuation (owner page)"),
    "s00360.tif": (0.0360, "16GEMSDOE h18-4-usgs-geologic-map-faults-gap (owner page)"),
    "s00286.tif": (0.0286, "6GEMSDOE hgb88-topk03 (owner page)"),
    "s00187.tif": (0.0187, "17GEMSDOE F-ensemble-2pct (owner page)"),
    "s00020.tif": (0.0020, "14GEMSDOE r5-geom-horse-ensemble (owner page)"),
}


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation without scipy.stats (ties averaged)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)

    def rank(x):
        order = np.argsort(x, kind="mergesort")
        r = np.empty(len(x), float)
        r[order] = np.arange(len(x), dtype=float)
        # average ties
        sx = x[order]
        i = 0
        while i < len(sx):
            j = i
            while j + 1 < len(sx) and sx[j + 1] == sx[i]:
                j += 1
            if j > i:
                r[order[i:j + 1]] = (i + j) / 2.0
            i = j + 1
        return r

    ra, rb = rank(a), rank(b)
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    den = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / den) if den > 0 else float("nan")


def build_pnf(cat: np.ndarray, sgmc: np.ndarray, buffer_px: int = 3) -> np.ndarray:
    """Proxy new faults: SGMC fault pixels outside the catalogue's 3 px collar.

    The collar is removed because a catalogue pixel and its 300 m neighbourhood
    are free under the organizer's mask, so a fault that SGMC and the catalogue
    both carry is not evidence of a *new* fault.
    """
    d = geology.distance_to(cat)
    return (sgmc > 0) & (d > buffer_px)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--cal", default="/tmp/cal", help="dir of <name>.tif artifacts")
    ap.add_argument("--sgmc", default=None, help="SGMC-derived 100 m raster")
    ap.add_argument("--blocks", type=int, default=4)
    ap.add_argument("--free-mode", default="exact", choices=("exact", "dilate3"))
    ap.add_argument("--out", default="docs/data/calibration.json")
    args = ap.parse_args()

    data = Path(args.data)
    labels = raster.read(data / "labels.tif")
    cat = labels == 1

    if args.sgmc is None:
        cands = [Path("/tmp/hist/sgmc_g30.tif")]
        cands = [c for c in cands if c.exists()]
        if not cands:
            raise SystemExit("pass --sgmc <sgmc raster>")
        args.sgmc = str(cands[0])
    sgmc = raster.read(args.sgmc)
    pnf = build_pnf(cat, sgmc)

    print(f"catalogue pixels          : {int(cat.sum()):,}")
    print(f"SGMC pixels               : {int((sgmc > 0).sum()):,}")
    print(f"proxy new faults (PNF)    : {int(pnf.sum()):,}")

    # blocked holdout over the catalogue
    from gems34.holdout import Instrument
    inst = Instrument(labels, n_blocks=args.blocks, buffer_px=3,
                      free_mode=args.free_mode)

    cal = Path(args.cal)
    rows = []
    for name, (score, prov) in CALIBRATION.items():
        p = cal / name
        if not p.exists():
            continue
        pred = raster.read(p)
        rec = dict(file=name, score=score, provenance=prov,
                   sha256=sha256_file(p))
        pred = np.where(np.isfinite(pred), np.clip(pred, 0.0, 1.0), 0.0)
        rec["n_positive"] = int((pred > 0).sum())
        rec["on_catalogue"] = int(((pred > 0) & cat).sum())
        rec["payload"] = int(((pred > 0) & ~cat).sum())

        # instrument A: catalogue-blocked holdout, pooled over folds
        scores = []
        for f in inst.folds:
            free = f.free
            c = score_fast(pred, f.truth, free)
            scores.append(c["dti"])
        rec["catalogue_blocked_mean"] = float(np.mean(scores))

        # instrument B: proxy new faults, mask the catalogue exactly as the
        # organizer does, and charge FP only off the catalogue.
        free = cat if args.free_mode == "exact" else geology.dilate(cat, 3)
        c = score_fast(pred, pnf, free)
        rec["pnf_dti"] = float(c["dti"])
        rec["pnf_tp"] = float(c["tp"])
        rec["pnf_fp"] = float(c["fp"])
        rec["pnf_coverage"] = float(c["coverage"])
        rows.append(rec)
        print(f"  {name:12s} live={score:.4f}  blocked={rec['catalogue_blocked_mean']:.5f}"
              f"  pnf={rec['pnf_dti']:.5f}  n={rec['n_positive']:,}"
              f"  oncat={rec['on_catalogue']:,}")

    if len(rows) < 4:
        print("not enough calibration artifacts found")
        return 1

    live = np.array([r["score"] for r in rows])
    blocked = np.array([r["catalogue_blocked_mean"] for r in rows])
    pnfv = np.array([r["pnf_dti"] for r in rows])
    res = dict(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        n_artifacts=len(rows),
        sgmc_source=args.sgmc,
        sgmc_sha256=sha256_file(args.sgmc),
        pnf_pixels=int(pnf.sum()),
        catalogue_pixels=int(cat.sum()),
        spearman_live_vs_catalogue_blocked=spearman(live, blocked),
        spearman_live_vs_pnf=spearman(live, pnfv),
        rows=rows,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
    print()
    print(f"n = {len(rows)} artifacts with an owner-reported live score")
    print(f"Spearman rho(live, catalogue_blocked) = "
          f"{res['spearman_live_vs_catalogue_blocked']:+.3f}")
    print(f"Spearman rho(live, pnf)               = "
          f"{res['spearman_live_vs_pnf']:+.3f}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
