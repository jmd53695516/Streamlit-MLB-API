"""MLB HR Park Factor Explorer — Streamlit entry point.

Wires Team -> Player -> Stadium selectors to controller.build_view and
renders spray chart + HR table.

Architecture (D-23): this module is the ONLY place that touches
st.session_state. controller.py + services/ stay UI-free.

No-fetch-before-selection (D-18): cold start fires only get_teams().
get_team_hitting_stats and load_all_parks fire only after their parent
selectbox is populated.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on sys.path for Streamlit Cloud (no editable install there)
_src = str(Path(__file__).resolve().parent.parent)
if _src not in sys.path:
    sys.path.insert(0, _src)

import pandas as pd
import streamlit as st

from mlb_park import chart, controller
from mlb_park.geometry.park import Park
from mlb_park.config import AVAILABLE_SEASONS, CURRENT_SEASON
from mlb_park.services.mlb_api import (
    get_teams,
    get_team_hitting_stats,
    load_all_parks,
)

# --- Session state keys (D-16) ---
# "team_id", "player_id", "venue_id" — bound via selectbox `key=`.


# --- Callbacks (D-17, D-20) ---
def _on_season_change() -> None:
    """D-02: season change resets ALL downstream selectors (full cascade)."""
    st.session_state["team_id"] = None
    st.session_state["player_id"] = None
    st.session_state["venue_id"] = None


def _on_team_change() -> None:
    """UX-04: team change nulls player_id and venue_id."""
    st.session_state["player_id"] = None
    st.session_state["venue_id"] = None


def _on_player_change() -> None:
    """UX-03: set venue_id to the selected team's home park.

    Defensive: if team_id is somehow None when this fires, no-op (don't
    crash and don't fetch). Real cascading flow always sets team_id first.
    """
    team_id = st.session_state.get("team_id")
    if team_id is None:
        return
    teams = get_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if team is None:
        return
    st.session_state["venue_id"] = team["venue"]["id"]


# --- Page chrome (UI-SPEC §Copywriting Contract) ---
st.set_page_config(page_title="MLB HR Park Explorer", layout="wide")
st.title("MLB HR Park Factor Explorer")


# --- Season selectbox (D-01: before Team; D-07: dynamic range; D-08: default=current year) ---
st.selectbox(
    "Season",
    options=AVAILABLE_SEASONS,
    key="season",
    index=0,
    help="Select a season to explore.",
    on_change=_on_season_change,
)

season = st.session_state.get("season", CURRENT_SEASON)


# --- Team selectbox (always populated — single eager fetch, D-18) ---
teams = controller.sorted_teams(get_teams())
team_options = [t["id"] for t in teams]
team_labels = {t["id"]: f'{t["name"]} ({t["abbreviation"]})' for t in teams}

st.selectbox(
    "Team",
    options=team_options,
    key="team_id",
    index=None,
    placeholder="Select a team…",
    help="Choose an MLB team to load its hitters.",
    format_func=lambda tid: team_labels.get(tid, str(tid)),
    on_change=_on_team_change,
)


# --- Player selectbox (only fetches when team is selected, D-18) ---
team_id = st.session_state.get("team_id")
if team_id is not None:
    roster = controller.sorted_hitters(
        get_team_hitting_stats(team_id, season)
    )
    player_options = [e["person"]["id"] for e in roster]
    player_labels = {
        e["person"]["id"]: (
            f'{e["person"]["fullName"]} — '
            f'{controller.hr_of(e)} HR'
        )
        for e in roster
    }
else:
    player_options = []
    player_labels = {}

st.selectbox(
    "Player",
    options=player_options,
    key="player_id",
    index=None,
    placeholder="Select a player…",
    help="Non-pitchers on this team, sorted by season HR count.",
    format_func=lambda pid: player_labels.get(pid, str(pid)),
    on_change=_on_player_change,
    disabled=(team_id is None),
)


# --- Stadium selectbox (fetch parks only once a player is chosen, D-18) ---
player_id = st.session_state.get("player_id")
if player_id is not None:
    parks_map = load_all_parks()  # dict[int, dict]
    venue_entries = sorted(
        parks_map.items(), key=lambda kv: kv[1].get("name", "")
    )
    venue_options = [vid for vid, _ in venue_entries]
    venue_labels = {vid: v.get("name", str(vid)) for vid, v in venue_entries}
else:
    venue_options = []
    venue_labels = {}

st.selectbox(
    "Stadium",
    options=venue_options,
    key="venue_id",
    index=None,
    placeholder="Select a stadium…",
    help="Defaults to the player's home park. Change to see how their HRs would play elsewhere.",
    format_func=lambda vid: venue_labels.get(vid, str(vid)),
    disabled=(player_id is None),
    # NO on_change — manual override sticks (D-17 final bullet).
)

st.divider()


# --- Render region (UI-SPEC §Render tree) ---
venue_id = st.session_state.get("venue_id")
if team_id is None or player_id is None or venue_id is None:
    st.info("Select a team, player, and stadium to begin.")
else:
    try:
        with st.spinner("Loading player data..."):
            view = controller.build_view(team_id, player_id, venue_id, season=season)
    except Exception as e:
        st.error(
            f"Could not load data. The MLB API may be temporarily unavailable. "
            f"({type(e).__name__})"
        )
        if st.button("Retry Request"):
            st.cache_data.clear()
            st.rerun()
        st.stop()  # Halt page execution after error -- don't render stale UI

    # D-27: error carrier banner with singular/plural noun.
    if view.errors:
        n = len(view.errors)
        noun = "game feed" if n == 1 else "game feeds"
        st.warning(
            f"{n} {noun} failed to fetch; HR data may be incomplete."
        )

    # --- Summary metrics (VIZ-04, D-01) ---
    if view.plottable_events:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total HRs", len(view.plottable_events))
        col2.metric("Avg Parks Cleared", f"{view.totals['avg_parks_cleared']:.1f} / 30")
        col3.metric("No-Doubters (30/30)", view.totals["no_doubters"])
        col4.metric("Cheap HRs (\u22645/30)", view.totals["cheap_hrs"])

    # --- Spray chart (Phase 5, VIZ-01/02/03) ---
    venue_fieldinfo = parks_map[view.venue_id].get("fieldInfo") or {}
    park = Park.from_field_info(
        venue_fieldinfo,
        venue_id=view.venue_id,
        name=view.venue_name,
    )

    # Empty-state info banners (D-25, D-26, D-12).
    if not view.events:
        st.info(f"{view.player_name} has no home runs in {view.season}.")
    elif not view.plottable_events:
        st.info(f"{view.player_name} has no plottable HRs in {view.season}.")
    else:
        st.subheader("Spray Chart")
        st.plotly_chart(
            chart.build_figure(view, park),
            use_container_width=True,
        )

        # --- Park Rankings (VIZ-05, D-02) ---
        if view.verdict_matrix is not None:
            ranking_df = controller.build_park_ranking(view)
            with st.expander("Park Rankings"):
                n_hrs = len(view.plottable_events)
                st.caption(
                    f"How many of {view.player_name}'s {n_hrs} "
                    f"HR{'s' if n_hrs != 1 else ''} would clear the fence at each park."
                )

                def _highlight_top_bottom(row):
                    """Highlight top 3 green, bottom 3 red (D-02 tie handling)."""
                    idx = row.name  # integer index after reset_index
                    n = len(ranking_df)
                    # Top 3: first 3 rows (already sorted desc by Clears)
                    top_cutoff = ranking_df["Clears"].iloc[min(2, n - 1)] if n > 0 else -1
                    bot_cutoff = ranking_df["Clears"].iloc[max(n - 3, 0)] if n > 0 else -1
                    clears_val = ranking_df["Clears"].iloc[idx]
                    if clears_val >= top_cutoff and top_cutoff > bot_cutoff:
                        return ["background-color: rgba(44, 160, 44, 0.15)"] * len(row)
                    elif clears_val <= bot_cutoff and top_cutoff > bot_cutoff:
                        return ["background-color: rgba(214, 39, 40, 0.15)"] * len(row)
                    return [""] * len(row)

                styled = ranking_df.style.apply(_highlight_top_bottom, axis=1)
                st.dataframe(styled, use_container_width=True, hide_index=True)

    # Plottable dataframe (only when plottable_events non-empty).
    if view.plottable_events:
        st.subheader("Plottable HRs")
        rows = []
        for ev, clears in zip(view.plottable_events, view.clears_selected_park):
            rows.append(
                {
                    "game_date": (
                        ev.game_date.isoformat()
                        if hasattr(ev.game_date, "isoformat")
                        else str(ev.game_date)
                    ),
                    "opponent_abbr": ev.opponent_abbr,
                    "distance_ft": (
                        int(ev.distance_ft) if ev.distance_ft is not None else None
                    ),
                    "launch_speed": (
                        round(ev.launch_speed, 1)
                        if ev.launch_speed is not None
                        else None
                    ),
                    "launch_angle": (
                        round(ev.launch_angle, 1)
                        if ev.launch_angle is not None
                        else None
                    ),
                    "clears_selected": bool(clears),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
