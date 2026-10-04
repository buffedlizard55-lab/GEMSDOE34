#!/usr/bin/env python3
"""Bound the hidden truth mass M and the credit elasticity, from nesting alone.

The metric identity for a binary submission with off-mask mass ``n`` and hidden
truth of effective mass ``M`` is

    s = T / (0.2*T + 0.2*F + 0.8*M),      FN_w = M - T  exactly

so, writing F ~ n (every off-mask dot that misses the truth is charged 1.0),

    T(s, n, M) = s * (0.2*n + 0.8*M) / (1 - 0.2*s)

That gives every live-scored artifact an implied credit ``T`` as a function of
the single unknown ``M``.  Two hard constraints then bound ``M`` without ever
seeing the truth:

  1. **Monotonicity.**  If A's dot set is a subset of B's then T_A <= T_B,
     because every truth pixel covered by A is covered by B.
  2. **Saturation.**  T_i <= M: no submission can earn more credit than there
     are truth pixels.

This script finds every nested pair in the fetched corpus, solves the resulting
interval for M, and then reports the local credit elasticity
b = (dT/dn) * (n/T) of each nested increment -- the number that decides the
optimal dot budget.

Usage
-----
    python scripts/run_mass_and_elasticity.py --corpus /tmp/corpus --data data \
        --out docs/data/mass-and-elasticity.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import rasterio

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from gems34 import ledger as ledger_mod  # noqa: E402


def implied_T(s: float, n: float, M: float) -> float:
    return s * (0.2 * n + 0.8 * M) / (1.0 - 0.2 * s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="/tmp/corpus")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default=None)
    ap.add_argument("--containment", type=float, default=0.999,
                    help="fraction of the smaller set that must sit inside the larger")
    a = ap.parse_args()

    lab = rasterio.open(os.path.join(a.data, "labels.tif")).read(1)
    inside = lab != -1
    cat = lab > 0

    rows = []
    for r in ledger_mod.resolve(a.corpus):
        if not r["file"]:
            continue
        arr = rasterio.open(os.path.join(a.corpus, r["file"])).read(1)
        A = (np.nan_to_num(arr, nan=0.0) > 0) & inside & ~cat
        n = int(A.sum())
        if n == 0:
            continue
        rows.append(dict(repo=r["repo"], claim=r["claim"], score=float(r["score"]),
                         file=r["file"], sha256=r["sha256"], n=n, mask=A))

    # ---- nested pairs -------------------------------------------------------
    pairs = []
    for i, ri in enumerate(rows):
        for j, rj in enumerate(rows):
            if i == j or ri["sha256"] == rj["sha256"]:
                continue
            if ri["n"] >= rj["n"]:
                continue
            inter = int((ri["mask"] & rj["mask"]).sum())
            frac = inter / ri["n"]
            if frac >= a.containment:
                pairs.append(dict(small=ri["claim"], big=rj["claim"],
                                  small_repo=ri["repo"], big_repo=rj["repo"],
                                  n_small=ri["n"], n_big=rj["n"],
                                  containment=round(frac, 5),
                                  s_small=ri["score"], s_big=rj["score"]))

    # ---- interval for M -----------------------------------------------------
    lo, hi = 1.0, 1e7
    binding = []
    grid = np.geomspace(10.0, 1e6, 20000)
    ok = np.ones_like(grid, bool)
    for p in pairs:
        d = implied_T(p["s_big"], p["n_big"], grid) - implied_T(p["s_small"], p["n_small"], grid)
        bad = d < 0
        if bad.any():
            m = grid[bad].min()
            hi = min(hi, m)
            binding.append(dict(kind="monotonicity", pair=f"{p['small']} -> {p['big']}",
                                bound="M <=", value=round(float(m), 1)))
        ok &= ~bad
    for r in rows:
        # T(s,n,M) <= M  ->  s*(0.2n+0.8M) <= M*(1-0.2s)
        #                 ->  M*(1-0.2s-0.8s) >= 0.2*s*n  ->  M >= 0.2*s*n/(1-s)
        need = 0.2 * r["score"] * r["n"] / (1.0 - r["score"])
        if need > lo:
            lo = need
            binding.append(dict(kind="saturation", pair=r["claim"], bound="M >=",
                                value=round(float(need), 1)))

    print(f"{len(rows)} live-scored artifacts, {len(pairs)} nested pairs "
          f"(containment >= {a.containment})")
    for p in pairs:
        print(f"  {p['n_small']:7d} -> {p['n_big']:7d}  ({p['containment']:.4f})  "
              f"{p['s_small']:.4f} -> {p['s_big']:.4f}   {p['small'][:44]}")

    print(f"\nfeasible M interval from nesting + saturation: [{lo:,.0f}, {hi:,.0f}]")
    if lo > hi:
        print("  ! EMPTY: the F ~ n approximation is falsified by the corpus")

    # ---- elasticity at the centre of the interval ---------------------------
    Ms = [lo, 0.5 * (lo + min(hi, 10 * lo)), hi] if hi > lo else [lo]
    elast = []
    for p in pairs:
        for M in Ms:
            Ta = implied_T(p["s_small"], p["n_small"], M)
            Tb = implied_T(p["s_big"], p["n_big"], M)
            dn = p["n_big"] - p["n_small"]
            dT = Tb - Ta
            elast.append(dict(M=round(M, 1), pair=f"{p['small']} -> {p['big']}",
                              n_small=p["n_small"], n_big=p["n_big"],
                              n_mid=round(0.5 * (p["n_small"] + p["n_big"])),
                              T_small=round(Ta, 1), dT=round(dT, 1), dn=dn,
                              marginal_credit=round(dT / dn, 4) if dn else None,
                              elasticity=round((dT / dn) * (0.5 * (p["n_small"] + p["n_big"]) / Ta), 4)
                              if dn and Ta > 0 else None))

    print("\nimplied credit and marginal credit of each nested increment:")
    hdr = f"{'M':>9} {'n_small':>8} {'n_big':>8} {'T_small':>9} {'dT':>8} {'dn':>7} {'dT/dn':>8} {'b':>7}"
    print(hdr); print("-" * len(hdr))
    for e in elast:
        print(f"{e['M']:9,.0f} {e['n_small']:8d} {e['n_big']:8d} "
              f"{e['T_small']:9.1f} {e['dT']:8.1f} {e['dn']:7d} "
              f"{e['marginal_credit'] or 0:8.4f} {e['elasticity'] or 0:7.3f}")

    out = dict(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        method="T(s,n,M) = s(0.2n+0.8M)/(1-0.2s); M bounded by subset-monotonicity and T<=M",
        approximation="F ~ n (every off-mask dot charged 1.0); exact when no dot lands within 300 m of truth",
        n_artifacts=len(rows), n_nested_pairs=len(pairs),
        M_lower=round(lo, 1), M_upper=round(hi, 1),
        binding_constraints=sorted(binding, key=lambda b: -b["value"])[:12],
        nested_pairs=pairs,
        elasticity=elast,
        rows=[{k: v for k, v in r.items() if k != "mask"} for r in rows],
    )
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump(out, open(a.out, "w"), indent=1)
        print("\nwrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
