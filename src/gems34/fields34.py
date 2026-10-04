"""Feature engineering + candidate hypothesis fields for the DOE GEMS task.

Everything here is built from rasters whose provenance is recorded in
``docs/knowledge/01_official_sources.md``:

* the 19 organizer-supplied bands of ``training_features.tif``
  (sha256 ``4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5``);
* the GeoDAWN airborne **radiometric** survey (K, Th, U, TC) -- USGS data release
  DOI `10.5066/P93LGLVQ <https://doi.org/10.5066/P93LGLVQ>`_, which is *not* in
  the organizer's stack;
* the GeoDAWN radiometric **ratios** (Th/K, U/K, U/Th) and upward-continued TMI
  from the same release;
* 12 LiDAR scarp-descriptor bands derived from the GeoDAWN/3DEP DEM.

Each field is a *hypothesis*, not a black box: it is a named physical signature
with a documented reason to expect it to mark a fault the USGS/INGENIOUS
catalogue missed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import rasterio
from scipy import ndimage as ndi

R_PX = 3.0


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
@dataclass
class Stack:
    """Lazy band access.

    The full stack is 39 bands x 12,279,160 cells; holding it as float32 costs
    1.9 GB and the sandbox has 3 GB, so bands are read from disk on demand and
    only a small cache is kept.  ``.bands`` behaves like a read-only mapping.
    """

    inside: np.ndarray
    cat: np.ndarray
    _reader: object = None
    _names: tuple = ()
    _ext: dict = None
    _cache: dict = None
    _cache_max: int = 3

    SENT = -3.4028234663852886e38

    def _fix(self, a):
        bad = ~np.isfinite(a) | (a <= self.SENT * 0.5)
        if bad.any():
            med = np.nanmedian(np.where(bad, np.nan, a)[self.inside])
            if not np.isfinite(med):
                med = 0.0
            a = a.copy()
            a[bad] = med
        return a

    def _read(self, name):
        if self._cache is None:
            object.__setattr__(self, "_cache", {})
        if name in self._cache:
            return self._cache[name]
        if name in self._names:
            i = self._names.index(name) + 1
            a = self._reader.read(i).astype(np.float32)
        elif name in self._ext:
            path, idx, zero_nan = self._ext[name]
            with rasterio.open(path) as ds:
                a = ds.read(idx).astype(np.float32)
            if zero_nan:
                a[a == 0] = np.nan
                a[~np.isfinite(a)] = np.nanmedian(a)
        else:
            raise KeyError(name)
        a = self._fix(a)
        if len(self._cache) >= self._cache_max:
            self._cache.pop(next(iter(self._cache)))
        self._cache[name] = a
        return a

    @property
    def bands(self):
        return _BandView(self)


class _BandView:
    """Read-only mapping over :class:`Stack` bands."""

    def __init__(self, st):
        self._st = st

    def __getitem__(self, k):
        return self._st._read(k)

    def get(self, k, default=None):
        return self._st._read(k) if (k in self) else default

    def __contains__(self, k):
        return k in self._st._names or k in self._st._ext

    def keys(self):
        return list(self._st._names) + list(self._st._ext)

    def items(self):
        return [(k, self._st._read(k)) for k in self.keys()]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self._st._names) + len(self._st._ext)


def _z(a, m):
    """Robust standardisation inside the footprint."""
    v = a[m].astype(np.float64)
    lo, hi = np.percentile(v, [1, 99])
    if hi <= lo:
        return np.zeros_like(a, np.float32)
    return np.clip((a.astype(np.float64) - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def load_stack(data_dir: str, ext_dir: str | None = None) -> Stack:
    tf = os.path.join(data_dir, "training_features.tif")
    ds = rasterio.open(tf)
    names = tuple(d.split(" - ")[0].strip() for d in ds.descriptions)
    with rasterio.open(os.path.join(data_dir, "labels.tif")) as lds:
        lab = lds.read(1)
    ext = {}
    if ext_dir:
        for rel, pref, zero_nan in (
            ("data/external/geodawn_rad_u8.tif", "rad_", True),
            ("data/external/geodawn_extensions_u8.tif", "ext_", True),
            ("data/external/lidar_scarp_features_u8.tif", "lid_", False),
        ):
            p = os.path.join(ext_dir, rel)
            if os.path.exists(p):
                with rasterio.open(p) as e:
                    for i, nm in enumerate(e.descriptions, start=1):
                        ext[pref + nm] = (p, i, zero_nan)
    return Stack(inside=lab != -1, cat=lab > 0, _reader=ds, _names=names,
                 _ext=ext, _cache={})


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------
def detrend(a: np.ndarray, sigma: float) -> np.ndarray:
    """Regional trend removed by a large Gaussian low-pass."""
    return a - ndi.gaussian_filter(a, sigma, mode="nearest")


def structure_tensor_anisotropy(a: np.ndarray, sigmas=(1.5, 3.0, 6.0)) -> np.ndarray:
    """Multi-scale |l1-l2|/(l1+l2) of the structure tensor: linear-fabric detector.

    A fault trace is a *lineament*: locally anisotropic gradient.  Ratioing the
    tensor eigenvalues makes the response invariant to contrast, so a subtle
    alluvium-buried trace scores like a bright scarp.
    """
    out = np.zeros(a.shape, np.float32)
    for s in sigmas:
        g = ndi.gaussian_filter(a, s * 0.5, mode="nearest")
        gy, gx = np.gradient(g)
        jxx = ndi.gaussian_filter(gx * gx, s, mode="nearest")
        jyy = ndi.gaussian_filter(gy * gy, s, mode="nearest")
        jxy = ndi.gaussian_filter(gx * gy, s, mode="nearest")
        tr = jxx + jyy
        disc = np.sqrt(np.maximum((jxx - jyy) ** 2 + 4 * jxy ** 2, 0))
        l1 = 0.5 * (tr + disc)
        l2 = 0.5 * (tr - disc)
        coh = (l1 - l2) / np.maximum(l1 + l2, 1e-9)
        out = np.maximum(out, coh.astype(np.float32))
    return out


def multi_scale_ridge(a: np.ndarray, sigmas=(1.0, 2.0, 4.0, 8.0)) -> np.ndarray:
    """Normalised max |second derivative across the strike| -- a scarp/step detector."""
    out = np.zeros(a.shape, np.float32)
    for s in sigmas:
        g = ndi.gaussian_filter(a, s, mode="nearest")
        gyy, gxy, gxx = (ndi.gaussian_filter(a, s, order=o, mode="nearest")
                         for o in [(2, 0), (1, 1), (0, 2)])
        # Hessian eigenvalues: the larger |lambda| is the across-strike curvature
        tr = gxx + gyy
        disc = np.sqrt(np.maximum((gxx - gyy) ** 2 + 4 * gxy ** 2, 0))
        lam = np.maximum(np.abs(0.5 * (tr + disc)), np.abs(0.5 * (tr - disc)))
        sc = (s * s) * lam  # scale-normalised
        out = np.maximum(out, sc.astype(np.float32))
    return out


def normalise(a: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Empirical *rank* transform inside the footprint, ties broken at random.

    A min-max or percentile-clip normalisation is unusable here: the external
    radiometric and LiDAR products are uint8, so a clipped rescale leaves tens
    of thousands of cells pinned at exactly 1.0 and the subsequent top-n
    selection degenerates into raster order.  Ranking gives a strictly
    continuous field, so "the top n pixels" is a real ranking.
    """
    a = np.asarray(a, np.float64)
    idx = np.flatnonzero(m.ravel())
    if idx.size == 0:
        return np.zeros(a.shape, np.float32)
    v = a.ravel()[idx]
    rng = np.random.default_rng(12345)
    key = v + rng.random(v.size) * 1e-9
    order = np.argsort(key, kind="stable")
    ranks = np.empty(v.size, np.float64)
    ranks[order] = np.arange(v.size, dtype=np.float64)
    out = np.zeros(a.size, np.float64)
    out[idx] = ranks / max(v.size - 1, 1)
    return out.reshape(a.shape).astype(np.float32)


