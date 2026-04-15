"""HTTP wrappers over statsapi.mlb.com — the ONLY module that imports `requests`.

Public API: 5 @st.cache_data-decorated functions, one per endpoint, plus
`load_all_parks()` for the disk-backed 30-venue cache.

Private API: 5 `_raw_*` helpers (un-cached) used by scripts/record_fixtures.py
so fixture capture never reads stale cached data.

Source shapes verified live against statsapi.mlb.com on 2026-04-14
(see .planning/phases/01-foundation-api-layer/01-RESEARCH.md §Endpoint Contracts).
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import requests
import streamlit as st

from mlb_park.config import (
    BASE_URL_V1,
    BASE_URL_V11,
    HTTP_TIMEOUT,
    USER_AGENT,
    TTL_TEAMS,
    TTL_ROSTER,
    TTL_GAMELOG,
    TTL_VENUE,
    TTL_FEED,
    VENUES_FILE,
    VENUES_STALE_DAYS,
)


class MLBAPIError(RuntimeError):
    """Raised when a statsapi.mlb.com call fails after one retry."""


# Module-level Session — never passed as a cache arg (would hit UnhashableParamError).
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def _get(url: str, params: dict | None = None) -> dict:
    """Shared GET with timeout + one retry on RequestException.

    Never decorated with @st.cache_data — caching happens at the endpoint-function
    boundary so cache keys are typed by (endpoint, ids) not URL strings.
    """
    try:
        r = _session.get(url, params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        time.sleep(1.0)  # single retry after 1s
        try:
            r = _session.get(url, params=params, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e2:
            raise MLBAPIError(f"GET {url} failed after retry: {e2}") from e2


# ---------------------------------------------------------------------------
# Raw helpers — no caching. Used by scripts/record_fixtures.py.
# ---------------------------------------------------------------------------

def _raw_teams() -> list[dict]:
    return _get(f"{BASE_URL_V1}/teams", params={"sportId": 1})["teams"]


def _raw_roster(team_id: int) -> list[dict]:
    assert isinstance(team_id, int), "team_id must be int (SSRF guard)"
    return _get(
        f"{BASE_URL_V1}/teams/{team_id}/roster",
        params={"rosterType": "active"},
    )["roster"]


def _raw_game_log(person_id: int, season: int) -> list[dict]:
    assert isinstance(person_id, int) and isinstance(season, int), \
        "person_id and season must be int (SSRF guard)"
    resp = _get(
        f"{BASE_URL_V1}/people/{person_id}/stats",
        params={
            "stats": "gameLog",
            "group": "hitting",
            "season": season,
            "gameType": "R",  # D-09: regular season only
        },
    )
    stats = resp.get("stats", [])
    if not stats:
        return []
    return stats[0].get("splits", [])


def _raw_game_feed(game_pk: int) -> dict:
    assert isinstance(game_pk, int), "game_pk must be int (SSRF guard)"
    # Note: v1.1 (not v1) — RESEARCH.md §Endpoint Contracts #4
    return _get(f"{BASE_URL_V11}/game/{game_pk}/feed/live")


def _raw_venue(venue_id: int) -> dict:
    assert isinstance(venue_id, int), "venue_id must be int (SSRF guard)"
    return _get(
        f"{BASE_URL_V1}/venues/{venue_id}",
        params={"hydrate": "location,fieldInfo"},
    )["venues"][0]


# ---------------------------------------------------------------------------
# Public cached wrappers — EXACTLY FIVE, one per endpoint, per ROADMAP #2.
# ---------------------------------------------------------------------------

@st.cache_data(ttl=TTL_TEAMS, show_spinner=False)
def get_teams() -> list[dict]:
    """All 30 MLB teams. TTL 24h."""
    return _raw_teams()


@st.cache_data(ttl=TTL_ROSTER, show_spinner=False)
def get_roster(team_id: int) -> list[dict]:
    """Active roster for a team. TTL 6h."""
    return _raw_roster(team_id)


@st.cache_data(ttl=TTL_GAMELOG, show_spinner=False)
def get_game_log(person_id: int, season: int) -> list[dict]:
    """Hitter game log, regular season only. TTL 1h."""
    return _raw_game_log(person_id, season)


@st.cache_data(ttl=TTL_FEED, show_spinner=False)
def get_game_feed(game_pk: int) -> dict:
    """Live/completed game feed with play-by-play + hitData. TTL 7d."""
    return _raw_game_feed(game_pk)


@st.cache_data(ttl=TTL_VENUE, show_spinner=False)
def get_venue(venue_id: int) -> dict:
    """Venue metadata with fieldInfo + location. TTL 24h."""
    return _raw_venue(venue_id)
