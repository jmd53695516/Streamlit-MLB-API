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


def _raw_team_hitting_stats(team_id: int, season: int) -> list[dict]:
    """Hydrated roster with single-season hitting stats (D-11 amended).

    Phase 7 D-03/D-04: fullSeason for past seasons, active for current.

    URL: /teams/{team_id}/roster?rosterType={active|fullSeason}
         &season={season}
         &hydrate=person(stats(type=statsSingleSeason,season={season},group=hitting))

    Returns the `roster` list (possibly empty — D-15).
    """
    assert isinstance(team_id, int) and isinstance(season, int), \
        "team_id and season must be int (SSRF guard, T-4-01)"
    from mlb_park.config import CURRENT_SEASON
    roster_type = "active" if season == CURRENT_SEASON else "fullSeason"
    hydrate = f"person(stats(type=statsSingleSeason,season={season},group=hitting))"
    resp = _get(
        f"{BASE_URL_V1}/teams/{team_id}/roster",
        params={"rosterType": roster_type, "season": season, "hydrate": hydrate},
    )
    return resp.get("roster", [])


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
def get_game_log_current(person_id: int, season: int) -> list[dict]:
    """Hitter game log, current season. TTL 1h."""
    return _raw_game_log(person_id, season)


@st.cache_data(ttl="30d", show_spinner=False)
def get_game_log_historical(person_id: int, season: int) -> list[dict]:
    """Hitter game log, past seasons. TTL 30d (immutable)."""
    return _raw_game_log(person_id, season)


def get_game_log(person_id: int, season: int) -> list[dict]:
    """Dispatcher: 30d TTL for past seasons, 1h for current (D-05/D-06)."""
    from mlb_park.config import CURRENT_SEASON
    if season < CURRENT_SEASON:
        return get_game_log_historical(person_id, season)
    return get_game_log_current(person_id, season)


@st.cache_data(ttl=TTL_GAMELOG, show_spinner=False)
def get_team_hitting_stats_current(team_id: int, season: int) -> list[dict]:
    """Active roster hydrated with per-player single-season hitting stats, current season. TTL 1h (D-14).

    D-11 amended endpoint — the `person.stats[0].splits[0].stat.homeRuns`
    field on each roster entry is the season HR total used by the Phase 4
    player selector's HR-descending sort.
    """
    return _raw_team_hitting_stats(team_id, season)


@st.cache_data(ttl="30d", show_spinner=False)
def get_team_hitting_stats_historical(team_id: int, season: int) -> list[dict]:
    """Full-season roster hydrated with per-player single-season hitting stats, past season. TTL 30d."""
    return _raw_team_hitting_stats(team_id, season)


def get_team_hitting_stats(team_id: int, season: int) -> list[dict]:
    """Dispatcher: 30d TTL for past seasons, existing TTL for current (D-05/D-06)."""
    from mlb_park.config import CURRENT_SEASON
    if season < CURRENT_SEASON:
        return get_team_hitting_stats_historical(team_id, season)
    return get_team_hitting_stats_current(team_id, season)


@st.cache_data(ttl="30d", max_entries=200, show_spinner=False)
def get_game_feed(game_pk: int) -> dict:
    """Live/completed game feed with play-by-play + hitData. TTL 30d (immutable after completion). Max 200 entries (OOM guard, D-discretion)."""
    return _raw_game_feed(game_pk)


@st.cache_data(ttl=TTL_VENUE, show_spinner=False)
def get_venue(venue_id: int) -> dict:
    """Venue metadata with fieldInfo + location. TTL 24h."""
    return _raw_venue(venue_id)


# ---------------------------------------------------------------------------
# Disk-backed venue cache — survives process restarts.
# ROADMAP criterion #3: cold 2nd run loads all 30 venues from disk, no network.
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically. Safe on Windows (os.replace is atomic, PEP 428).

    Writes to a tempfile in the SAME directory (same filesystem required for
    atomic rename), then os.replace. Partial-write corruption is impossible:
    either the whole file is the old version, or the whole file is the new one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_all_parks() -> dict[int, dict]:
    """Return {venue_id: venue_dict} for all 30 team home venues.

    First run: fetches teams, dedups home venue IDs, calls get_venue for each,
    writes atomically to data/venues_cache.json.

    Subsequent runs (file age < 30 days): reads from disk, zero network calls.
    This is what makes ROADMAP criterion #3 pass.

    Stale (file age >= 30 days): rebuilds from the API.
    """
    if VENUES_FILE.exists():
        age_days = (time.time() - VENUES_FILE.stat().st_mtime) / 86400.0
        if age_days < VENUES_STALE_DAYS:
            raw = json.loads(VENUES_FILE.read_text(encoding="utf-8"))
            # JSON keys are always strings; convert back to int.
            return {int(k): v for k, v in raw.items()}
    # Rebuild from API.
    teams = get_teams()
    venue_ids = sorted({t["venue"]["id"] for t in teams})
    result = {vid: get_venue(vid) for vid in venue_ids}
    # Persist with string keys (JSON requires string keys).
    _atomic_write_json(VENUES_FILE, {str(k): v for k, v in result.items()})
    return result
