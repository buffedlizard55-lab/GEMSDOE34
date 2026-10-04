"""Validate the candidate hypotheses on the organizer-shaped blocked holdout.

Protocol (leakage-free):
  * 4x4 spatial blocks over the competition grid; for each fold the *held-out*
    block is the "new fault" population and the remaining catalogue is the
    visible, known-fault set;
  * the freed mask is the visible catalogue (``--free-mode exact``) or its 3 px
    dilation (``--free-mode dilate3``), matching the two readings of the
    organizers' masking statement;
  * every field generator sees only the visible catalogue and the 19 published
    feature bands -- never the held-out block;
  * the emitter then applies the decision rule tau > bar (and tau > 0 on the
    free mask), optionally with non-maximum suppression at radius r.

Outputs docs/data/hypotheses.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems34 import fields, geology, holdout, raster  # noqa: E402

BARS = [0.02, 0.05, 0.08, 0.12, 0.20, 0.30]
RADII = [0, 3]


def _load_h5_inputs(path):
    """Read only the bands H5 needs, one at a time, as float32."""
    import rasterio
    need = ["tc", "tmi_hg", "iso_grav_anom_hg", "iso_grav_anom_vg", "tmi_vg",
            "geod_2ndinv", "geod_shearrate", "geod_dilaterate", "det_elev",
            "cond_surf"]
    out = {}
    with rasterio.open(path) as s:
        for k in need:
            a = s.read(fields.BAND[k] + 1).astype(np.float32)
            a[~np.isfinite(a)] = 0.0
            out[k] = a
    return out


def build_fields(cat_visible: np.ndarray, feats: dict | None) -> dict:
    sk = geology.skeleton(cat_visible)
    cos, sin = geology.local_strike(sk)
    out = {
        "H1_near_catalogue": fields.h1_near_catalogue(cat_visible),
        "H2_tip_extrapolation": _from_ext(cat_visible, sk, cos, sin, 14),
        "H3_gap_linkage": _from_bridge(cat_visible, sk),
        "H4_parallel_strands": fields.h4_parallel_strands(cat_visible),
    }
    h2 = out["H2_tip_extrapolation"]; h3 = out["H3_gap_linkage"]; h4 = out["H4_parallel_strands"]
    h1 = out["H1_near_catalogue"]
    out["H2+H3+H4"] = fields.composite((h2, 1.0), (h3, 1.0), (h4, 1.0))
    out["H1+H2+H3+H4"] = fields.composite((h1, 1.0), (h2, 1.0), (h3, 1.0), (h4, 1.0))
    if feats is not None:
        h5 = fields.h5_geophysical_lineaments(feats)
        out["H5_geophysical_lineaments"] = h5
        out["H5+struct"] = fields.composite((h5, 1.0), (out["H2+H3+H4"], 1.0))
    return out


def _from_ext(cat, sk, cos, sin, length):
    ext = geology.extrapolate_tips(cat.shape, sk, cos, sin, length=length) & ~cat
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(ext.astype(np.float64), 2.0)


def _from_bridge(cat, sk):
    from scipy.ndimage import gaussian_filter
    br = geology.bridge_gaps(sk, max_gap=16) & ~cat
    return gaussian_filter(br.astype(np.float64), 2.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/work/data")
    ap.add_argument("--out", default="docs/data/hypotheses.json")
    ap.add_argument("--blocks", type=int, default=4)
    ap.add_argument("--free-mode", default="exact", choices=["exact", "dilate3"])
    ap.add_argument("--quick", action="store_true", help="2x2 blocks instead of 4x4")
    args = ap.parse_args()
    if args.quick:
        args.blocks = 2

    d = Path(args.data)
    labels = raster.read(d / "labels.tif")
    cat = labels == 1
    instr = holdout.Instrument(cat, n_blocks=args.blocks, free_mode=args.free_mode)
    print(f"instrument: {len(instr.folds)} folds, {args.blocks}x{args.blocks} blocks, "
          f"free_mode={args.free_mode}, total truth={int(instr.cat.sum())}")

    feats = None
    h5 = None
    if (d / "training_features.tif").exists():
        feats = _load_h5_inputs(d / "training_features.tif")
        h5 = fields.h5_geophysical_lineaments(feats)
        del feats
        print("H5 lineament energy computed from 10 published bands")

    t0 = time.time()
    per_fold = {}
    refs = {}
    from scipy.ndimage import distance_transform_edt
    for fi, f in enumerate(instr.folds):
        dt = distance_transform_edt(~f.truth).astype(np.float32)
        cat_vis = instr.fold_catalogue(f)
        free = instr.fold_free(f)
        flds = build_fields(cat_vis, None)
        if h5 is not None:
            flds["H5_geophysical_lineaments"] = h5
            flds["H5+struct"] = fields.composite((h5, 1.0), (flds["H2+H3+H4"], 1.0))
        # reference strategies
        refs.setdefault("R0_empty", []).append(
            instr.score_against(np.zeros_like(labels, np.float32), f.truth, f.free, dt)["dti"])
        carpet = np.zeros(cat.shape, np.float32); carpet[free] = 1.0
        refs.setdefault("R1_carpet_only", []).append(
            instr.score_against(carpet, f.truth, f.free, dt)["dti"])
        del carpet
        for name, fld in flds.items():
            tau = holdout.smooth(fld)
            for bar in BARS:
                for rad in RADII:
                    em = holdout.emission(free, tau, bar, use_free=True,
                                          spacing=rad, free_mask=free)
                    key = (name, bar, rad)
                    per_fold.setdefault(key, []).append(
                        instr.score_against(em, f.truth, f.free, dt)["dti"])
                    del em
            del tau
        del flds, dt
        if fi % 4 == 3:
            import gc; gc.collect()
        print(f"  fold {f.name} done ({time.time()-t0:.0f}s)", flush=True)

    rows = []
    for (name, bar, rad), vals in per_fold.items():
        rows.append(dict(field=name, bar=bar, radius=rad,
                         mean_dti=float(np.mean(vals)), n_folds=len(vals),
                         per_fold=[round(v, 6) for v in vals]))
    rows.sort(key=lambda r: -r["mean_dti"])
    ref_rows = {k: dict(mean_dti=float(np.mean(v)), per_fold=[round(x, 6) for x in v])
                for k, v in refs.items()}

    out = dict(protocol=dict(blocks=args.blocks, free_mode=args.free_mode,
                             bars=BARS, radii=RADII, n_folds=len(instr.folds)),
               references=ref_rows, results=rows, top=rows[:15],
               note=("Truth is held-out *catalogue* geometry. This instrument "
                     "measures whether a rule recovers unseen fault geometry under "
                     "the organizers' masking rule; it is not a leaderboard score "
                     "and does not prove the hidden faults resemble catalogue faults."))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print("\nreferences:", json.dumps({k: round(v['mean_dti'], 5) for k, v in ref_rows.items()}))
    for r in rows[:12]:
        print(f"  {r['field']:26s} bar={r['bar']:<5} r={r['radius']}  DTI={r['mean_dti']:.5f}")
    print(f"\nwrote {args.out} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
