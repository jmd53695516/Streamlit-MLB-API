# Phase 4: Controller & Selectors UI — Research

**Researched:** 2026-04-15
**Domain:** Streamlit session-state cascade + MLB StatsAPI team-level hitting stats + pure controller composition
**Confidence:** HIGH (all load-bearing claims verified against live API or official Streamlit docs)

## Summary

Phase 4 is a thin Streamlit shell that composes already-tested layers (Phase 1 services, Phase 2 geometry, Phase 3 pipeline) into a single `ViewModel`, driven by three cascading selectboxes with `st.session_state` reset callbacks. The research surfaced **one load-bearing correction to CONTEXT (D-11)**: the endpoint `GET /teams/{id}/stats?stats=season&group=hitting` returns team aggregate totals, NOT per-player splits — so the per-player HR list must come from a different call. The correct one-HTTP-call replacement is `GET /teams/{id}/roster?rosterType=active&hydrate=person(stats(type=statsSingleSeason,season={s},group=hitting))`, which returns 26 roster entries with `position.type` at top-level AND hydrated `person.stats[0].splits[0].stat.homeRuns` per hitter. Everything else in CONTEXT holds.

Streamlit 1.55+ supports `index=None` with `placeholder=` (both verified). `on_change` callbacks fire **after** `st.session_state[key]` is updated to the new value (verified via forum reports / issue threads), so `_on_team_change` / `_on_player_change` can read the new parent value directly off session_state. If session_state carries a value that is no longer in a selectbox's `options`, Streamlit **raises `ValueError`** — the cascade reset in `_on_team_change` (nulling `player_id` and `venue_id`) is therefore not decorative; it's crash-prevention.

**Primary recommendation:** Amend D-11 to use `roster + hydrate` one-call path (`get_team_hitting_stats` wraps it), keep every other decision, and ship `controller.build_view` as a pure function plus a ~60-line `app.py`. Manual smoke test: `streamlit run src/mlb_park/app.py` → NYY → Judge → Yankee Stadium → 6 HRs in the dataframe.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions
Copied verbatim from `.planning/phases/04-controller-selectors-ui/04-CONTEXT.md` §Implementation Decisions:

