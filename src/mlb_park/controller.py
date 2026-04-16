"""Controller — ViewModel + build_view entry point for the MLB HR Park Factor Explorer.

This module is the ONLY place that composes pipeline output for the UI. It
must NOT import `streamlit` (D-23) — UI concerns live in app.py / views/.

Import discipline (D-02): every runtime dependency flows through
`mlb_park.pipeline`. VerdictMatrix is imported from geometry as a TYPE
reference only (annotations / isinstance); no runtime composition escapes
the pipeline package boundary.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Union

from mlb_park.pipeline import (  # noqa: F401 — re-exports primed for Plan 04-02
    CURRENT_SEASON,
    HREvent,
    HitData,
    MLBAPIError,
    PipelineError,
    compute_verdict_matrix,
    extract_hrs,
    hr_event_to_hit_data,
    load_all_parks,
    load_parks,
)

# Type-only import; runtime calls go through mlb_park.pipeline (D-02 spirit).
from mlb_park.geometry.verdict import VerdictMatrix

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViewModel:
    """Immutable projection of a (team, player, venue) selection (D-06).

    Consumed by Phase 4/5 UI code. `to_dict()` produces a JSON-safe snapshot
    suitable for `st.json`, debugging dumps, and URL-state serialization.
    """

    season: int
    team_id: int
    team_abbr: str
    player_id: int
    player_name: str
    venue_id: int
    venue_name: str
    player_home_venue_id: int
    events: tuple[HREvent, ...]
    plottable_events: tuple[HREvent, ...]
    verdict_matrix: VerdictMatrix | None
    clears_selected_park: tuple[bool, ...]
    totals: dict[str, Union[int, float]]
    errors: tuple[PipelineError, ...]

    def to_dict(self) -> dict:
        """Return a JSON-safe snapshot of this view model.

        Layout:
          - Scalars pass through as-is.
          - events/plottable_events → list[dict] (HREvent fields; game_date → ISO string).
          - verdict_matrix → summary {shape, venue_ids, cleared_per_park} (D-24 scope;
            no to_dict() on the geometry dataclass). None when matrix is absent.
          - errors → list[{game_pk, endpoint, message}].
          - tuples → lists.
        """
        return {
            "season": int(self.season),
            "team_id": int(self.team_id),
            "team_abbr": str(self.team_abbr),
            "player_id": int(self.player_id),
            "player_name": str(self.player_name),
            "venue_id": int(self.venue_id),
            "venue_name": str(self.venue_name),
            "player_home_venue_id": int(self.player_home_venue_id),
            "events": [_hr_event_to_dict(ev) for ev in self.events],
            "plottable_events": [_hr_event_to_dict(ev) for ev in self.plottable_events],
            "verdict_matrix": _verdict_matrix_summary(self.verdict_matrix),
            "clears_selected_park": [bool(x) for x in self.clears_selected_park],
            "totals": dict(self.totals),
            "errors": [_pipeline_error_to_dict(e) for e in self.errors],
        }


def _hr_event_to_dict(ev: HREvent) -> dict:
    """Project an HREvent into a JSON-safe dict (date → ISO string)."""
    return {
        "game_pk": int(ev.game_pk),
        "game_date": ev.game_date.isoformat(),
        "opponent_abbr": str(ev.opponent_abbr),
        "inning": int(ev.inning),
        "half_inning": str(ev.half_inning),
        "play_idx": int(ev.play_idx),
        "distance_ft": ev.distance_ft,
        "coord_x": ev.coord_x,
        "coord_y": ev.coord_y,
        "launch_speed": ev.launch_speed,
        "launch_angle": ev.launch_angle,
        "has_distance": bool(ev.has_distance),
        "has_coords": bool(ev.has_coords),
        "has_launch_stats": bool(ev.has_launch_stats),
        "is_itp": bool(ev.is_itp),
    }


def _pipeline_error_to_dict(err: PipelineError) -> dict:
    return {
        "game_pk": None if err.game_pk is None else int(err.game_pk),
        "endpoint": str(err.endpoint),
        "message": str(err.message),
    }


def _verdict_matrix_summary(matrix: VerdictMatrix | None) -> dict | None:
    """Build the RESEARCH.md-prescribed summary shape (D-24 controller scope).

    Returns None when no matrix is present (UI can render "no HRs / no parks").
    """
    if matrix is None:
        return None
    venue_ids = [int(v) for v in matrix.venue_ids.tolist()]
    cleared_per_park = {
        int(vid): int(matrix.cleared[:, j].sum())
        for j, vid in enumerate(venue_ids)
    }
    return {
        "shape": list(matrix.cleared.shape),
        "venue_ids": venue_ids,
        "cleared_per_park": cleared_per_park,
    }


# ---------------------------------------------------------------------------
# Selector helpers — sorted_teams / sorted_hitters (UX-01, UX-02, D-12/13).
# ---------------------------------------------------------------------------


def sorted_teams(teams: list[dict]) -> list[dict]:
    """Return teams sorted by `name` ascending (UX-01).

    Pure: no mutation of the input list. Missing `name` sorts as empty string
    (shouldn't happen with the real StatsAPI response but keeps the function
    total for defensive callers).
    """
    return sorted(teams, key=lambda t: t.get("name", ""))


def hr_of(entry: dict) -> int:
    """Extract `person.stats[0].splits[0].stat.homeRuns`, defaulting to 0 (D-13)."""
    try:
        stats = entry.get("person", {}).get("stats") or []
        if not stats or not isinstance(stats[0], dict):
            return 0
        splits = stats[0].get("splits") or []
        if not splits or not isinstance(splits[0], dict):
            return 0
        raw = splits[0].get("stat", {}).get("homeRuns", 0)
        return int(raw or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


def name_of(entry: dict) -> str:
    """Extract `person.fullName`, defaulting to empty string."""
    return entry.get("person", {}).get("fullName", "") or ""


def sorted_hitters(roster: list[dict]) -> list[dict]:
    """Filter non-pitchers, then sort by (-homeRuns, fullName) (D-12, D-13).

    Missing `position` key ⇒ WARNING logged per-entry, entry treated as
    non-pitcher (defensive — the real StatsAPI always returns position, but
    a malformed fixture / roster row shouldn't crash the UI).
    Missing `homeRuns` ⇒ sorts as 0.
    """
    out: list[dict] = []
    for entry in roster:
        position = entry.get("position") or {}
        if not position:
            log.warning(
                "Roster entry missing position; treating as non-pitcher: %s",
                name_of(entry) or "<unknown>",
            )
        if position.get("type") == "Pitcher":
            continue
        out.append(entry)
    return sorted(out, key=lambda e: (-hr_of(e), name_of(e)))


# ---------------------------------------------------------------------------
# Plan 04-02 Task 2 — build_view composition + private helpers.
# ---------------------------------------------------------------------------


def _clears_for_venue(matrix: VerdictMatrix, venue_id: int) -> tuple[bool, ...]:
    """Return per-plottable-HR bool: does this HR clear the fence at `venue_id`?

    Alignment is POSITIONAL (D-08): result[i] corresponds to plottable_events[i]
    — the same order fed into compute_verdict_matrix. The j-th column of
    matrix.cleared holds the per-HR verdicts for matrix.venue_ids[j].

    Raises KeyError when venue_id is not present (load_all_parks normally
    returns all 30 MLB venues, so this indicates a configuration bug).
    """
    venue_ids_list = matrix.venue_ids.tolist()
    try:
        j = venue_ids_list.index(int(venue_id))
    except ValueError as e:
        raise KeyError(f"venue_id {venue_id} not in verdict matrix") from e
    return tuple(bool(x) for x in matrix.cleared[:, j])


def _compute_totals(
    events: tuple,
    plottable: tuple,
    matrix: VerdictMatrix | None,
) -> dict[str, Union[int, float]]:
    """Build the 5-key totals dict (D-09).

    Keys: total_hrs, plottable_hrs, avg_parks_cleared, no_doubters, cheap_hrs.
      - avg_parks_cleared: mean over plottable HRs of parks-cleared; 0.0 when empty.
      - no_doubters:       count of plottable HRs that clear ALL parks.
      - cheap_hrs:         count of plottable HRs that clear <= 5 parks.
    """
    n_plottable = len(plottable)
    if matrix is None or n_plottable == 0:
        return {
            "total_hrs": len(events),
            "plottable_hrs": n_plottable,
            "avg_parks_cleared": 0.0,
            "no_doubters": 0,
            "cheap_hrs": 0,
        }
    # Per-HR count of parks cleared (sum across columns).
    per_hr_cleared = matrix.cleared.sum(axis=1)  # shape (n_hrs,)
    n_parks = matrix.cleared.shape[1]
    return {
        "total_hrs": len(events),
        "plottable_hrs": n_plottable,
        "avg_parks_cleared": float(per_hr_cleared.mean()),
        "no_doubters": int((per_hr_cleared == n_parks).sum()),
        "cheap_hrs": int((per_hr_cleared <= 5).sum()),
    }


def build_view(
    team_id: int,
    player_id: int,
    venue_id: int,
    *,
    season: int | None = None,
    api: Any = None,
) -> ViewModel:
    """Compose services + Phase 3 pipeline + Phase 2 verdict matrix into a ViewModel.

    Pure (D-23): no streamlit, no session_state. Not cached (D-22) — caching
    belongs at the services boundary where cache keys are URL-scoped.

    Args:
        team_id: MLB team.id (integer).
        player_id: MLB person.id of the selected hitter.
        venue_id: MLB venue.id of the selected stadium.
        season: 4-digit year; defaults to config.CURRENT_SEASON.
        api: module-like object exposing get_teams, get_team_hitting_stats,
             get_game_log, get_game_feed, load_all_parks, MLBAPIError.
             Defaults to mlb_park.services.mlb_api (imported lazily to keep
             this function test-friendly under dependency injection).

    Returns:
        A fully-populated ViewModel. `verdict_matrix is None` iff no HR has
        both distance and spray coords (D-10). `errors` carries per-feed
        failures from the pipeline unchanged (D-27).
    """
    if api is None:
        # Local import — never at module top — so controller.py stays
        # streamlit-free when the caller injects a stub.
        from mlb_park.services import mlb_api as api  # noqa: F811
    if season is None:
        season = CURRENT_SEASON

    # 1. Selection-context lookups (team/player/venue display fields).
    teams = api.get_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if team is None:
        raise ValueError(f"team_id {team_id} not found in get_teams() response")
    team_abbr = team.get("abbreviation", "") or ""
    player_home_venue_id = int(team.get("venue", {}).get("id", 0) or 0)

    roster = api.get_team_hitting_stats(team_id, season)
    player_entry = next(
        (e for e in roster if e["person"]["id"] == player_id), None
    )
    if player_entry is None:
        raise ValueError(f"player_id {player_id} not found in roster for team {team_id}")
    player_name = player_entry["person"].get("fullName", "") or ""

    parks_dict = api.load_all_parks()
    venue_name = parks_dict.get(venue_id, {}).get("name", "") or ""

    # 2. Run Phase 3 HR-extraction pipeline (injected api is reused).
    result = extract_hrs(player_id, season=season, api=api)
    events = result.events
    errors = result.errors

    # 3. Filter plottable events (D-07) — need both distance AND coords.
    plottable = tuple(ev for ev in events if ev.has_distance and ev.has_coords)

    # 4. Build verdict matrix (D-10: None when no plottable HRs).
    matrix: VerdictMatrix | None
    if plottable:
        hit_data_list = [hr_event_to_hit_data(ev) for ev in plottable]
        # Defensive: the plottable filter above already excludes events that
        # would adapt to None, but keep the guard in case the adapter evolves.
        hit_data_list = [h for h in hit_data_list if h is not None]
        park_objs = load_parks(parks_dict)  # D-02: imported via pipeline re-export
        matrix = compute_verdict_matrix(hit_data_list, park_objs)
    else:
        matrix = None

    # 5. clears_selected_park — per-plottable-HR verdict for the selected venue (D-08).
    clears = _clears_for_venue(matrix, venue_id) if matrix is not None else ()

    # 6. totals dict (D-09).
    totals = _compute_totals(events, plottable, matrix)

    return ViewModel(
        season=season,
        team_id=team_id,
        team_abbr=team_abbr,
        player_id=player_id,
        player_name=player_name,
        venue_id=venue_id,
        venue_name=venue_name,
        player_home_venue_id=player_home_venue_id,
        events=events,
        plottable_events=plottable,
        verdict_matrix=matrix,
        clears_selected_park=clears,
        totals=totals,
        errors=errors,
    )


__all__ = [
    "ViewModel",
    "build_view",
    "sorted_teams",
    "sorted_hitters",
    "hr_of",
    "name_of",
]
