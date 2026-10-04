"""Format tests: the published submission requirements, checked on real bytes."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems34 import raster  # noqa: E402

SAMPLE = Path("/tmp/work/data/sample_submission.tif")


def _toy():
    v = np.zeros((raster.GRID["height"], raster.GRID["width"]), np.float32)
    v[100:110, 100:110] = 1.0
    v[200:210, 200:210] = 0.4
    v[0, 0] = np.float32("nan")          # a nodata cell, as in the official rasters
    return v


def test_write_and_verify_round_trip(tmp_path):
    receipt = raster.write_submission(tmp_path / "t.tif", _toy(), outside="nan")
    assert receipt["format_ok"] is True
    assert receipt["bands"] == 1 and receipt["dtype"] == "float32"
    assert receipt["crs"] == "EPSG:32611" and receipt["res"] == [100.0, 100.0]
    assert receipt["bounds"] == list(raster.GRID["bounds"])
    assert receipt["min"] == 0.0 and receipt["max"] == 1.0
    assert receipt["all_in_unit_interval"] is True
    assert receipt["n_nonfinite"] == 1 and receipt["convention"] == "nan-outside"
    assert receipt["nodata_is_nan"] is True
    # one stray NaN cell is legal but is *not* the official nodata pattern
    assert receipt["sample_convention"] is False


def test_zero_outside_convention_is_available(tmp_path):
    receipt = raster.write_submission(tmp_path / "z.tif", _toy(), outside="zero")
    assert receipt["format_ok"] is True
    assert receipt["n_nonfinite"] == 0 and receipt["convention"] == "none"
    assert receipt["nodata_is_none"] is True


def test_wrong_shape_is_refused(tmp_path):
    with pytest.raises(ValueError):
        raster.write_submission(tmp_path / "bad.tif", np.zeros((10, 10), np.float32))


def test_out_of_range_input_is_clipped_not_written(tmp_path):
    v = _toy()
    v[300, 300] = -5.0
    v[301, 301] = 7.0
    receipt = raster.write_submission(tmp_path / "clip.tif", v, outside="nan")
    assert receipt["format_ok"] is True
    assert receipt["min"] == 0.0 and receipt["max"] == 1.0


@pytest.mark.skipif(not SAMPLE.exists(), reason="official sample submission not staged")
def test_footprint_matches_the_official_sample():
    """The valid-data region must equal the organizers' own sample's."""
    a = raster.footprint(SAMPLE)
    assert a.shape == (raster.GRID["height"], raster.GRID["width"])
    assert int(a.sum()) == 5_167_373
    assert int((~a).sum()) == raster.NONFINITE_N


@pytest.mark.skipif(not SAMPLE.exists(), reason="official sample submission not staged")
def test_sample_submission_is_the_catalogue_not_an_empty_raster():
    """docs/irregularities.md IR-34-01, as a test that fails if the file changes."""
    s = raster.read(SAMPLE)
    lab = raster.read("/tmp/work/data/labels.tif")
    pos = s > 0
    assert int(pos.sum()) == 60_988
    assert np.array_equal(pos, lab == 1)
