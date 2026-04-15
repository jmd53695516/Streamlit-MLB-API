"""Shared pytest fixtures for Phase 2 tests — read-only access to tests/fixtures/ JSON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
JUDGE_PERSON_ID = 592450


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def judge_hrs(fixtures_dir: Path) -> list[dict]:
    """Return the 6 Judge HR records extracted from feed_*.json fixtures.

    Each record: {"gamePk": int, "coordX": float, "coordY": float, "totalDistance": float}.
    """
    hrs: list[dict] = []
    for feed_path in sorted(fixtures_dir.glob("feed_*.json")):
        feed = json.loads(feed_path.read_text(encoding="utf-8"))
        game_pk = int(feed_path.stem.split("_")[1])
        all_plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", []) or []
        for play in all_plays:
            if play.get("result", {}).get("eventType") != "home_run":
                continue
            if play.get("matchup", {}).get("batter", {}).get("id") != JUDGE_PERSON_ID:
                continue
            hit_data = None
            for event in reversed(play.get("playEvents", []) or []):
                if isinstance(event.get("hitData"), dict):
                    hit_data = event["hitData"]
                    break
            if hit_data is None:
                continue
            coords = hit_data.get("coordinates", {}) or {}
            if "coordX" not in coords or "coordY" not in coords or "totalDistance" not in hit_data:
                continue
            hrs.append({
                "gamePk": game_pk,
                "coordX": float(coords["coordX"]),
                "coordY": float(coords["coordY"]),
                "totalDistance": float(hit_data["totalDistance"]),
            })
    return hrs


@pytest.fixture(scope="session")
def venues(fixtures_dir: Path) -> dict[int, dict]:
    """Return {venue_id: venue_dict} loaded from tests/fixtures/venue_*.json (30 venues)."""
    out: dict[int, dict] = {}
    for path in sorted(fixtures_dir.glob("venue_*.json")):
        venue = json.loads(path.read_text(encoding="utf-8"))
        out[int(venue["id"])] = venue
    return out