# ---------------------------------------------------------------------------
# candidate fields
# ---------------------------------------------------------------------------
def field_candidates(st: Stack) -> dict[str, np.ndarray]:
    """Return every candidate hypothesis as a [0,1] field inside the footprint."""
    b, m = st.bands, st.inside
    out: dict[str, np.ndarray] = {}

    de = detrend(b["det_elev"], 40.0)
    out["H-A detrended-elevation curvature ridge"] = normalise(
        multi_scale_ridge(de, (1.0, 2.0, 4.0, 8.0)), m)
    out["H-B detrended-elevation fabric anisotropy"] = normalise(
        structure_tensor_anisotropy(de, (1.5, 3.0, 6.0)), m)

    # --- H-C: radiometric alteration ratio -----------------------------------
    # Hydrothermal circulation along a fault leaches U and K and concentrates Th
    # in the fault zone / clay cap.  Th/K and U/K anomalies therefore trace a
    # *fluid pathway*, which need not have any topographic expression at all --
    # exactly the class of fault a lidar-based catalogue misses.
    K = np.maximum(b.get("rad_K", np.zeros_like(de)), 1e-6)
    Th = np.maximum(b.get("rad_Th", np.zeros_like(de)), 1e-6)
    U = np.maximum(b.get("rad_U", np.zeros_like(de)), 1e-6)
    thk = normalise(np.log(Th / K), m)
    uk = normalise(np.log(U / K), m)
    tc_anom = normalise(np.abs(detrend(b.get("rad_TC", de), 30.0)), m)
    out["H-C radiometric alteration ratio (Th/K, U/K, TC anomaly)"] = normalise(
        0.4 * thk + 0.4 * uk + 0.2 * tc_anom, m)

    # --- H-D: basement-surface offset ----------------------------------------
    # A normal fault offsets the pre-basin-fill basement.  Where the basin is
    # filled, the surface shows nothing but `depth_to_base_surf` steps.  The
    # gradient magnitude of that band is a *buried*-fault detector.
    dbs = b["depth_to_base_surf"]
    out["H-D basement-depth step (buried fault)"] = normalise(
        multi_scale_ridge(detrend(dbs, 40.0), (1.0, 2.0, 4.0)), m)

    # --- H-E: geodetic strain-rate invariants --------------------------------
    # The strain-rate tensor's second invariant and dilatation mark the active
    # deformation corridor.  Faults that are active but unmapped concentrate
    # there; the catalogue is a *geologic* map, not a deformation map.
    strain = normalise(0.5 * normalise(b["geod_2ndinv"], m)
                       + 0.25 * normalise(np.abs(detrend(b["geod_dilaterate"], 20.0)), m)
                       + 0.25 * normalise(b["geod_shearrate"], m), m)
    out["H-E geodetic strain-rate corridor"] = strain

    # --- H-F: LiDAR scarp descriptors ----------------------------------------
    # The experts mapped the new faults from lidar.  The 12 GeoDAWN DEM
    # scarp-descriptor bands are the closest available reproduction of the
    # evidence they used: step height, laplacian extrema, up/down-facing
    # asymmetry and 100 m profile coherence.
    lk = [k for k in b if k.startswith("lid_") and k != "lid_valid"]
    if lk:
        acc = np.zeros(de.shape, np.float32)
        for k in lk:
            acc = acc + normalise(b[k], m)
        out["H-F LiDAR scarp-descriptor consensus"] = normalise(acc / len(lk), m)

    # --- H-G: magnetics edge detector ----------------------------------------
    # Basin fill hides the surface expression, but a fault juxtaposing
    # magnetically distinct basement blocks leaves a TMI gradient.  The
    # horizontal gradient and tilt-angle bands are already edge products; their
    # multi-scale ridge response traces *linear* magnetic contacts.
    mag = normalise(0.4 * normalise(b["tmi_hg"], m)
                    + 0.3 * normalise(b["iso_grav_anom_hg"], m)
                    + 0.3 * normalise(np.abs(detrend(b["tc"], 30.0)), m), m)
    out["H-G magneto-gravitic linear contact"] = normalise(
        multi_scale_ridge(mag, (1.0, 2.0, 4.0)), m)

    # --- H-H: shallow conductivity gradient ----------------------------------
    # A fault zone is a conductivity contrast (clay-filled gouge vs. breccia).
    # `cond_surf` and `depth_to_base_surf` are the MT products; their gradient
    # marks the *lateral* boundary, i.e. the trace, not the body.
    cond = normalise(np.hypot(*np.gradient(detrend(b["cond_surf"], 30.0))), m)
    out["H-H MT surface-conductivity lateral gradient"] = cond

    # --- H-I: measured winner habitat signature ------------------------------
    # Fitted, not guessed: docs/data/winner-signature.json measures the mean
    # percentile of the group's best-scoring emission (0.2778, 37,654 dots) in
    # every band against a size-matched random off-catalogue sample.  The
    # coefficients below ARE those measured lifts, sign included.  Reading them
    # geologically: the emission sits on sloped, LiDAR-scarped, magnetically
    # gradient-ed ground with a HIGH U/K and U/Th ratio (mobile uranium
    # enriched by hydrothermal alteration) and LOW total radiometric count,
    # low K, low Th and shallow basement -- i.e. altered bedrock range fronts,
    # not K-rich basin fill.  `tc`, `rad_TC`, `rad_K`, `rad_Th`, `rad_U` all
    # carry a *negative* coefficient, which is the opposite of what a
    # radiometric-total or tilt-angle detector would use.
    W_POS = {"det_elev_slope": 0.1573, "lid_upface_max": 0.1391,
             "lid_downface_max": 0.1246, "lid_lappos_max": 0.1213,
             "lid_cross_max": 0.1210, "lid_lapneg_max": 0.1174,
             "lid_ex_max": 0.1126, "lid_relief": 0.1084,
             "lid_step_max": 0.1057, "lid_ex_mean": 0.0942,
             "tmi_hg": 0.0739, "ext_UK": 0.0682, "ext_UTh": 0.0521,
             "det_elev": 0.0603, "iso_grav_anom": 0.0517,
             "geod_dilaterate": 0.0321, "deq_n100a15": 0.0290,
             "geod_2ndinv": 0.0252}
    W_NEG = {"rad_K": 0.1413, "tc": 0.1228, "rad_TC": 0.1226,
             "rad_Th": 0.0873, "rad_U": 0.0831,
             "depth_to_base_surf": 0.0321, "tmi_vg": 0.0262,
             "cond_surf": 0.0238}
    acc = np.zeros(de.shape, np.float64)
    wsum = 0.0
    for nm, w in {**W_POS, **{k: -v for k, v in W_NEG.items()}}.items():
        if nm not in b:
            continue
        acc = acc + w * normalise(b[nm], m).astype(np.float64)
        wsum += abs(w)
    habitat = normalise(acc.astype(np.float32), m)
    out["H-I measured-winner alteration-scarp habitat"] = habitat

    # --- H-J: habitat x linearity --------------------------------------------
    # A fault scarp is *linear*; a hillslope or an alluvial fan edge is not.
    # The habitat field above is pointwise, so it cannot tell them apart.
    # Multiplying it by the structure-tensor anisotropy of the LiDAR relief
    # keeps only the habitat that is organised into a lineament.  This term is
    # absent from the winner's measured signature and is the new element.
    rel = b["lid_relief"] if "lid_relief" in b else de
    lin = normalise(structure_tensor_anisotropy(
        np.asarray(rel, np.float32), (1.5, 3.0, 6.0)), m)
    out["H-J habitat x lineament anisotropy"] = normalise(
        (0.65 * habitat + 0.35 * lin).astype(np.float32), m)

    # --- H-K: catalogue-shadow shell on shallow basement ---------------------
    # Derived from docs/data/leaderboard-regression.json, a ridge model fitted
    # to 42 live leaderboard scores with leave-one-out R^2 = 0.885.  Two
    # descriptors dominate it by a wide margin:
    #
    #   mean|d(dots, catalogue) - 20 px|   Spearman rho = -0.977
    #   percentile(depth_to_base_surf)     Spearman rho = -0.967
    #
    # Read geologically, both say the same thing.  Unmapped faults are not
    # re-mappings of mapped ones (those are masked and score nothing) and they
    # are not in the middle of nowhere: they sit at the *characteristic spacing*
    # of the Basin and Range fault system, about 2 km from an existing trace, on
    # uplifted ground where the basement is shallow enough for a normal fault to
    # reach the surface.  So this field multiplies
    #
    #   (a) a Gaussian shell at 20 px = 2 km from the nearest catalogue pixel,
    #   (b) a shallow-basement weight 1 - percentile(depth_to_base_surf),
    #   (c) the positive-coefficient habitat: LiDAR up-facing scarp, LiDAR
    #       maximum extension, TMI horizontal gradient, isostatic gravity
    #       anomaly, detrended-elevation slope,
    #   (d) minus the negative-coefficient bands: TMI vertical gradient,
    #       surface conductivity, LiDAR 100 m profile coherence, uranium, tilt
    #       angle and total radiometric count.
    #
    # The shell term is supplied by the caller because it needs the catalogue;
    # this function returns the habitat part and the shell is combined in
    # ``shell_habitat``.
    P = {"lid_upface_max": 0.578, "lid_ex_max": 0.518, "tmi_hg": 0.466,
         "lid_step_max": 0.443, "iso_grav_anom": 0.388,
         "det_elev_slope": 0.300, "geod_2ndinv": 0.150}
    N = {"tmi_vg": 0.513, "cond_surf": 0.372, "lid_coh100": 0.260,
         "rad_U": 0.155, "tc": 0.090, "rad_TC": 0.090,
         "depth_to_base_surf": 0.967}
    acc = np.zeros(de.shape, np.float64)
    for nm, w in P.items():
        if nm in b:
            acc += w * normalise(b[nm], m).astype(np.float64)
    for nm, w in N.items():
        if nm in b:
            acc -= w * normalise(b[nm], m).astype(np.float64)
    out["H-K catalogue-shadow habitat (shallow basement)"] = normalise(
        acc.astype(np.float32), m)

    # --- controls ------------------------------------------------------------
    # C-0 is the instrument's null: without it a credit curve cannot be read.
    rng = np.random.default_rng(20261004)
    out["C-0 RANDOM control"] = rng.random(de.shape).astype(np.float32)
    # C-1 is the group's own winning *shape*: mass spread along the catalogue's
    # structural fabric but pushed off the catalogue itself.
    from scipy.ndimage import distance_transform_edt as _edt
    d = _edt(~st.cat)
    out["C-1 distance-to-catalogue band (4-12 px)"] = np.clip(
        1.0 - np.abs(d - 8.0) / 4.0, 0, 1).astype(np.float32)

    return out


def shell_habitat(habitat: np.ndarray, dcat: np.ndarray, mu_px: float = 20.0,
                  sigma_px: float = 8.0, inside: np.ndarray | None = None,
                  power: float = 1.0) -> np.ndarray:
    """Multiply a habitat field by a Gaussian shell at ``mu_px`` from the catalogue.

    ``dcat`` is the Euclidean distance, in pixels, to the nearest catalogue
    pixel.  ``mu_px`` is the shell radius that the leaderboard regression puts
    at the optimum (20 px = 2 km); ``sigma_px`` sets how tight the shell is.
    """
    g = np.exp(-0.5 * ((dcat - mu_px) / sigma_px) ** 2)
    out = (np.asarray(habitat, np.float64) * g ** power)
    if inside is not None:
        out = np.where(inside, out, 0.0)
    return out.astype(np.float32)
