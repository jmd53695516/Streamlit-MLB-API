"""Tests for dynamic season constants in config.py.

Phase 7 Plan 01 — SEASON-01/SEASON-02.
Verifies that CURRENT_SEASON is dynamically computed and AVAILABLE_SEASONS
exports exactly 5 years in descending order starting from CURRENT_SEASON.
"""
from __future__ import annotations

import datetime
import unittest.mock

import pytest

from mlb_park.config import AVAILABLE_SEASONS, CURRENT_SEASON, _current_season


def test_current_season_is_int() -> None:
    """CURRENT_SEASON must be an int (not a str or float)."""
    assert isinstance(CURRENT_SEASON, int)


def test_current_season_matches_now() -> None:
    """CURRENT_SEASON matches the expected year for the current date."""
    now = datetime.datetime.now()
    expected = now.year if now.month >= 3 else now.year - 1
    assert CURRENT_SEASON == expected


def test_available_seasons_length() -> None:
    """AVAILABLE_SEASONS must contain exactly 5 elements."""
    assert len(AVAILABLE_SEASONS) == 5


def test_available_seasons_starts_with_current() -> None:
    """AVAILABLE_SEASONS[0] must equal CURRENT_SEASON."""
    assert AVAILABLE_SEASONS[0] == CURRENT_SEASON


def test_available_seasons_descending() -> None:
    """AVAILABLE_SEASONS must be a contiguous descending range from CURRENT_SEASON."""
    assert AVAILABLE_SEASONS == list(range(CURRENT_SEASON, CURRENT_SEASON - 5, -1))


def test_current_season_january_returns_prior_year() -> None:
    """_current_season() returns year - 1 in January (off-season)."""
    fake_dt = datetime.datetime(2026, 1, 15, 12, 0, 0)
    with unittest.mock.patch("mlb_park.config.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = fake_dt
        result = _current_season()
    assert result == 2025


def test_current_season_march_returns_same_year() -> None:
    """_current_season() returns the same year in March (season started)."""
    fake_dt = datetime.datetime(2026, 3, 27, 12, 0, 0)
    with unittest.mock.patch("mlb_park.config.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = fake_dt
        result = _current_season()
    assert result == 2026
