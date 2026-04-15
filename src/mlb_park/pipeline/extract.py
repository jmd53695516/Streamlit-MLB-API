"""extract_hrs: player_id -> PipelineResult[HREvent]. Pure composition of
Phase 1 HTTP wrappers + Phase 2 HitData contract. No `requests`, no `streamlit`.

See .planning/phases/03-hr-pipeline/03-CONTEXT.md D-07..D-17 for the locked spec.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

from mlb_park.services import mlb_api as _default_api
from mlb_park.pipeline.events import HREvent, PipelineError, PipelineResult

logger = logging.getLogger(__name__)


def extract_hrs(
    player_id: int,
    season: int | None = None,
    *,
    api: Any = _default_api,
) -> PipelineResult:
    """Return all HRs hit by player_id in season as HREvent records.

    DATA-01: filters gameLog to stat.homeRuns >= 1 BEFORE fetching any feed.
    DATA-02: walks each HR game's feed for (batter.id == player_id,
             eventType == "home_run") plays.
    DATA-05: retains HRs with missing hitData via has_* flags (never drops).

    Args:
        player_id: MLB `person.id`.
        season: 4-digit year. If None, resolves to config.CURRENT_SEASON.
        api: module-like object exposing MLBAPIError, get_game_log,
             get_game_feed. Defaults to mlb_park.services.mlb_api.
             Tests inject a stub.

    Returns:
        PipelineResult with events sorted by (game_date, play_idx) ascending.

    Raises:
        api.MLBAPIError: if the initial get_game_log call fails (D-14).
    """
    if season is None:
        from mlb_park.config import CURRENT_SEASON
        season = CURRENT_SEASON

    # D-14: get_game_log failure propagates; no catch here.
    game_log = api.get_game_log(player_id, season)

    # D-07: DATA-01 filter BEFORE any feed fetch — stat.homeRuns >= 1.
    hr_rows = [r for r in game_log if int(r.get("stat", {}).get("homeRuns", 0)) >= 1]

    events: list[HREvent] = []
    errors: list[PipelineError] = []

    for row in hr_rows:
        game_pk = int(row["game"]["gamePk"])
        expected = int(row["stat"]["homeRuns"])
        batter_team_id = int(row["team"]["id"])
        try:
            feed = api.get_game_feed(game_pk)
        except api.MLBAPIError as exc:
            # D-14: catch per-feed, record, continue.
            errors.append(PipelineError(
                game_pk=game_pk, endpoint="game_feed", message=str(exc),
            ))
            continue

        matched = _walk_feed_for_hrs(feed, player_id, batter_team_id)

        # D-09: count mismatch = warning, NOT exception.
        if len(matched) != expected:
            logger.warning(
                "gameLog/feed HR count mismatch for gamePk=%d: expected %d, matched %d",
                game_pk, expected, len(matched),
            )

        events.extend(matched)

    # D-13: chronological (game_date, play_idx).
    events.sort(key=lambda e: (e.game_date, e.play_idx))

    return PipelineResult(
        events=tuple(events),
        errors=tuple(errors),
        season=season,
        player_id=player_id,
    )


# ---------------------------------------------------------------------
# Private helpers — D-18 suggests keeping in one file unless line count
# warrants a split. Implemented as module-level _-prefixed functions.
# ---------------------------------------------------------------------

def _walk_feed_for_hrs(
    feed: dict, player_id: int, batter_team_id: int,
) -> list[HREvent]:
    """Return HREvents for all plays matching (batter.id, eventType=='home_run').

    D-08: batter id + eventType are the ONLY filter (no review-reversal
    special-casing). `play_idx` is the enumerate index into allPlays
    (Pitfall 2 — do NOT use atBatIndex).
    """
    game_pk = int(feed["gamePk"])
    game_date = datetime.date.fromisoformat(
        feed["gameData"]["datetime"]["officialDate"]
    )
    opp_abbr = _opponent_abbr(feed, batter_team_id)

    all_plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", []) or []
    out: list[HREvent] = []
    for i, play in enumerate(all_plays):
        result = play.get("result") or {}
        if result.get("eventType") != "home_run":
            continue
        matchup = play.get("matchup") or {}
        batter = matchup.get("batter") or {}
        if batter.get("id") != player_id:
            continue

        about = play.get("about") or {}
        hit_data = _extract_hit_data(play)

        distance_ft = hit_data.get("totalDistance") if hit_data else None
        coords = (hit_data.get("coordinates") or {}) if hit_data else {}
        coord_x = coords.get("coordX")
        coord_y = coords.get("coordY")
        launch_speed = hit_data.get("launchSpeed") if hit_data else None
        launch_angle = hit_data.get("launchAngle") if hit_data else None

        has_distance = distance_ft is not None
        has_coords = (coord_x is not None) and (coord_y is not None)
        has_launch_stats = (launch_speed is not None) and (launch_angle is not None)
        is_itp = _detect_itp(result.get("description") or "")

        out.append(HREvent(
            game_pk=game_pk,
            game_date=game_date,
            opponent_abbr=opp_abbr,
            inning=int(about.get("inning", 0)),
            half_inning=str(about.get("halfInning", "")),
            play_idx=i,
            distance_ft=float(distance_ft) if has_distance else None,
            coord_x=float(coord_x) if coord_x is not None else None,
            coord_y=float(coord_y) if coord_y is not None else None,
            launch_speed=float(launch_speed) if launch_speed is not None else None,
            launch_angle=float(launch_angle) if launch_angle is not None else None,
            has_distance=has_distance,
            has_coords=has_coords,
            has_launch_stats=has_launch_stats,
            is_itp=is_itp,
        ))
    return out


def _extract_hit_data(play: dict) -> dict | None:
    """Return the hitData dict for a play, or None.

    D-10: prefer `playEvents[-1].hitData`; fall back to the last playEvent
    with non-null hitData. Return None if no playEvent carries hitData.
    """
    events = play.get("playEvents") or []
    if not events:
        return None
    last = events[-1]
    if isinstance(last.get("hitData"), dict):
        return last["hitData"]
    for e in reversed(events):
        if isinstance(e.get("hitData"), dict):
            return e["hitData"]
    return None


def _detect_itp(description: str) -> bool:
    """D-11: case-insensitive substring match on 'inside-the-park'."""
    return "inside-the-park" in description.lower()


def _opponent_abbr(feed: dict, batter_team_id: int) -> str:
    """Resolve opponent 3-letter abbr from feed.gameData.teams.

    Pitfall 3: 'opponent' is relative to batter's team id, not to home/away.
    Fallback chain: abbreviation -> teamName -> clubName -> name -> '???'.
    """
    teams = feed.get("gameData", {}).get("teams", {}) or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    opp = away if home.get("id") == batter_team_id else home
    return (
        opp.get("abbreviation")
        or opp.get("teamName")
        or opp.get("clubName")
        or opp.get("name")
        or "???"
    )


# ---------------------------------------------------------------------
# D-06: HREvent -> HitData adapter. Phase 2's compute_verdict_matrix
# consumes HitData; the pipeline emits HREvents. HRs missing distance or
# coords return None (caller splits events into "verdict-eligible" vs
# "emit-only" buckets — Phase 4's responsibility).
# ---------------------------------------------------------------------

from mlb_park.geometry.verdict import HitData


def hr_event_to_hit_data(ev: HREvent) -> HitData | None:
    """Adapter: HREvent -> HitData for the geometry layer (D-06).

    Returns None when the event lacks `distance_ft` or coords — these HRs
    are still emitted by extract_hrs (DATA-05) but cannot participate in
    the verdict matrix.
    """
    if not (ev.has_distance and ev.has_coords):
        return None
    return HitData(
        distance_ft=ev.distance_ft,
        coord_x=ev.coord_x,
        coord_y=ev.coord_y,
        identifier=(ev.game_pk, ev.play_idx),
    )