- **D-01..D-04** — Caching + import origin: only `services/mlb_api.py` uses `@st.cache_data` / `requests`; Phase 4 imports pipeline via `mlb_park.pipeline`; no URL-state; no UX-05 polish.
- **D-05..D-10** — ViewModel shape: `controller.build_view(team_id, player_id, venue_id, *, season=None, api=...) -> ViewModel` is a frozen dataclass with fields `season, team_id, team_abbr, player_id, player_name, venue_id, venue_name, player_home_venue_id, events, plottable_events, verdict_matrix, clears_selected_park, totals, errors`. `plottable_events = events where has_distance AND has_coords`. `verdict_matrix` is `None` when `plottable_events` empty.
- **D-11 (needs amendment — see Open Question Q1):** New services wrapper `get_team_hitting_stats(team_id, season)`. CONTEXT's endpoint choice (`/teams/{id}/stats?stats=season&group=hitting`) does NOT return per-player rows. Correct endpoint is `/teams/{id}/roster?hydrate=person(stats(type=statsSingleSeason,season=...,group=hitting))`.
- **D-12** — Non-pitcher filter: `position.type != "Pitcher"`. **VERIFIED** against live NYY 2026 fixture (see §Environment findings). Keeps Outfielder / Infielder / Catcher / Hitter (DH) / Two-Way Player.
- **D-13** — Sort `(-homeRuns, fullName)`. Zero-HR hitters included.
- **D-14** — `@st.cache_data(ttl="1h")` for the new wrapper.
- **D-15** — Empty roster → empty selectbox, no crash.
- **D-16..D-20** — session_state keys `"team_id" | "player_id" | "venue_id"`; `on_change` callbacks (`_on_team_change` nulls both children; `_on_player_change` sets venue to player's home park); `index=None` cold start; `build_view` gated on all three being non-None; home-venue lookup via cached `get_teams()[team_id]["venue"]["id"]`.
- **D-21..D-23** — Single `src/mlb_park/controller.py` module; NO `@st.cache_data` on `build_view`; controller is pure (no `st.*`, no session_state reads).
- **D-24..D-26** — Raw dump = `st.json(view.to_dict())` + `st.dataframe(...)`. 0-HR → `st.info`, no dataframe. All-missing-hitData → `st.info` + JSON, no dataframe.
- **D-27** — `ViewModel.errors` forwards `PipelineResult.errors`; render `st.warning(f"{n} game feed(s) failed...")` when non-empty.
- **D-28..D-30** — Controller unit tests under `tests/controller/`, stub-api injection pattern mirrors Phase 3's `StubAPI`, `app.py` is manual-smoke only (no Streamlit AppTest).

### Claude's Discretion
- `ViewModel.to_dict()` implementation strategy (`dataclasses.asdict` with post-processing, or hand-rolled).
- Callback location (module-level in `app.py` vs a helper submodule).
- Layout: `st.columns(3)` vs stacked.
- `totals` as plain `dict` vs `Totals` dataclass.
- Pandas DataFrame vs list-of-dicts for `st.dataframe`.
- Logging of `build_view` invocations.

### Deferred Ideas (OUT OF SCOPE)
- V2-05 URL query-param state (`bind=` feature).
- Persisted last-used selections.
- UX-05 spinners / friendly errors / retry button (Phase 6).
- Streamlit AppTest framework for `app.py` (Phase 6 if useful).
- Expanded `Totals` dataclass.
- Per-HR details-table polish (V2-02).
- Wall-height caveat banner (V2-03).
- Cheap-HR threshold slider (V2-04).
- Package-splitting `controller/` (defer until >200 LOC).
- Namespaced session_state keys.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **UX-01** | User selects a team from a dropdown of all 30 MLB teams. | `get_teams()` already exists + `teams.json` fixture has 30 rows with `abbreviation`/`name`/`venue.id`. Team selectbox options come directly from it. |
| **UX-02** | Player dropdown filtered to non-pitchers, sorted by current-season HR desc. | Verified one-HTTP-call path: `/teams/{id}/roster?hydrate=person(stats(...))`. `position.type != "Pitcher"` filter confirmed (Q1 below). Zero-HR hitters included per D-13. |
| **UX-03** | Stadium dropdown defaults to player's home park. | `_on_player_change` sets `venue_id = get_teams()[team_id]["venue"]["id"]`. Cached via the existing `get_teams()` wrapper — no extra HTTP. |
| **UX-04** | Changing Team clears Player; changing Player resets Stadium to home park. Managed via `st.session_state`. | `on_change` callbacks nulling child keys is the canonical Streamlit pattern **and** a crash prevention (stale session_state value raises `ValueError` when options change — see Pitfall P-02). |

---

## Standard Stack

### Core (already pinned, no additions in Phase 4)

| Library | Version | Purpose | Why Standard |
|---|---|---|---|
| streamlit | `>=1.55,<2.0` (current 1.56.0) `[VERIFIED: requirements.txt + CLAUDE.md]` | UI + session_state + caching | Locked. 1.55 added `index=None` + `placeholder` on `st.selectbox`, `on_change` callback semantics stable since 1.11. |
| pandas | `>=2.2,<3.0` `[VERIFIED: requirements.txt]` | DataFrame for the plottable-HRs table | `st.dataframe` accepts DataFrames natively; a list-of-dicts also works but loses column ordering control. |
| requests | `>=2.32,<3.0` | HTTP (indirectly via `services.mlb_api`) | Only touched by `services/mlb_api.py`. Phase 4 does NOT import `requests`. |

No new third-party dependencies for Phase 4. `streamlit-extras` / `streamlit-aggrid` / `streamlit-option-menu` are **forbidden** per UI-SPEC §Registry Safety and CLAUDE.md.

### Version verification

```bash
pip index versions streamlit  # 1.56.0 current (2026-03-31 release)
pip index versions pandas     # 2.2.x line
```

`[VERIFIED: pinned in requirements.txt, confirmed against CLAUDE.md §Recommended Stack which was live-verified on 2026-04-14 per ROADMAP]`

---

## Architecture Patterns

### File layout (D-21)

```
src/mlb_park/
├── app.py                     # Streamlit entry point (wholesale REPLACEMENT of current 6-line scaffold)
├── controller.py              # NEW — ViewModel dataclass + build_view (pure, no st.*)
├── config.py                  # existing — CURRENT_SEASON
├── services/
│   └── mlb_api.py             # existing — ADD get_team_hitting_stats + _raw_team_hitting_stats
├── geometry/verdict.py        # existing
└── pipeline/__init__.py       # existing — Phase 4 imports ONLY from here

tests/
├── controller/
│   ├── __init__.py            # NEW
│   ├── conftest.py            # NEW — extends Phase 3 StubAPI with get_team_hitting_stats + get_teams
│   ├── test_build_view.py     # NEW — D-29 five happy/edge-path tests
│   └── fixtures/              # (optional) if Phase 4-specific synthetic stubs are needed
└── fixtures/
    ├── team_stats_147_2026.json  # NEW — captured live 2026-04-15 (see §Environment findings)
    ├── teams.json                 # existing
    ├── roster_147.json            # existing
    ├── gamelog_592450_2026.json   # existing (reused from Phase 3)
    ├── feed_*.json (×5)           # existing (reused from Phase 3)
    └── venue_*.json (×30)         # existing
```

`src/mlb_park/app.py` currently contains a 6-line Phase-1 scaffold (`st.title` + `st.info`). Phase 4 **replaces it wholesale**.

### Pattern 1: Cascading selectboxes with `on_change` reset (D-16..D-20)

```python
# Source: streamlit docs + empirical forum verification (see Sources)
# session_state[key] is updated BEFORE the callback fires.
def _on_team_change() -> None:
    """New team selected — null children so the next rerun uses fresh options."""
    st.session_state["player_id"] = None
    st.session_state["venue_id"] = None

def _on_player_change() -> None:
    """New player selected — default venue to player's home park (UX-03)."""
    team_id = st.session_state["team_id"]  # already the NEW value
    teams = {t["id"]: t for t in get_teams()}  # cached; no network
    st.session_state["venue_id"] = teams[team_id]["venue"]["id"]

# In app.py:
st.selectbox(
    "Team",
    options=sorted_team_ids,
    format_func=lambda tid: f"{teams[tid]['name']} ({teams[tid]['abbreviation']})",
    key="team_id",
    index=None,
    placeholder="Select a team…",
    on_change=_on_team_change,
    help="Choose an MLB team to load its hitters.",
)

# Player selectbox — only render when team_id is set; options computed fresh each run.
player_options = _sorted_hitters(st.session_state.get("team_id"))  # [] if team is None
st.selectbox(
    "Player",
    options=[p["id"] for p in player_options],
    format_func=lambda pid: f"{name_of[pid]} — {hr_of[pid]} HR",
    key="player_id",
    index=None,
    placeholder="Select a player…",
    on_change=_on_player_change,
    disabled=(st.session_state.get("team_id") is None),
    help="Non-pitchers on this team, sorted by current-season HR count.",
)
```

### Pattern 2: Pure controller (D-22, D-23)

```python
# Source: Phase 3 StubAPI pattern (tests/pipeline/conftest.py)
# controller.build_view is pure composition — zero st.* calls, zero session_state reads.
from dataclasses import dataclass
from mlb_park.pipeline import (
    extract_hrs, hr_event_to_hit_data, HREvent, PipelineError,
    compute_verdict_matrix, load_all_parks, CURRENT_SEASON, MLBAPIError,
)
from mlb_park.geometry.verdict import VerdictMatrix

@dataclass(frozen=True)
class ViewModel:
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
    totals: dict[str, int | float]
    errors: tuple[PipelineError, ...]

    def to_dict(self) -> dict:
        """JSON-safe — dates to ISO, VerdictMatrix to summary dict, numpy to lists."""
        ...

def build_view(
    team_id: int,
    player_id: int,
    venue_id: int,
    *,
    season: int | None = None,
    api = _default_api,  # mlb_park.services.mlb_api
) -> ViewModel:
    season = season or CURRENT_SEASON
    # Compose: get_teams + get_team_hitting_stats (for player_name) + extract_hrs + compute_verdict_matrix
    # Split events → plottable_events, build verdict matrix from HitData adapter outputs,
    # compute clears_selected_park by looking up venue_id column of the matrix,
    # compute totals per D-09 schema.
```

### Pattern 3: `ViewModel.to_dict()` — JSON-safe serialization (D-24)

Since `VerdictMatrix` does NOT have a `.to_dict()` method today `[VERIFIED: grep over src/mlb_park/geometry/verdict.py]`, the helper must:

1. `dataclasses.asdict(self)` over scalar fields.
2. Convert `events` / `plottable_events` `HREvent`s via `dataclasses.asdict` + `game_date.isoformat()`.
3. Convert `verdict_matrix` to a **summary dict** (not the full 60 × 30 float arrays — too noisy for the JSON dump):
   ```python
   {"shape": [n_hrs, 30], "venue_ids": [...], "cleared_per_park": {venue_id: int_count}}
   ```
4. `numpy.ndarray` → `.tolist()`, `PipelineError` → `asdict`.

Adding a real `VerdictMatrix.to_dict()` method in `geometry/verdict.py` is an **option** (see Discretion in CONTEXT) but is strictly beyond Phase 4's scope — keeping the summary logic inside `ViewModel.to_dict()` respects the phase boundary.

### Anti-Patterns to Avoid

- **`@st.cache_data` on `build_view`** → violates D-22; cache lives at services boundary only.
- **`st.*` inside `controller.py`** → violates D-23; breaks test isolation.
- **Reading `st.session_state` inside `build_view`** → violates D-23.
- **Eager fetch of all 30 teams' rosters** on cold start → violates CLAUDE.md "no hammering".
- **Third-party Streamlit components** (`streamlit-extras`, `streamlit-aggrid`, etc.) → forbidden per UI-SPEC §Registry Safety.
- **`pybaseball` / `MLB-StatsAPI`** → forbidden per CLAUDE.md §What NOT to Use.
- **Hardcoded team_id / player_id defaults in `app.py`** → violates D-18 empty-placeholder cold start.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Selectbox dependent-reset logic | Custom wrapper widget, manual rerun calls | `on_change` callback + `index=None` | Streamlit native. Session_state is updated before the callback fires, so callbacks just assign `None` / default. |
| JSON-safe dataclass serialization | Manual recursive walk | `dataclasses.asdict` + post-processing for `date`/`numpy` | `asdict` handles nested frozen dataclasses; only non-JSON-native types need manual handling. |
| Home-venue lookup for a team | Separate `/teams/{id}` call | `get_teams()[team_id]["venue"]["id"]` | Already cached by existing 24h TTL wrapper. Zero added HTTP. |
| Per-player HR count + position | Per-player `/people/{id}/stats` fan-out (26 calls) | Single roster+hydrate call | 1 HTTP vs 26; respects CLAUDE.md rate posture. |

---

## Runtime State Inventory

(Phase 4 is greenfield for the controller layer — no renames/migrations. Section included for completeness.)

| Category | Items | Action |
|---|---|---|
| Stored data | None — Phase 4 is code-only. Existing venue cache at `data/venues_cache.json` is untouched. | None. |
| Live service config | None. | None. |
| OS-registered state | None. | None. |
| Secrets / env vars | None — no new env vars; no API keys required. | None. |
| Build artifacts / installed packages | No new packages. `requirements.txt` unchanged. | None. |

---

## Common Pitfalls

### P-01: Assuming `/teams/{id}/stats?group=hitting` returns per-player splits
**What goes wrong:** The endpoint returns team-level aggregate stats (1 split = the team as a whole). Coding against "each split is a player" produces no player list at all.
**Why:** The `/teams/{id}/stats` endpoint aggregates over the team entity. Per-player splits require hydration of the roster resource.
**How to avoid:** Use `GET /teams/{id}/roster?rosterType=active&hydrate=person(stats(type=statsSingleSeason,season={s},group=hitting))`. **Empirically verified 2026-04-15** — see §Environment findings.
**Warning signs:** `len(response["stats"][0]["splits"]) == 1` with the sole split's `team` matching the requested `team_id`.

### P-02: Stale session_state value raising `ValueError` when options change
**What goes wrong:** After user switches Team, the Player selectbox's new options no longer contain the stale `player_id`. Streamlit raises `ValueError` (GitHub issue #3598).
**Why:** Streamlit validates that `session_state[key]` is in `options` at widget instantiation time.
**How to avoid:** `_on_team_change` MUST null `player_id` and `venue_id` before the next rerun renders the Player selectbox. This is not decorative reset logic; it's crash prevention.
**Warning signs:** `ValueError: ... is not in iterable` on team-change interaction.

### P-03: `on_change` callback read order assumption
**What goes wrong:** Developer writes `_on_player_change` assuming `st.session_state["player_id"]` still holds the OLD value.
**Why:** It doesn't — session_state is updated BEFORE the callback fires. Callback sees the NEW value.
**How to avoid:** Name variables and write comments matching the actual semantics. Test with fixtures that assert post-callback state.
**Warning signs:** Home-park default looks up the wrong team.

### P-04: Empty `person.stats` arrays for pitchers
**What goes wrong:** Iterating `roster_entry["person"]["stats"][0]["splits"][0]["stat"]["homeRuns"]` blindly crashes with `IndexError` on pitchers (no `stats` key; even if present, `splits` is empty).
**Why:** Pitchers don't have hitting splits at the person level even when queried for the hitting group.
**How to avoid:** Defensive chained `.get(..., [])` + default `homeRuns = 0`. Also — pitchers are filtered out by `position.type == "Pitcher"` anyway, so the nested access never runs on them. Defensive code is still cheap.
**Warning signs:** `IndexError: list index out of range` when iterating newly-called-up hitters (possible 0-AB edge).

### P-05: `venue_id` sticks when team changes (UX bug)
**What goes wrong:** D-17 only nulls `venue_id` on team change. If `_on_player_change` also runs (common when both happen in sequence), venue re-defaults. But if user changes Team and then manually picks a DIFFERENT stadium before picking a Player, that stadium would be overridden by `_on_player_change`. This is the CONTEXT-specified behavior (venue resets to home park on player change) but worth naming.
**Why:** Three-level cascade; only child-reset is stored.
**How to avoid:** Accept this as locked per D-17. If the UX feedback during manual smoke flags it, raise a new CONTEXT entry (not a Phase 4 change).

### P-06: Rendering full 60×30 verdict matrix in `st.json`
**What goes wrong:** `st.json` with a large nested dict renders a huge collapsed-tree UI, defeating the "dev dump" purpose.
**Why:** VerdictMatrix carries dense numpy arrays (n_hrs × 30).
**How to avoid:** `ViewModel.to_dict()` emits a SUMMARY for `verdict_matrix` — shape, venue_ids, per-park cleared-count. The full matrix content is derivable from the dataframe + a future chart.

### P-07: Windows path / fixture loading
**What goes wrong:** Tests written with forward-slash string paths might fail on Windows.
**Why:** Project is Windows-hosted (`Streamlit MLB API` on `C:\Users\joedo`).
**How to avoid:** Use `pathlib.Path` everywhere (Phase 3 already does). Mirror the pattern.

---

## Code Examples

### Team hitting stats wrapper (the amended D-11)

```python
# src/mlb_park/services/mlb_api.py — ADD these (mirrors existing pattern)
def _raw_team_hitting_stats(team_id: int, season: int) -> list[dict]:
    """Active roster entries with hydrated season hitting stats (D-11 amended).
    
    Returns the `roster` array (one entry per rostered player). Each entry has:
      - position.type  ← top-level; D-12 non-pitcher filter reads from here
      - person.id, person.fullName
      - person.stats[0].splits[0].stat.homeRuns (when the player has any season splits)
    Pitchers typically have empty person.stats.
    """
    assert isinstance(team_id, int) and isinstance(season, int), \
        "team_id and season must be int (SSRF guard)"
    return _get(
        f"{BASE_URL_V1}/teams/{team_id}/roster",
        params={
            "rosterType": "active",
            "hydrate": f"person(stats(type=statsSingleSeason,season={season},group=hitting))",
        },
    )["roster"]


@st.cache_data(ttl=TTL_TEAM_HITTING, show_spinner=False)  # TTL_TEAM_HITTING = "1h" (D-14)
def get_team_hitting_stats(team_id: int, season: int) -> list[dict]:
    """Per-hitter season-to-date HR counts for a team. TTL 1h."""
    return _raw_team_hitting_stats(team_id, season)
```

Add `TTL_TEAM_HITTING = "1h"` to `src/mlb_park/config.py`.

### Non-pitcher filter + sort (D-12, D-13)

```python
# Source: live verification against tests/fixtures/team_stats_147_2026.json
def _sorted_hitters(entries: list[dict]) -> list[dict]:
    """Non-pitchers, sorted by (-homeRuns, fullName). Zero-HR hitters included."""
    def hr_count(entry: dict) -> int:
        stats = entry.get("person", {}).get("stats") or []
        if not stats:
            return 0
        splits = stats[0].get("splits") or []
        if not splits:
            return 0
        return splits[0].get("stat", {}).get("homeRuns", 0) or 0

    hitters = [
        e for e in entries
        if (e.get("position") or {}).get("type") != "Pitcher"
    ]
    return sorted(
        hitters,
        key=lambda e: (-hr_count(e), e["person"]["fullName"]),
    )
```

### Plottable-HR DataFrame (D-24)

```python
# UI-SPEC locks column names and order exactly.
import pandas as pd

def _build_plottable_df(view: "ViewModel") -> pd.DataFrame:
    rows = []
    for ev, cleared in zip(view.plottable_events, view.clears_selected_park):
        rows.append({
            "game_date": ev.game_date.isoformat(),    # YYYY-MM-DD as plain str (safest st.dataframe path)
            "opponent_abbr": ev.opponent_abbr,
            "distance_ft": int(ev.distance_ft) if ev.distance_ft is not None else None,
            "launch_speed": ev.launch_speed,
            "launch_angle": ev.launch_angle,
            "clears_selected": bool(cleared),
        })
    return pd.DataFrame(rows, columns=[
        "game_date", "opponent_abbr", "distance_ft",
        "launch_speed", "launch_angle", "clears_selected",
    ])
```

Passing ISO strings (rather than `datetime.date` objects) sidesteps any `st.column_config.DateColumn` formatting concerns for this phase. UI-SPEC §Dataframe doesn't require Date-column semantics — plain strings pass the copy contract.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| `st.beta_*` / deprecated layout APIs | `st.columns`, `st.container`, `st.tabs` (stable) | Streamlit 1.0+ | No impact; we're already on 1.55+. |
| Cascading selectboxes via manual `experimental_rerun()` | `on_change` callback + session_state | Streamlit 1.0+ | Our locked approach. |
| Dict index tricks to preserve selection | `index=None` + `placeholder=` | Streamlit 1.35 (index=None), 1.27 (placeholder) | Our cold-start pattern. |
| `st.cache` | `@st.cache_data` / `@st.cache_resource` | Streamlit 1.18 | Already adopted across `services/mlb_api.py`. |

**Deprecated / outdated:**
- `st.cache` — replaced by `st.cache_data`.
- `st.experimental_rerun()` — stable since `st.rerun()` (Streamlit 1.27).
- `st.beta_columns` — long since stable as `st.columns`.

---

## Environment Availability

Phase 4 is pure code/config. No new external dependencies.

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| Python 3.12 | Runtime | — (not re-audited; Phase 1 confirmed) | — | — |
| Streamlit ≥1.55 | Selectors, session_state, on_change | ✓ | pinned | — |
| pandas ≥2.2 | Plottable-HRs DataFrame | ✓ | pinned | list-of-dicts to `st.dataframe` |
| Existing pipeline + services + geometry | `build_view` composition | ✓ (Phases 1-3 complete per STATE.md) | — | — |
| Live `statsapi.mlb.com` | Running `streamlit run app.py` manually | ✓ verified 2026-04-15 | — | Fixture-driven tests cover the controller offline. |

**New fixture recorded:** `tests/fixtures/team_stats_147_2026.json` — captured live 2026-04-15 from `/teams/147/roster?rosterType=active&hydrate=person(stats(type=statsSingleSeason,season=2026,group=hitting))`. 26 roster entries: 13 Pitchers (filtered out), 13 hitters (9 with ≥1 HR, 4 at 0 HR). Top HR-leader: Aaron Judge (6). `position.type` present on every entry; `person.primaryPosition.type` mirrors it on hitters. Distribution is the Phase 4 happy-path + edge-path test oracle.

### Fixture inventory (existing, reusable)

| Fixture | Size | Phase-4 role |
|---|---|---|
| `tests/fixtures/teams.json` | 30 teams | Populates Team selectbox; `_home_venue_id` lookup. |
| `tests/fixtures/roster_147.json` | 26 NYY roster entries | Legacy reference only — Phase 4 does NOT use roster directly (uses hydrated team_stats call instead). |
| `tests/fixtures/gamelog_592450_2026.json` | Judge gameLog | `build_view` happy-path (reused from Phase 3). |
| `tests/fixtures/feed_82*.json` (×5) | Judge game feeds | `build_view` happy-path (reused from Phase 3). |
| `tests/fixtures/venue_*.json` (×30) | Park fieldInfo | `load_all_parks()` (reused from Phase 1). |
| `tests/fixtures/team_stats_147_2026.json` | **NEW** — 26 roster entries with hydrated hitting splits | Phase 4 player-selector oracle. |
| `tests/pipeline/fixtures/feed_*.json` | 5 synthetic degradation feeds | Phase-3 owned; `build_view` edge-case tests (all-missing-hitData) may reuse `feed_missing_hitdata.json` + `feed_partial_hitdata.json`. |

---

## Validation Architecture

Phase 4's validation is **fixture-verified controller unit tests** plus a **manual Streamlit smoke checklist**. Per D-30, `app.py` gets no automated coverage in this phase.

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest 8.x (already pinned and in use across `tests/`) |
| Config file | `pyproject.toml` / `pytest.ini` (existing — Phases 2 and 3 tests run green) |
| Quick run command | `pytest tests/controller/ -q` |
| Full suite command | `pytest tests/ -q` |
| Manual smoke command | `streamlit run src/mlb_park/app.py` |

### Phase Requirements → Test Map

| REQ | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| UX-01 | 30 teams populate Team selectbox | unit (sorted options + len) | `pytest tests/controller/test_build_view.py::test_build_view_happy_path -x` (indirect — `build_view` takes a team_id; selector coverage is via `_sorted_teams` helper test) | ❌ Wave 0 |
| UX-01 | Team dropdown cold-start returns None (no default) | manual smoke | `streamlit run ...` → observe placeholder | ❌ (manual) |
| UX-02 | Pitchers filtered out; zero-HR hitters included at bottom | unit | `pytest tests/controller/test_helpers.py::test_sorted_hitters_excludes_pitchers -x` | ❌ Wave 0 |
| UX-02 | Sort order `(-homeRuns, fullName)` | unit | `pytest tests/controller/test_helpers.py::test_sorted_hitters_sort_order -x` | ❌ Wave 0 |
| UX-03 | After picking Judge on NYY, venue_id defaults to Yankee Stadium (id 3313) | unit (callback simulation) | `pytest tests/controller/test_callbacks.py::test_on_player_change_sets_home_venue -x` | ❌ Wave 0 |
| UX-04 | Team-change nulls player_id and venue_id | unit (callback simulation) | `pytest tests/controller/test_callbacks.py::test_on_team_change_nulls_children -x` | ❌ Wave 0 |
| D-05..D-09 | `build_view(NYY, Judge, YankeeStadium)` happy path | unit (fixture-verified) | `pytest tests/controller/test_build_view.py::test_build_view_happy_path -x` | ❌ Wave 0 |
| D-10/D-25 | 0-HR player → `verdict_matrix is None`, `events == ()` | unit | `pytest tests/controller/test_build_view.py::test_build_view_zero_hr_player -x` | ❌ Wave 0 |
| D-10/D-26 | All-missing-hitData → `verdict_matrix is None`, `events` non-empty | unit | `pytest tests/controller/test_build_view.py::test_build_view_all_missing_hitdata -x` | ❌ Wave 0 |
| D-27 | One feed fails → `errors` non-empty, other HRs still in `events` | unit | `pytest tests/controller/test_build_view.py::test_build_view_one_feed_fails -x` | ❌ Wave 0 |
| D-08 | Stadium flip: same (team, player), different venue_id → `clears_selected_park` differs, `verdict_matrix` identical | unit | `pytest tests/controller/test_build_view.py::test_build_view_stadium_flip -x` | ❌ Wave 0 |
| D-09 | `totals` arithmetic (total_hrs, plottable_hrs, avg_parks_cleared, no_doubters, cheap_hrs) | unit | `pytest tests/controller/test_build_view.py::test_build_view_totals -x` | ❌ Wave 0 |
| D-24 | `ViewModel.to_dict()` is JSON-serializable | unit | `pytest tests/controller/test_view_model.py::test_to_dict_json_safe -x` | ❌ Wave 0 |
| Manual | `streamlit run` → NYY → Judge → Yankee Stadium → 6 HRs with correct dataframe columns | manual smoke | (human checklist) | N/A |

### Sampling Rate
- **Per task commit:** `pytest tests/controller/ -q` (fast — stub-api only, no network).
- **Per wave merge:** `pytest tests/ -q` (full suite; Phase 1-3 tests continue to pass).
- **Phase gate:** Full suite green + manual smoke checklist complete before `/gsd-verify-work`.

### Wave 0 Gaps
All test files are new in Phase 4:
- [ ] `tests/controller/__init__.py`
- [ ] `tests/controller/conftest.py` — extends Phase 3 `StubAPI` with `get_team_hitting_stats(team_id, season)` and `get_teams()` methods; provides a Judge-preloaded factory fixture using `team_stats_147_2026.json` + existing gameLog/feed fixtures.
- [ ] `tests/controller/test_build_view.py` — 5 tests per D-29.
- [ ] `tests/controller/test_callbacks.py` — `_on_team_change` and `_on_player_change` simulated via a session_state dict shim (pure Python — no Streamlit needed if callbacks take session_state as an argument or are tested via the `streamlit.testing.v1.AppTest`-free shim pattern).
- [ ] `tests/controller/test_helpers.py` — `_sorted_hitters` filter + sort coverage.
- [ ] `tests/controller/test_view_model.py` — `ViewModel.to_dict()` JSON round-trip.

### Synthetic fixtures needed beyond the Judge set

| Fixture | Purpose | Build approach |
|---|---|---|
| `team_stats_empty.json` (synthetic) | D-15 empty-roster guard | Hand-written `{"roster": []}` |
| `team_stats_all_pitchers.json` (synthetic) | Edge: team with only pitchers filtered out | Subset of `team_stats_147_2026.json` keeping only Pitcher entries |
| `team_stats_zero_hr_player.json` (synthetic) | 0-HR player drives `build_view` empty-events path | One roster entry with `splits[0].stat.homeRuns = 0` |
| Reuse `tests/pipeline/fixtures/feed_missing_hitdata.json` | All-missing-hitData `build_view` path | Already exists from Phase 3 |

None of these new synthetics require network access; all are ≤20-line hand-authored JSON or programmatic slices.

### Extending `StubAPI` for the controller (Phase 3 pattern)

```python
# tests/controller/conftest.py (sketch)
from tests.pipeline.conftest import StubAPI as PipelineStubAPI

class ControllerStubAPI(PipelineStubAPI):
    def __init__(
        self,
        *,
        teams: list[dict] | None = None,
        team_hitting_stats: dict[int, list[dict]] | None = None,  # {team_id: [roster entries...]}
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._teams = list(teams) if teams else []
        self._team_hitting_stats = dict(team_hitting_stats) if team_hitting_stats else {}

    def get_teams(self) -> list[dict]:
        return list(self._teams)

    def get_team_hitting_stats(self, team_id: int, season: int) -> list[dict]:
        return list(self._team_hitting_stats.get(team_id, []))
```

Mirrors Phase 3's dependency-injection pattern exactly (D-28 says "same pattern"). Production `build_view` receives this stub via the `api=` keyword, never monkey-patching.

### Manual smoke checklist (D-30)

- [ ] Fresh venv: `streamlit run src/mlb_park/app.py` starts without error.
- [ ] Initial page load: title + subtitle visible, three selectboxes show placeholders, `st.info("Select a team, player, and stadium to begin.")` renders below the divider.
- [ ] Open Team dropdown: 30 teams listed, format `"New York Yankees (NYY)"`.
- [ ] Select "New York Yankees (NYY)": Player selectbox becomes enabled; Stadium remains disabled/empty.
- [ ] Open Player dropdown: pitchers absent (e.g., Max Fried not in list); Aaron Judge appears near top with `"Aaron Judge — 6 HR"`.
- [ ] Select Aaron Judge: Stadium selectbox auto-sets to "Yankee Stadium"; raw dump renders with 6 HRs.
- [ ] `st.subheader("ViewModel (raw)")` above JSON dump; `st.subheader("Plottable HRs")` above dataframe.
- [ ] Dataframe has 6 rows, columns in order: `game_date, opponent_abbr, distance_ft, launch_speed, launch_angle, clears_selected`.
- [ ] Change Stadium to (say) Fenway Park: dataframe's `clears_selected` column flips for at least one HR (Judge's cheap HRs vs Fenway's Green Monster wall — verdicts will differ, ignoring wall height per GEO-03).
- [ ] Change Team to "Boston Red Sox": Player and Stadium selectboxes reset to placeholders; info message returns.
- [ ] Select a zero-HR hitter (e.g., Ryan McMahon): `st.info("Ryan McMahon has no home runs in 2026.")` renders; JSON dump shows `events: []`, `totals.total_hrs: 0`.

---

## Security Domain

`security_enforcement` is not configured in `.planning/config.json`; treat as **enabled**.

### Applicable ASVS Categories

| Category | Applies | Control |
|---|---|---|
| V2 Authentication | no | Single-user local app; no auth. |
| V3 Session Management | no | Streamlit session_state is client-bound per tab; no cross-user sessions. |
| V4 Access Control | no | No multi-user model. |
| V5 Input Validation | **yes** | Selectbox values are constrained to `options` (server-side). Controller asserts `isinstance(team_id, int)` etc. (mirrors existing SSRF guard pattern in `services/mlb_api.py`). |
| V6 Cryptography | no | No crypto needs in Phase 4. |

### Known Threat Patterns

| Pattern | STRIDE | Mitigation |
|---|---|---|
| SSRF via user-controlled ID fed into URL path | Tampering | Existing `_raw_*` helpers assert `isinstance(x, int)`; Phase 4's new `_raw_team_hitting_stats` follows the same assertion pattern. Selectbox `options` restrict inputs to a closed set of valid team/player/venue IDs. |
| Injection via `f"{venue_name}"` into markdown | Tampering | UI-SPEC §Color forbids `unsafe_allow_html=True`; `st.info` / `st.warning` content is plain text with Streamlit's default escaping. |
| Cache poisoning (Streamlit's `@st.cache_data`) | Tampering | Cache key is `(function, args)`; team_id/season are ints. No user-string in cache key. Same posture as Phase 1/3. |
| Third-party component supply chain | (multiple) | UI-SPEC §Registry Safety forbids third-party Streamlit components in Phase 4. Only `streamlit` + `pandas` + `requests` (already pinned) in play. |

---

## Project Constraints (from CLAUDE.md)

Extracted directives with Phase 4 applicability:

| Directive | Phase 4 Compliance |
|---|---|
| Direct HTTP to `statsapi.mlb.com/api/v1` only; no third-party wrappers (`MLB-StatsAPI`, `pybaseball`). | Only new HTTP touches go through `services/mlb_api.py`'s existing `_get` + `@st.cache_data` pattern. |
| `@st.cache_data` at the services boundary only; `requests-cache` forbidden. | D-22 bars caching `build_view`; the one new cached wrapper (`get_team_hitting_stats`) lives in `services/mlb_api.py`. |
| Aggressive caching, no hammering the API. | D-11 amended path is **1 HTTP call per team selection**. D-14 caches it 1h. Cold start fetches ONLY `get_teams()` (UX-01 options). |
| Streamlit ≥1.55, <2.0. | Pinned. `index=None` + `on_change` + `placeholder` all native on 1.55+. |
| pandas ≥2.2, <3.0. | Pinned. `st.dataframe(pd.DataFrame(...))` is the locked raw-dump path. |
| No `unsafe_allow_html=True`. | UI-SPEC §Color explicitly rejects custom HTML. |
| No `poetry` / `pyproject.toml` for dep pinning — use `requirements.txt`. | Phase 4 adds zero deps; nothing to pin. |
| `plotly` for future viz — NOT used in Phase 4. | Phase 5 owns it. |
| GSD workflow enforcement — no ad-hoc edits. | Research → Plan → Execute sequence. |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | `ViewModel.to_dict()` implemented inline (no new method on `VerdictMatrix`). | Architecture §Pattern 3 | Low — keeps geometry layer untouched; if Phase 5 wants a full matrix serializer it can add one to `VerdictMatrix` then. |
| A2 | Passing `game_date.isoformat()` strings to `st.dataframe` renders as plain YYYY-MM-DD (no DateColumn config needed). | Code Examples | Low — verified via community docs; worst case we add `st.column_config.DateColumn(format="YYYY-MM-DD")` later, no schema change. |
| A3 | `teams.json` fixture has `abbreviation` on every team (used in ViewModel.team_abbr). | Phase Requirements UX-01 | **VERIFIED** — inspected fixture, all 30 teams have `abbreviation`. |

All other load-bearing claims are `[VERIFIED]` against live API fetches (2026-04-15), fixture inspection, or cited Streamlit docs. See §Sources.

---

## Open Questions

### Q1: **D-11 endpoint is wrong — requires CONTEXT amendment**

**What we know `[VERIFIED: live fetch 2026-04-15]`:**
- `GET /teams/147/stats?stats=season&group=hitting&season=2026&sportId=1` returns `stats[0].splits` with **exactly one entry**: the team's aggregate totals (`stat.homeRuns = 19` for the NYY team as a whole, no player info). `split.player` is `{}`. This endpoint CANNOT produce a per-player list.
- `GET /teams/147/roster?rosterType=active&hydrate=person(stats(type=statsSingleSeason,season=2026,group=hitting))` returns `roster` array of 26 entries (for NYY). Each entry has:
  - `position.type` at **top-level** (not nested under `person`) — e.g. `"Outfielder"`, `"Pitcher"`, `"Infielder"`, `"Catcher"`, `"Hitter"` (DH), and would be `"Two-Way Player"` for Ohtani.
  - `person.id`, `person.fullName`.
  - `person.primaryPosition.type` (mirrors `position.type` for hitters; pitchers have it too).
  - `person.stats[0].splits[0].stat.homeRuns` for hitters with ≥1 PA this season. Pitchers have `person.stats == []` (empty list) typically.

**Recommendation:**
- **Amend D-11 to the roster+hydrate endpoint.** Rename the services wrapper is optional (`get_team_hitting_stats` still fits semantically — it's the "per-hitter HR counts for a team" fetch).
- **D-12 is correct as stated** — `position.type != "Pitcher"` is the right filter. The JSON path is confirmed to be **top-level `entry["position"]["type"]`**, not under `player` or `person`. UI-SPEC §Copywriting player-option format remains valid.
- **No further research needed** to plan Phase 4 — the fixture `tests/fixtures/team_stats_147_2026.json` is recorded.

**Proposed CONTEXT amendment text:**
> **D-11 (amended 2026-04-15 per research):** Sort + filter data source: the **active roster endpoint with hydrated season hitting stats**. Add a new services wrapper: `get_team_hitting_stats(team_id: int, season: int) -> list[dict]` calling `GET /teams/{team_id}/roster?rosterType=active&hydrate=person(stats(type=statsSingleSeason,season={season},group=hitting))`. Returns one entry per rostered player (including pitchers — filter via D-12) with top-level `position.type` and nested `person.stats[0].splits[0].stat.homeRuns` (empty list for players with no season splits). One HTTP call per team selection.

### Q2: `VerdictMatrix.to_dict()` existence

`[VERIFIED]` — does NOT exist today (`src/mlb_park/geometry/verdict.py` inspected; `VerdictMatrix` has `iter_records` and `parks_cleared` methods, no `to_dict`). Phase 4 builds a summary dict inside `ViewModel.to_dict()` — **no change to the geometry layer**. Resolved.

### Q3: How to test callbacks without Streamlit runtime?

**Options:**
1. Write callbacks that take `session_state: dict` as an explicit argument (easy to test with a plain dict), and wrap them in `app.py` with the real `st.session_state`. Breaks the on_change signature slightly — callbacks normally take zero args.
2. Use `streamlit.testing.v1.AppTest` — but D-30 defers AppTest to Phase 6.
3. Test against a **shim** that assigns `st.session_state` to a dict-backed mock before import (fragile).

**Recommendation:** Option 1 — define `_reset_children(session_state: dict) -> None` and `_default_home_venue(session_state: dict, teams: list[dict]) -> int | None` as **pure helpers**, then wrap them in the actual zero-arg callbacks that read `st.session_state`. Tests hit the helpers with a plain dict. This preserves D-23's "controller is pure" spirit for the reset logic too and keeps `app.py` thin.

Resolved.

### Q4: Should `totals` be a `dict` or a `Totals` dataclass?

CONTEXT marks this Claude's Discretion. **Recommendation:** Plain `dict[str, int | float]`. Reasons:
- `ViewModel.to_dict()` serialization is trivial.
- Schema is locked in D-09 (5 keys with fixed names); a dict is not looser than a dataclass here because both rely on the same D-09 key names.
- Keeps total LOC in `controller.py` down.
- Phase 6 can promote to a dataclass via the deferred-idea escape hatch.

Resolved.

---

## Sources

### Primary (HIGH confidence)
- **Live API fetch 2026-04-15** — `GET /teams/147/stats?stats=season&group=hitting&season=2026` returns team aggregate (proof of D-11 bug).
- **Live API fetch 2026-04-15** — `GET /teams/147/roster?rosterType=active&hydrate=person(stats(type=statsSingleSeason,season=2026,group=hitting))` returns 26 entries with top-level `position.type` + hydrated hitting splits. Recorded as `tests/fixtures/team_stats_147_2026.json`.
- **Codebase inspection** — `src/mlb_park/services/mlb_api.py`, `src/mlb_park/pipeline/__init__.py`, `src/mlb_park/geometry/verdict.py`, `tests/pipeline/conftest.py`, `src/mlb_park/app.py`, `tests/fixtures/{teams,roster_147}.json`.
- [st.selectbox — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/widgets/st.selectbox) — `index=None`, `placeholder`, `disabled`, `on_change` arguments.
- [Session State — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state) — callback order-of-execution statement.
- [Widget behavior — Streamlit Docs](https://docs.streamlit.io/develop/concepts/architecture/widget-behavior) — widget identity rules.

### Secondary (MEDIUM confidence — verified against multiple sources)
- [GitHub issue #3598: Initializing default session_state value for a selectbox raises ValueError if options change](https://github.com/streamlit/streamlit/issues/3598) — confirms the stale-options crash behavior (Pitfall P-02).
- [GitHub issue #7649: If a selectbox is set to None using a session_state key, interacting with another widget returns first value instead of None](https://github.com/streamlit/streamlit/issues/7649) — relevant caveat for `index=None` + key + callback interplay.
- Streamlit forum search summary (2025 threads) — "session state is updated BEFORE the callback fires" confirmed by multiple community posts + deep-dive articles. Matches official docs' "Order of execution" paragraph.
- [Date display with pandas — Streamlit forum](https://discuss.streamlit.io/t/date-display-with-pandas/38351) — `datetime.date` + `st.dataframe` default rendering behavior.
- [st.column_config.DateColumn](https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.datecolumn) — `format="YYYY-MM-DD"` path if needed.

### Tertiary (reference only)
- CLAUDE.md §Recommended Stack (pre-verified 2026-04-14 per Phase 1 RESEARCH).
- `.planning/phases/03-hr-pipeline/03-CONTEXT.md` — upstream contracts (HREvent, PipelineResult, StubAPI pattern).

---

## Metadata

**Confidence breakdown:**
- Team-stats endpoint shape: **HIGH** — live API fetch 2026-04-15, fixture recorded.
- Streamlit selectbox `index=None` + `on_change` + `placeholder` semantics: **HIGH** — official docs confirm `index=None` and `placeholder` args; `on_change` timing verified via multiple community sources + docs' "Order of execution" statement.
- Stale-session_state crash behavior: **HIGH** — GitHub issue #3598 documents the ValueError explicitly.
- `VerdictMatrix.to_dict()` absence: **HIGH** — source inspection.
- Architecture patterns (pure controller, callback split): **HIGH** — mirrors Phase 3's verified dependency-injection pattern.
- `st.dataframe` + `datetime.date` rendering: **MEDIUM** — forum + docs agree; we mitigate by pre-converting to ISO strings, which is unambiguous.

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (30 days — stable stack, stable endpoint, no upcoming Streamlit major). Re-verify if Streamlit ships a 1.57+ that changes selectbox semantics, or if MLB StatsAPI deprecates the roster hydration path.
