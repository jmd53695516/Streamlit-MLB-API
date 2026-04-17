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

# --- Page config (must be first st call) ---
st.set_page_config(
    page_title="MLB HR Park Explorer",
    page_icon="\u26be",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Custom CSS — "Press Box at Night" broadcast aesthetic
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* ---- Fonts ---- */
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    /* ---- Root variables ---- */
    :root {
        --bg-deep:    #0a0e17;
        --bg-surface: #131a2b;
        --bg-card:    #1a2236;
        --accent:     #f0a500;
        --accent-dim: #c48800;
        --field:      #1a4d2e;
        --clears:     #00d68f;
        --blocked:    #ff6b6b;
        --text-primary: #e8e8e8;
        --text-muted:   #6b7b8d;
        --border-subtle: rgba(240, 165, 0, 0.15);
    }

    /* ---- Global typography ---- */
    html, body, [class*="css"] {
        font-family: 'IBM Plex Mono', monospace !important;
    }
    h1, h2, h3, h4, h5, h6,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Oswald', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ---- Header banner ---- */
    .hero-banner {
        background: linear-gradient(135deg, #131a2b 0%, #1a2236 50%, #0a0e17 100%);
        border-bottom: 3px solid var(--accent);
        padding: 1.8rem 2rem 1.4rem;
        margin: -1rem -1rem 1.5rem -1rem;
        position: relative;
        overflow: hidden;
    }
    .hero-banner::before {
        content: '';
        position: absolute;
        top: 0; right: 0;
        width: 300px; height: 100%;
        background: radial-gradient(ellipse at top right, rgba(240,165,0,0.08) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-title {
        font-family: 'Oswald', sans-serif !important;
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin: 0;
        line-height: 1.1;
    }
    .hero-subtitle {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        color: var(--accent);
        margin-top: 0.3rem;
        letter-spacing: 0.04em;
    }

    /* ---- Sidebar styling ---- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1220 0%, #0a0e17 100%) !important;
        border-right: 1px solid var(--border-subtle);
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMarkdown p {
        font-family: 'Oswald', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 0.8rem;
        color: var(--text-muted) !important;
    }
    .sidebar-logo {
        font-family: 'Oswald', sans-serif;
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 0.5rem 0 1rem;
        border-bottom: 1px solid var(--border-subtle);
        margin-bottom: 1rem;
    }

    /* ---- Metric cards (broadcast stat overlay) ---- */
    .metric-row {
        display: flex;
        gap: 1rem;
        margin: 1rem 0 1.5rem;
        flex-wrap: wrap;
    }
    .metric-card {
        background: linear-gradient(145deg, #1a2236 0%, #131a2b 100%);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 1rem 1.4rem;
        flex: 1;
        min-width: 160px;
        position: relative;
        overflow: hidden;
    }
    .metric-card::after {
        content: '';
        position: absolute;
        top: 0; left: 0;
        width: 3px; height: 100%;
        background: var(--accent);
    }
    .metric-card.green::after { background: var(--clears); }
    .metric-card.red::after { background: var(--blocked); }
    .metric-label {
        font-family: 'Oswald', sans-serif;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin-bottom: 0.25rem;
    }
    .metric-value {
        font-family: 'Oswald', sans-serif;
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
        line-height: 1;
    }
    .metric-value .unit {
        font-size: 0.9rem;
        font-weight: 400;
        color: var(--text-muted);
    }

    /* ---- Player context bar ---- */
    .player-context {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 1rem 1.5rem;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        gap: 1.5rem;
        flex-wrap: wrap;
    }
    .player-name {
        font-family: 'Oswald', sans-serif;
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .player-detail {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
        color: var(--text-muted);
    }
    .player-detail .highlight {
        color: var(--accent);
        font-weight: 600;
    }

    /* ---- Section headers ---- */
    .section-header {
        font-family: 'Oswald', sans-serif;
        font-size: 1.1rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--accent);
        border-bottom: 1px solid var(--border-subtle);
        padding-bottom: 0.4rem;
        margin: 1.5rem 0 0.8rem;
    }

    /* ---- Dataframe styling ---- */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border-subtle) !important;
        border-radius: 6px;
        overflow: hidden;
    }

    /* ---- Expander styling ---- */
    [data-testid="stExpander"] {
        border: 1px solid var(--border-subtle) !important;
        border-radius: 6px !important;
        background: var(--bg-surface) !important;
    }

    /* ---- Info/warning banners ---- */
    [data-testid="stAlert"] {
        border-radius: 6px;
    }

    /* ---- Empty state ---- */
    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        color: var(--text-muted);
    }
    .empty-state .icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.4;
    }
    .empty-state .message {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.9rem;
    }

    /* ---- Hide default Streamlit title ---- */
    [data-testid="stHeader"] {
        background: transparent !important;
    }

    /* ---- Plotly chart container ---- */
    [data-testid="stPlotlyChart"] {
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        overflow: hidden;
    }

    /* ---- Smooth scrollbar ---- */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-deep); }
    ::-webkit-scrollbar-thumb { background: var(--accent-dim); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


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
    """UX-03: set venue_id to the selected team's home park."""
    team_id = st.session_state.get("team_id")
    if team_id is None:
        return
    teams = get_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if team is None:
        return
    st.session_state["venue_id"] = team["venue"]["id"]


# ---------------------------------------------------------------------------
# Hero banner
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero-banner">
    <div class="hero-title">MLB HR Park Factor Explorer</div>
    <div class="hero-subtitle">How cheap (or no-doubt) are their home runs?</div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar — cascading selectors
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-logo">\u26be Park Explorer</div>',
                unsafe_allow_html=True)

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
        placeholder="Select a team\u2026",
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
                f'{e["person"]["fullName"]} \u2014 '
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
        placeholder="Select a player\u2026",
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
        placeholder="Select a stadium\u2026",
        help="Defaults to the player's home park. Change to compare.",
        format_func=lambda vid: venue_labels.get(vid, str(vid)),
        disabled=(player_id is None),
        # NO on_change — manual override sticks (D-17 final bullet).
    )

    # Sidebar footer
    st.markdown("---")
    st.caption("Data via statsapi.mlb.com")


