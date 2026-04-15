"""Calibration fit + committed-constant reproducibility tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from mlb_park.geometry.calibration import (
    CALIB_OX,
    CALIB_OY,
    CALIB_S,
    CALIB_RESIDUALS_FT,
    extract_hrs_from_feeds,
    fit_calibration,
)


def test_judge_fixtures_extract_six_hrs(judge_hrs):
    """Sanity: we have exactly 6 HR records from the 5 feed fixtures."""
    assert len(judge_hrs) == 6
    for hr in judge_hrs:
        assert {"gamePk", "coordX", "coordY", "totalDistance"} <= hr.keys()
        assert hr["totalDistance"] > 300.0


def test_extract_hrs_helper_matches_conftest(fixtures_dir, judge_hrs):
    """calibration.extract_hrs_from_feeds mirrors the conftest loader."""
    via_helper = extract_hrs_from_feeds(fixtures_dir)
    assert len(via_helper) == len(judge_hrs)
    # Same gamePk multiset
    assert sorted(h["gamePk"] for h in via_helper) == sorted(h["gamePk"] for h in judge_hrs)


def test_fit_reproduces_committed_constants(judge_hrs):
    """Re-fitting from fixtures must reproduce the committed CALIB_* within tolerance."""
    X = [h["coordX"] for h in judge_hrs]
    Y = [h["coordY"] for h in judge_hrs]
    D = [h["totalDistance"] for h in judge_hrs]
    Ox, Oy, s, residuals = fit_calibration(X, Y, D)
    assert abs(Ox - CALIB_OX) < 0.01, f"Ox drifted: {Ox} vs {CALIB_OX}"
    assert abs(Oy - CALIB_OY) < 0.01, f"Oy drifted: {Oy} vs {CALIB_OY}"
    assert abs(s - CALIB_S) < 0.001, f"s drifted: {s} vs {CALIB_S}"
    # All per-HR residuals sub-foot on the fitted params.
    assert all(r < 1.0 for r in residuals), f"residuals too large: {residuals}"
    # Committed residual vector has 6 entries matching the 6 HRs.
    assert len(CALIB_RESIDUALS_FT) == 6


def test_fit_beats_community_seed(judge_hrs):
    """Seeded (125,199,2.35) underfits by ~5%; fitted must be < 1ft max-residual."""
    X = [h["coordX"] for h in judge_hrs]
    Y = [h["coordY"] for h in judge_hrs]
    D = [h["totalDistance"] for h in judge_hrs]
    _, _, _, fitted_residuals = fit_calibration(X, Y, D)
    assert max(fitted_residuals) < 1.0


def test_geometry_imports_are_io_free():
    """D-01: mlb_park.geometry.* must not import requests, streamlit, or touch I/O at import time."""
    for name in list(sys.modules):
        if name.startswith("mlb_park.geometry"):
            del sys.modules[name]
    import mlb_park.geometry  # noqa: F401
    import mlb_park.geometry.calibration  # noqa: F401
    # Walk source files; grep for forbidden imports.
    root = Path(mlb_park.geometry.__file__).parent
    forbidden = ("import requests", "from requests", "import streamlit", "from streamlit")
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{py} imports {needle!r}"


def test_scipy_not_in_requirements():
    """D-07 / RESEARCH.md: scipy is NOT a pinned runtime dep."""
    req = Path("requirements.txt").read_text(encoding="utf-8")
    lower = req.lower()
    # Allow comments like "# scipy considered & rejected"; forbid actual pins.
    for line in lower.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        assert not stripped.startswith("scipy"), f"scipy must not be pinned: {line!r}"
