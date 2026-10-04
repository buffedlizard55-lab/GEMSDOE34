#!/usr/bin/env python3
"""Build the GEMSDOE34 weekly candidate: the *screened curvature-ridge core* emission.

Two things changed this session, both from measurement rather than taste.
See ``docs/method.md`` for the full derivation and ``docs/data/*.json`` for the
numbers.

1. A new geological field, H6 (docs/hypotheses.md): a signed step edge of the
   top-of-crustal magnetic source depth surface (``tc``), gated to basin fill
   and corroborated by independent potential-field lineaments.  It targets
   buried basin-margin faults -- a class the Quaternary surface-fault catalogue
   cannot carry, and the class geothermal exploration actually targets.

2. A much smaller payload.  The group's live record contains ten submissions
   that are *pure isolated-dot emissions* (every connected component exactly
   one pixel).  Across those ten, the owner-reported live score is a perfectly
   monotone decreasing function of the number of dots (Spearman rho = -1.000)
   over a 5.5x range in dot count and a 3.1x range in score:

       37,654 dots -> 0.2778     91,533 -> 0.1352
       40,199       -> 0.2708    103,347 -> 0.1294
       44,090       -> 0.2600    155,021 -> 0.1193
       60,069       -> 0.2477    206,895 -> 0.0904
       69,281       -> 0.1839

   Two within-family controls say the same thing with the field held fixed:
   44,090 dots (0.2600) beats its own 60,069-dot superset (0.2477), and pruning
   2,545 dots from the 40,199-dot file raised it to 0.2778.  So the group has
   been on the wrong side of the emission-mass optimum for its whole history,
   and every artifact it ever scored is *bigger* than its best one.

   The metric says why.  With unit-valued dots and total kernel credit T,
   DTI = T / (0.2 n + 0.8 K) exactly, so one more dot improves the score only
   while its realised credit exceeds 0.2 * DTI.  At the live operating point
   that bar is ~0.056, and the group's marginal dots are below it.  This script
   therefore emits a deliberately small, high-confidence core.

   The reduction is chosen conservatively.  The 10-point series fits a
   power-law marginal-credit curve whose optimum lies far below any observed
   point, but nothing in the record constrains the curve below 37,654 dots, and
   the world's best score (0.3262) argues against the extreme reading.  Three
   estimators of the gain from cutting 37,654 -> 24,000 bracket it at
   +0.01 (same-rule within-family slope), +0.04 (prune-slope) and +0.11
   (power-law fit).  All positive, so the move is taken; the magnitude is
   flagged as unvalidated.  See docs/limitations.md.

3. The free catalogue carpet stays: the organizers confirmed on the official
   forum that known USGS/INGENIOUS fault pixels are excluded from the penalty
   terms, and the group proved it live -- the 8GEMSDOE Hedge-v2 artifact is a
   strict superset of the 0.1563 ens12 artifact with 54,533 extra pixels, all of
   them on that mask, and it scored exactly 0.1563.  Mass there is weakly
   dominant.

Run:
  python scripts/build_submission_h6.py --data data --out docs/downloads
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, sobel

from gems34 import fields, geology, holdout, raster, registry
from gems34.metric import score_fast

BAND = {"mag_anom": 0, "rtp": 1, "tmi_hg": 2, "geod_2ndinv": 3,
        "iso_grav_anom_slope": 4, "tc": 5, "geod_shearrate": 6,
        "geod_dilaterate": 7, "tmi_vg": 8, "deq_n100a15": 9,
        "iso_grav_anom_vg": 10, "det_elev": 11, "iso_grav_anom": 12, "tmi": 13,
        "depth_to_base_surf": 14, "ieq_n100a15": 15, "cond_surf": 16,
        "iso_grav_anom_hg": 17, "det_elev_slope": 18}

SENTINEL = 1.0e30   # training_features.tif stores nodata as -3.402823466e38

# Weights of the shipped composite.
#
# These are the OUTCOME of the pre-registered screen in
# scripts/run_field_screen.py (docs/data/field-screen.json), not a taste choice.
# Eight mechanisms were each reduced to the same 28,000-dot emission shape and
# scored on the proxy truth (USGS SGMC faults the competition catalogue does not
# carry) across eleven spatial blocks.  Result, pooled T at 28,000 dots:
#
#     curv_det_elev    5454.7   <-- winner (multi-scale |l1-l2| of det_elev)
#     H6_basin_step    3437.9   <-- the new hypothesis, second, and rejected
#     H5_lineament10   3236.5
#     H1_wide_shell    2676.4
#     H2_tips          2670.6
#     contrast_tmi_iso 2535.7
#     H4_wide_parallel 2282.8
#     step_basement    545.7
#
# Forward selection then added H2 (tip extrapolation) for a further +0.0004 --
# inside noise, but the screen selected it, so it is carried at low weight.
# H6 is *not* shipped: naming a hypothesis is not evidence for it, and this one
# lost to a simpler field by 37 % on the blocked instrument.
W_CURV, W_H2 = 0.85, 0.15

# Payload size and packing.  See the module docstring: every isolated-dot
# artifact this group has ever scored is larger than its best one.
TARGET_PAYLOAD = 28000
SPACING_PX = 3          # == the metric kernel radius R = 300 m; tiles are the
                        # vectorised form of greedy non-maximum suppression
COLLAR_PX = 3           # dots inside the catalogue's 300 m collar are charged
                        # in full and, measured live, earn nothing


def _valid(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    return np.isfinite(a) & (np.abs(a) < SENTINEL)


def _norm01(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    x = np.where(_valid(x), x, np.nan)
    if not np.isfinite(x).any():
        return np.zeros(x.shape, np.float32)
    lo, hi = np.nanpercentile(x, 1.0), np.nanpercentile(x, 99.0)
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        return np.zeros(x.shape, np.float32)
    return np.nan_to_num(np.clip((x - lo) / (hi - lo), 0.0, 1.0),
                         nan=0.0).astype(np.float32)


def _clean(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    return np.where(_valid(a), a, 0.0)


def step_edge(surface: np.ndarray, sigma: float) -> np.ndarray:
    s = gaussian_filter(_clean(surface), sigma)
    return _norm01(np.hypot(sobel(s, axis=1), sobel(s, axis=0)))


def anisotropy(gray: np.ndarray, sigma: float) -> np.ndarray:
    """Contrast-invariant lineament energy |l1 - l2| of the structure tensor."""
    g = _clean(gray)
    gy, gx = sobel(g, axis=0), sobel(g, axis=1)
    jxx = gaussian_filter(gx * gx, sigma)
    jyy = gaussian_filter(gy * gy, sigma)
    jxy = gaussian_filter(gx * gy, sigma)
    tr = jxx + jyy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - (jxx * jyy - jxy * jxy), 0.0))
    return _norm01(2.0 * disc)


def build_fields(bands: dict[str, np.ndarray], cat: np.ndarray) -> dict[str, np.ndarray]:
    """The screened composite: detrended-elevation curvature ridge + tip extension.

    ``curv`` is the contrast-invariant anisotropy |l1 - l2| of the structure
    tensor of the detrended-elevation band (band 12), taken at three scales.  A
    fault scarp is a ridge in the detrended surface and a lineament in the
    potential fields; taking the anisotropy rather than the gradient makes the
    detector fire on bright-vs-dark structure equally, which is what a scarp
    crossing a slope looks like compared with a scarp crossing a flat.

    ``H6`` and the other six arms are still computed so the rejected hypotheses
    stay reproducible; they are simply not combined into the shipped field.
    """
    # --- H6: concealed basin-margin step ---------------------------------
    fill = 0.5 * _norm01(bands["depth_to_base_surf"]) + 0.5 * _norm01(bands["cond_surf"])
    step = np.maximum.reduce([step_edge(bands["tc"], s) for s in (1.5, 3.0, 6.0)])
    magn = np.maximum.reduce([anisotropy(bands["tmi_hg"], 2.0),
                              anisotropy(bands["tmi_vg"], 2.0)])
    grav = anisotropy(bands["iso_grav_anom_hg"], 2.0)
    corroboration = np.sqrt(np.maximum(magn * grav, 0.0))
    h6 = _norm01(np.cbrt(np.maximum(step, 0.0) ** 2 * np.maximum(corroboration, 0.0))
                 * (0.25 + 0.75 * fill))
    # --- H5: multi-band potential-field lineament energy ------------------
    h5 = fields.h5_geophysical_lineaments(bands)
    # --- surface term: multi-scale curvature ridge of detrended elevation --
    curv = np.maximum.reduce([anisotropy(bands["det_elev"], s) for s in (1.5, 3.0, 6.0)])
    # --- H2: tip continuation (second forward-selection member) -----------
    h2 = fields.h2_tip_extrapolation(cat)
    comp = _norm01(W_CURV * _norm01(curv) + W_H2 * _norm01(h2))
    return {"h6": h6, "h5": h5, "curv": curv, "h2": h2, "composite": comp}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="docs/downloads")
    ap.add_argument("--history", nargs="*", default=[])
    ap.add_argument("--registry", default="registry/history.json")
    ap.add_argument("--name", default="g34-3-screen-curvridge-core28k")
    ap.add_argument("--target", type=int, default=TARGET_PAYLOAD)
    ap.add_argument("--spacing", type=int, default=SPACING_PX)
    ap.add_argument("--collar", type=int, default=COLLAR_PX)
    ap.add_argument("--no-carpet", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    d = Path(args.data)
    labels = raster.read(d / "labels.tif")
    cat = labels == 1
    footprint = np.isfinite(raster.read(d / "sample_submission.tif"))

    import rasterio
    bands = {}
    with rasterio.open(d / "training_features.tif") as s:
        for k in BAND:
            a = s.read(BAND[k] + 1).astype(np.float32)
            a[~np.isfinite(a)] = 0.0
            a[np.abs(a) >= 1.0e30] = 0.0
            bands[k] = a
    print(f"grid {cat.shape}  catalogue {int(cat.sum()):,}  footprint {int(footprint.sum()):,}")

    print("building fields ...", flush=True)
    f = build_fields(bands, cat)
    del bands
    comp = f["composite"].copy()
    comp[~footprint] = 0.0
    comp[cat] = 0.0                                   # free carpet handles these

    dcat = geology.distance_to(cat)
    payload_zone = footprint & ~cat & (dcat > args.collar)
    tau = holdout.smooth(comp)
    tau[~payload_zone] = 0.0

    # ---- greedy non-maximum suppression at the kernel radius ------------
    # The competition kernel has R = 3 px, and the group's live record says the
    # packing that pays is *isolated* dots at the largest separation that still
    # leaves no gap wider than the kernel.  On the integer grid the admissible
    # offsets are |d| >= sqrt(8) ~ 2.83 px: everything closer (1, sqrt2, 2,
    # sqrt5) wastes credit, everything farther leaves holes.  A per-tile
    # arg-max does NOT enforce that -- two neighbouring tiles can pick adjacent
    # pixels -- which is exactly the defect measured on the first pass of this
    # script (mean component size 1.70 px instead of 1.00).  So: walk the
    # candidates in descending tau and block the 21 sub-2.83 px offsets around
    # every accepted dot.
    s = float(args.spacing)
    c = float(np.floor(s / np.sqrt(2.0)))          # 2 for s = 3 -> |d| >= 2.83
    offs = [(dy, dx) for dy in range(-int(c) - 1, int(c) + 2)
            for dx in range(-int(c) - 1, int(c) + 2)
            if np.hypot(dy, dx) < s]
    offs = np.array(offs, dtype=np.int32)
    print(f"packing: min separation {s} px, suppression disk |d| < {s} "
          f"({len(offs)} offsets)")

    h, w = tau.shape
    cand_y, cand_x = np.nonzero(tau > 0)
    cand_v = tau[cand_y, cand_x]
    order = np.argsort(-cand_v, kind="stable")
    pool = min(order.size, max(400_000, args.target * 60))
    order = order[:pool]
    blocked = np.zeros((h, w), bool)
    accepted = np.empty((args.target, 2), np.int32)
    n_acc = 0
    oy, ox = offs[:, 0], offs[:, 1]
    for i in order:
        y, x = int(cand_y[i]), int(cand_x[i])
        if blocked[y, x]:
            continue
        accepted[n_acc] = (y, x)
        n_acc += 1
        yy, xx = y + oy, x + ox
        good = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
        blocked[yy[good], xx[good]] = True
        if n_acc >= args.target:
            break
    payload = np.zeros_like(cat)
    accepted = accepted[:n_acc]
    payload[accepted[:, 0], accepted[:, 1]] = True
    print(f"payload dots selected: {n_acc:,} (target {args.target:,}, "
          f"candidate pool {order.size:,})")

    emission = np.where(payload, 1.0, 0.0)
    if not args.no_carpet:
        emission = np.where(cat, 1.0, emission)
    n_tot = int((emission > 0).sum())
    n_free = int(((emission > 0) & cat).sum())
    n_pay = n_tot - n_free
    print(f"emission: {n_tot:,} px = {n_free:,} free carpet + {n_pay:,} payload")

    # ---- validation (necessary, not sufficient: see docs/irregularities.md
    # IR-34-IG-01 -- neither offline instrument ranks the live scores) --------
    val = {}
    inst = holdout.Instrument(labels, n_blocks=4, buffer_px=3, free_mode="exact")
    pay_only = np.where(payload, 1.0, 0.0)
    for tag, arr in (("payload_only", pay_only), ("with_carpet", emission)):
        sc = [inst.score_against(arr, fl.truth, fl.free)["dti"] for fl in inst.folds]
        val[f"catalogue_blocked_mean_{tag}"] = float(np.mean(sc))
        if tag == "payload_only":
            val["catalogue_blocked_folds"] = [float(x) for x in sc]
    print(f"  catalogue-blocked mean DTI : payload_only="
          f"{val['catalogue_blocked_mean_payload_only']:.5f}  "
          f"with_carpet={val['catalogue_blocked_mean_with_carpet']:.5f}")
    print("  (the carpet inflates this instrument by construction: every fold's "
          "held-out truth is a catalogue subset, so carpeting the catalogue "
          "covers it -- the payload-only column is the honest one)")

    sgmc_path = Path("/tmp/hist/sgmc_g30.tif")
    if sgmc_path.exists():
        sgmc = raster.read(sgmc_path)
        pnf = (sgmc > 0) & (dcat > 3) & footprint
        for tag, arr in (("payload_only", pay_only), ("with_carpet", emission)):
            c = score_fast(arr, pnf, cat)
            val[f"pnf_dti_{tag}"] = float(c["dti"])
        val["pnf_pixels"] = int(pnf.sum())
        print(f"  proxy-new-fault DTI (SGMC) : payload_only="
              f"{val['pnf_dti_payload_only']:.5f}  "
              f"with_carpet={val['pnf_dti_with_carpet']:.5f}")

    from scipy import ndimage
    lab_n, ncomp = ndimage.label(payload, structure=np.ones((3, 3)))
    sizes = np.bincount(lab_n.ravel())[1:] if ncomp else np.array([0])
    nn = None
    ys, xs = np.nonzero(payload)
    if ys.size > 1:
        from scipy.spatial import cKDTree
        pts = np.column_stack([ys, xs])
        dd, _ = cKDTree(pts).query(pts, k=2)
        nn = float(np.median(dd[:, 1]))
    val.update(payload_components=int(ncomp),
               payload_mean_component_size=float(sizes.mean()) if ncomp else 0.0,
               payload_median_nn_px=nn)
    print(f"  payload {n_pay:,} px in {ncomp:,} components, mean "
          f"{val['payload_mean_component_size']:.3f} px, median NN {nn}")

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"gems34-{args.name}-{stamp}"
    tif = out / f"{stem}.tif"
    receipt = raster.write_submission(tif, np.where(emission > 0, 1.0, 0.0),
                                      outside="nan")
    print(f"wrote {tif}  format_ok={receipt['format_ok']} "
          f"values[{receipt['min']},{receipt['max']}] n_nonfinite={receipt['n_nonfinite']}")

    gate = None
    hist = args.history or (["/tmp/hist"] if Path("/tmp/hist").exists() else [])
    if hist or Path(args.registry).exists():
        try:
            gate = registry.gate(tif, history=hist, catalogue=cat,
                                 registry=args.registry)
            print(f"gate verdict: {gate.get('verdict')}  "
                  f"max_payload_dice={gate.get('max_payload_dice')}")
        except TypeError:
            gate = {"note": "registry.gate signature differs; run scripts/run_gate.py"}

    audit = dict(
        name=stem, generated_utc=datetime.now(timezone.utc).isoformat(),
        hypothesis="H6 concealed basin-margin step + H5 potential-field lineaments "
                   "+ detrended-elevation curvature ridge (docs/hypotheses.md)",
        emission_rule=dict(value=1.0, spacing_px=args.spacing, target_payload=args.target,
                           collar_px=args.collar, carpet=not args.no_carpet),
        counts=dict(total=n_tot, free_carpet=n_free, payload=n_pay),
        validation=val, format=receipt, gate=gate,
        evidence_class=["DERIVED", "PROXY"],
        caveat=("No organizer score exists for this file. Both offline instruments "
                "are reported; docs/data/calibration.json measures that neither ranks "
                "the group's 27 live-scored artifacts (rho = -0.11 / +0.12), so this "
                "validation is a sanity floor, not a prediction. The payload-size "
                "reduction is supported by a 10-point monotone live relationship "
                "(rho = -1.000) whose extrapolation below 37,654 dots is unconstrained "
                "by any observation."),
    )
    (out / f"{stem}-audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out / f'{stem}-audit.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
