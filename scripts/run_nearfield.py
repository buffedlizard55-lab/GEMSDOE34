"""Near-field hypothesis comparison on the contiguous-run instrument."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems34 import fields, geology, holdout, nearfield, raster  # noqa: E402

BARS = [0.03, 0.06, 0.10, 0.20]
RADII = [2, 3, 4, 5, 6]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/work/data")
    ap.add_argument("--out", default="docs/data/nearfield.json")
    ap.add_argument("--splits", type=int, default=4)
    ap.add_argument("--seeds", type=int, default=400)
    ap.add_argument("--free-mode", default="exact", choices=["exact", "dilate3"])
    args = ap.parse_args()

    d = Path(args.data)
    cat = raster.read(d / "labels.tif") == 1
    h5 = None
    tf = d / "training_features.tif"
    if tf.exists():
        import rasterio
        need = {"tc": 5, "tmi_hg": 2, "iso_grav_anom_hg": 17, "iso_grav_anom_vg": 10,
                "tmi_vg": 8, "geod_2ndinv": 3, "geod_shearrate": 6,
                "geod_dilaterate": 7, "det_elev": 11, "cond_surf": 16}
        feats = {}
        with rasterio.open(tf) as s:
            for k, b in need.items():
                a = s.read(b + 1).astype(np.float32)
                a[~np.isfinite(a)] = 0.0
                feats[k] = a
        h5 = fields.h5_geophysical_lineaments(feats)
        del feats
        print("H5 lineament energy ready", flush=True)

    t0 = time.time()
    acc: dict = {}
    refs: dict = {}
    meta = []
    for split in range(args.splits):
        truth, visible = nearfield.cut_runs(cat, n_seeds=args.seeds, seed=1000 + split)
        free = visible if args.free_mode == "exact" else geology.dilate(visible, 3)
        meta.append(dict(split=split, n_truth=int(truth.sum()),
                         n_visible=int(visible.sum())))
        sk = geology.skeleton(visible)
        cos, sin = geology.local_strike(sk)
        flds = {
            "H1_near_catalogue": fields.h1_near_catalogue(visible, sigma_px=6.0),
            "H2_tip_extrapolation": fields.h2_tip_extrapolation(visible),
            "H3_gap_linkage": fields.h3_gap_linkage(visible),
            "H4_parallel_strands": fields.h4_parallel_strands(visible),
        }
        flds["H2+H3+H4"] = fields.composite((flds["H2_tip_extrapolation"], 1.0),
                                            (flds["H3_gap_linkage"], 1.0),
                                            (flds["H4_parallel_strands"], 1.0))
        flds["H1+H2+H3+H4"] = fields.composite((flds["H1_near_catalogue"], 1.0),
                                               (flds["H2+H3+H4"], 1.0))
        if h5 is not None:
            flds["H5_geophysical_lineaments"] = h5
            flds["H5+H234"] = fields.composite((h5, 1.0), (flds["H2+H3+H4"], 1.0))
            flds["ALL"] = fields.composite((h5, 1.0), (flds["H1+H2+H3+H4"], 1.0))

        refs.setdefault("R0_empty", []).append(
            nearfield.score(np.zeros_like(cat, np.float32), truth, free)["dti"])
        refs.setdefault("R1_carpet_only", []).append(
            nearfield.score(nearfield.carpet(free), truth, free)["dti"])
        refs.setdefault("R2_carpet_plus_visible_ring", []).append(
            nearfield.score(np.where(geology.dilate(visible, 2), np.float32(1),
                                     nearfield.carpet(free)), truth, free)["dti"])

        for name, fld in flds.items():
            tau = holdout.smooth(fld)
            for bar in BARS:
                for rad in RADII:
                    em = holdout.emission(free, tau, bar, use_free=True,
                                          spacing=rad, free_mask=free)
                    acc.setdefault((name, bar, rad), []).append(
                        nearfield.score(em, truth, free)["dti"])
                    del em
            del tau
        del flds
        print(f"  split {split} done ({time.time()-t0:.0f}s)", flush=True)

    rows = [dict(field=n, bar=b, radius=r, mean_dti=float(np.mean(v)),
                 per_split=[round(x, 6) for x in v])
            for (n, b, r), v in acc.items()]
    rows.sort(key=lambda x: -x["mean_dti"])
    ref_rows = {k: dict(mean_dti=float(np.mean(v)), per_split=[round(x, 6) for x in v])
                for k, v in refs.items()}
    out = dict(protocol=dict(splits=args.splits, seeds=args.seeds,
                             free_mode=args.free_mode, bars=BARS, radii=RADII),
               splits=meta, references=ref_rows, results=rows, top=rows[:20],
               note=("Near-field instrument: truth = contiguous removed runs of "
                     "mapped trace, free mask = visible catalogue. Measures recovery "
                     "of unmapped geometry adjacent to mapped traces under the "
                     "organizers' masking rule. Not a leaderboard score."))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print("\nreferences:", {k: round(v["mean_dti"], 5) for k, v in ref_rows.items()})
    for r in rows[:15]:
        print(f"  {r['field']:26s} bar={r['bar']:<5} r={r['radius']}  DTI={r['mean_dti']:.5f}")
    print(f"\nwrote {args.out} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
