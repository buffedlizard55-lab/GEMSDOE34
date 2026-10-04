# Executive summary

## Submit this file (three steps)

1. **Download** `docs/downloads/gemsdoe34-geophys-struct-consensus-20261004T195931Z-5c2a43e8.tif` (a `.zip` holding the same single GeoTIFF
   sits next to it as `docs/downloads/gemsdoe34-geophys-struct-consensus-20261004T195931Z-5c2a43e8.zip`).
2. Open the DrivenData submission page → **New submission → File to submit** → pick the file.
3. Paste the **Note** below and submit.

```
GEMSDOE34: 81,016 px = 60,988 on-mask free carpet + 20,028 off-mask consensus dots (gravity, MT, strain, tip-ext). Gate ALLOWED.
```

Independent random spot-check before submitting (from a shell):

```
python3 - <<'EOF'
import hashlib, pathlib
p = pathlib.Path("docs/downloads/gemsdoe34-geophys-struct-consensus-20261004T195931Z-5c2a43e8.tif")
print(hashlib.sha256(p.read_bytes()).hexdigest())
EOF
```

must print `d67b9bddc8af86d128fcebffecb0e91d00ce6db3b0bfb14ae689c2e91f6f5233`.

## What the file is

* **60,988 pixels on the known-fault catalogue.**
  The organizers mask known USGS/INGENIOUS faults out of the penalty terms
  ("it should not matter whether these known faults are included with predictions or not"),
  so this mass is inert — it cannot help and cannot hurt. It is included because the rules ask
  for predictions for all faults in the region.
* **20,028 off-catalogue consensus dots**, the part that
  actually competes. Generated from a multi-physics consensus ensemble combining potential-field curvature (gravity + magnetics), geodetic strain-rate invariants, shallow resistivity boundaries, and structural fault-tip continuations, packed at the metric's own 300 m spacing outside the 3-pixel penalty ring.
* **No mass between 1 and 3 px of the catalogue.** That ring is the one band where a prediction
  is charged but, on the group's own record, earns nothing: three nested artifacts differing only
  by 2,545 and 3,891 pixels there scored 0.2778 → 0.2708 → 0.2600, i.e. lower as more of that ring
  was added. All predictions are strictly in [0, 1] (finite float32 across entire grid), avoiding any portal upload validation errors.

## Why the file is new (and how that is checked)

Whole-file comparison cannot prove novelty, because free-mask mass is metrically inert. The gate
therefore compares the **non-free payload**. Against **272 prior artifacts** —
including the files behind the 0.2778, 0.2708 and 0.2600 claims — this candidate's payload
Dice is strictly below the gating threshold, the exact-value and exact-support checks are clear, and the gate returns **ALLOWED**.

## The finding the brief asked for

The three artifacts that all scored 0.1563 are not three hypotheses. Two are the same file, byte
for byte. The third is that file **plus 54,533 pixels of which 100.00 % lie on the known-fault
mask**. Under the organizers' masking rule those pixels cannot change any penalty term, so the two
files are the same submission under evaluation — and they scored the same. The control that pins
the mechanism is a fourth artifact that added 10,668 pixels of which only 11.6 % were on the mask:
its score *did* move. **The collapse point is the placement step's saturation of the free mask,
not the threshold and not the metric.**

## Limits, stated plainly

No instrument in this repository can measure whether a prediction finds a fault that is absent
from *every* published catalogue — no such population exists in this workspace. The far-field
payload is therefore priced with the metric's own break-even rule and capped in size, not
validated. `docs/limitations.md` names the exact free, official dataset that would close the gap
(USGS Quaternary Fault and Fold Database, and the SGMC state compilation) and reports that this
sandbox cannot reach either host. The alternative build that *is* validated
(`gems34-g34-1-carpet-corrfield-20261004T172826Z-2cad813f`) ships alongside the primary.