# ---------------------------------------------------------------------------
# Main content area
# ---------------------------------------------------------------------------
venue_id = st.session_state.get("venue_id")

if team_id is None or player_id is None or venue_id is None:
    # Empty state
    st.markdown("""
    <div class="empty-state">
        <div class="icon">\u26be</div>
        <div class="message">
            Select a team, player, and stadium<br>
            from the sidebar to begin.
        </div>
    </div>
    """, unsafe_allow_html=True)
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
        st.stop()

    # D-27: error carrier banner with singular/plural noun.
    if view.errors:
        n = len(view.errors)
        noun = "game feed" if n == 1 else "game feeds"
        st.warning(f"{n} {noun} failed to fetch; HR data may be incomplete.")

    # --- Player context bar ---
    st.markdown(f"""
    <div class="player-context">
        <div class="player-name">{view.player_name}</div>
        <div class="player-detail">
            <span class="highlight">{view.team_abbr}</span> &middot;
            {view.season} Season &middot;
            Stadium: <span class="highlight">{view.venue_name}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Summary metrics (VIZ-04, D-01) — broadcast stat cards ---
    if view.plottable_events:
        n_hrs = len(view.plottable_events)
        avg_cleared = view.totals['avg_parks_cleared']
        no_doubters = view.totals["no_doubters"]
        cheap = view.totals["cheap_hrs"]

        st.markdown(f"""
        <div class="metric-row">
            <div class="metric-card">
                <div class="metric-label">Total HRs</div>
                <div class="metric-value">{n_hrs}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Parks Cleared</div>
                <div class="metric-value">{avg_cleared:.1f} <span class="unit">/ 30</span></div>
            </div>
            <div class="metric-card green">
                <div class="metric-label">No-Doubters (30/30)</div>
                <div class="metric-value">{no_doubters}</div>
            </div>
            <div class="metric-card red">
                <div class="metric-label">Cheap HRs (\u22645/30)</div>
                <div class="metric-value">{cheap}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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
        st.markdown('<div class="section-header">Spray Chart</div>',
                    unsafe_allow_html=True)
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
                    f"HR{'s' if n_hrs != 1 else ''} would clear the fence "
                    f"at each park."
                )

                def _highlight_top_bottom(row):
                    """Highlight top 3 green, bottom 3 red (D-02 tie handling)."""
                    idx = row.name
                    n = len(ranking_df)
                    top_cutoff = ranking_df["Clears"].iloc[min(2, n - 1)] if n > 0 else -1
                    bot_cutoff = ranking_df["Clears"].iloc[max(n - 3, 0)] if n > 0 else -1
                    clears_val = ranking_df["Clears"].iloc[idx]
                    if clears_val >= top_cutoff and top_cutoff > bot_cutoff:
                        return ["background-color: rgba(0, 214, 143, 0.15)"] * len(row)
                    elif clears_val <= bot_cutoff and top_cutoff > bot_cutoff:
                        return ["background-color: rgba(255, 107, 107, 0.15)"] * len(row)
                    return [""] * len(row)

                styled = ranking_df.style.apply(_highlight_top_bottom, axis=1)
                st.dataframe(styled, use_container_width=True, hide_index=True)

    # Plottable dataframe (only when plottable_events non-empty).
    if view.plottable_events:
        st.markdown('<div class="section-header">HR Detail</div>',
                    unsafe_allow_html=True)
        rows = []
        for ev, clears in zip(view.plottable_events, view.clears_selected_park):
            rows.append(
                {
                    "Date": (
                        ev.game_date.isoformat()
                        if hasattr(ev.game_date, "isoformat")
                        else str(ev.game_date)
                    ),
                    "Opp": ev.opponent_abbr,
                    "Dist (ft)": (
                        int(ev.distance_ft) if ev.distance_ft is not None else None
                    ),
                    "Exit Velo": (
                        round(ev.launch_speed, 1)
                        if ev.launch_speed is not None
                        else None
                    ),
                    "Launch \u00b0": (
                        round(ev.launch_angle, 1)
                        if ev.launch_angle is not None
                        else None
                    ),
                    "Clears?": "\u2705" if clears else "\u274c",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
