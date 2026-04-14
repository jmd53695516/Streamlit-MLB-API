# Project Research Summary

**Project:** Streamlit MLB HR Park Factor Explorer
**Domain:** Single-user Streamlit data-viz hobby app over unofficial MLB StatsAPI
**Researched:** 2026-04-14
**Confidence:** HIGH on stack, features, and architecture patterns; MEDIUM on Gameday coordinate constants (must be calibrated empirically in Phase 2)

## Executive Summary

This is a well-trodden genre — a Baseball-Savant-style spray chart / HR verdict app — built on a deliberately minimal Python data-viz stack (Streamlit + requests + Plotly + pandas) and a single unofficial JSON API (`statsapi.mlb.com/api/v1`). The engineering is straightforward: five cached HTTP wrappers, a pure-function HR pipeline, a pure-function park-geometry module, and a thin controller/view layer. No database, no async, no auth, no scaling dimension that matters.

The recommended approach is to keep every piece boring and composable: one `mlb_api.py` that is the only module holding `requests` and `@st.cache_data`, a `park_model.py` that does 1-D linear interpolation of fence distance by spray angle (not shapely, not splines), and a `plotting.py` that receives fully-resolved data and renders with Plotly. Cascading Team → Player → Stadium selectors drive a controller returning a `ViewModel` the UI renders declaratively. Plotly is chosen over matplotlib specifically to unlock the hover-tooltip differentiator for near-zero additional cost.

The two non-trivial risks are (1) the Gameday coordinate system — Y is inverted, origin is pixel-space near (125, 199), scale factor around 2.29–2.5 ft/unit, and none of this is officially documented — which demands a one-time empirical calibration against a known HR's `totalDistance`; and (2) the unofficial API's fan-out problem, where a 30-HR hitter spread across ~28 games needs ~28 `game/{pk}/feed/live` fetches (1–5 MB each) on cold load — solved with aggressive `st.cache_data` TTLs plus a disk-backed venue cache and gameLog-filtered fetch (never fetch all 162 games). Missing/partial `hitData` on ITP HRs, rain-shortened games, and review-reversed plays is the third material hazard; defensive `.get()` chains and per-HR degradation handle it.

## Key Findings

### Recommended Stack

Minimal 4-dependency Python stack pinned to April-2026 versions. Everything else transitive or explicitly rejected (shapely, httpx, polars, requests-cache, matplotlib-as-primary).

- **Python 3.12 + uv + flat requirements.txt** — zero-ceremony; drop-in pip replacement.
- **Streamlit 1.56** (`>=1.55,<2.0`) — locked by PROJECT.md; 1.55+ `on_change` / URL `bind=` improve cascading selectors.
- **requests 2.32.x** — sync matches Streamlit's rerun model; no concurrency win justifies httpx.
- **plotly 6.7** — polygon overlay + scatter + hover is Plotly's sweet spot; unlocks hover-tooltip differentiator for free.
- **pandas 2.2.x** — native `st.dataframe` / `st.data_editor`; data volume (<2K rows) makes polars overkill.
- **Caching:** `@st.cache_data(ttl=...)` only; no `requests-cache`. Venues 24h–30d with disk fallback, teams 7d, roster 6h, gameLog 1h, completed feeds 7d.
- **Geometry:** `math.atan2` + `numpy.interp` — 1-D linear interp in angle-space. Shapely rejected (wrong primitive for v1).

### Expected Features

Benchmarked against Baseball Savant HR Tracking + Spray Chart, scoped to single-player / single-stadium.

**Table stakes (v1):**
- Cascading Team → Player → Stadium selectors with `session_state` guards.
- Roster filtered to non-pitcher hitters, sorted by HR count desc.
- Summary card (`st.metric`): total HRs, avg parks cleared / 30, no-doubters (30/30), cheap HRs (≤5/30).
- Spray chart: stadium outline from `fieldInfo`, HR dots colored by verdict, foul lines, feet labels, LF/CF/RF orientation.
- Per-HR table: date, distance, EV, LA, parks cleared / 30.
- Loading spinner, empty-state ("0 HRs"), friendly API-error messages, wall-height caveat in-UI.

**Differentiators (v1.x):**
- Plotly hover tooltips per HR dot (pitcher, date, EV/LA, parks cleared) — highest effort-to-wow ratio.
- "Best/worst park for this player" ranking.
- Cheap-HR threshold slider; URL query-param state; click-HR → show parks that made the difference.

**Deferred (v2+):**
- Wall-height modeling; career/multi-season; park factors; video link-outs; league-avg annotations; all-30-parks overlay; opponent/date filters.

### Architecture Approach

Flat, layered Python package where imports flow strictly downward: `app.py → controller.py → services/{hr_pipeline, park_model, plotting} → services/mlb_api.py → statsapi.mlb.com`. Only `mlb_api.py` touches `requests` and `@st.cache_data`. `park_model.py` and `plotting.py` are I/O-free pure functions. A single `ViewModel` dataclass carries fully-resolved data from controller to UI.

**Modules:**
1. **`app.py`** — Streamlit layout, selectors, session state, calls controller. No HTTP, no math.
2. **`controller.py`** — `build_view(team_id, player_id, venue_id) -> ViewModel`.
3. **`services/mlb_api.py`** — One cached function per endpoint. Sole home of `requests` and `st.cache_data`.
4. **`services/hr_pipeline.py`** — gameLog → HR-games filter → game feeds → `HREvent[]` with null-safe extraction.
5. **`services/park_model.py`** — `Park` dataclass from `fieldInfo`; `fence_distance_at(angle)` via piecewise-linear interp; `clears_fence(...)`.
6. **`services/plotting.py`** — Renders stadium polygon + HR scatter from resolved `Park` + `HREvent[]`. No fetching.
7. **`models.py`** — Neutral shared dataclasses (avoids import cycles).
8. **`data/venues_cache.json`** — Disk-backed venue cache, TTL 30 days.

### Critical Pitfalls

1. **Gameday coordinate inversion + unknown scale.** Y points *down*; origin ~(125, 199) pixels; scale 2.29–2.5 ft/unit (community-reported). Isolate in one `coords_to_feet()`, use `hitData.totalDistance` as authoritative distance (coords only for angle), calibrate empirically before trusting output.
2. **Missing / partial `hitData`.** ITPs, review-reversed plays, rain-shortened games, spring training, pre-Statcast feeds can have `hitData: {}`. Treat every field as Optional, use `.get()` chains, degrade per-HR rather than crash, explicitly flag ITPs.
3. **Fan-out / rate-limiting.** ~28 game-feed calls per 30-HR player at 1–5 MB each. Filter gameLog to `homeRuns > 0` *before* fetching feeds; aggressive TTLs; disk fallback for venues; polite User-Agent.
4. **Fence interpolation kinks.** 6–7 `fieldInfo` points at non-uniform angles; naive index-lerp or cubic splines produce phantom "cleared" verdicts near foul poles. Piecewise-linear in *angle space*.
5. **Same-name players + mid-season trades.** Always key on `personId`, names for display only.
6. **Streamlit version skew.** `st.cache` removed; `experimental_rerun` → `rerun`; async unsupported in `@st.cache_data`. Pin `streamlit>=1.55,<2.0`.

## Implications for Roadmap

Suggested 7-phase build order matching strict downward architecture dependency, pushing the biggest technical risks (coord calibration, `hitData` shape) into isolated phases where fixtures and unit tests can solve them before UI exists.

### Phase 0: Scaffolding
Pin versions early. Delivers `requirements.txt`, `uv venv`, skeleton, `.streamlit/config.toml`, README stub with wall-height caveat.

### Phase 1: API Layer + Fixtures
Nail HTTP + caching and record fixtures before anything depends on it. Delivers `services/mlb_api.py` with 5 cached endpoint functions, timeout + retry, disk-backed venue cache, `tests/fixtures/*.json`. Validated via scratch script, no UI.

### Phase 2: Models + Geometry
Pure-function, I/O-free, 100% unit-testable. Delivers `models.py`, `services/park_model.py` with `fence_distance_at`, `clears_fence`, `coords_to_feet` with empirically-calibrated constants, full unit tests.

### Phase 3: HR Pipeline
End-to-end "player_id → HREvent[]" green over fixtures. Delivers `services/hr_pipeline.py`; null-safe `hitData` extraction; ITP classifier; per-HR degradation flags.

### Phase 4: Controller + Minimal UI
Thinnest Streamlit app that proves the three cascading selectors + ViewModel pipeline work end-to-end. Defer plotting. Delivers `controller.build_view`, `app.py` with selectors, raw JSON/dataframe dump.

### Phase 5: Spray Chart Plotting
Render ViewModel with Plotly. Stadium polygon + foul lines + home plate + HR scatter color-coded by verdict.

### Phase 6: Summary, Table, Polish
Ship v1. `st.metric` summary, per-HR `st.dataframe`, spinners, friendly error UX, empty states, wall-height caveat, cache freshness indicator.

### Phase 7 (optional): Differentiators
Hover tooltips, best/worst park ranking, threshold slider, URL query params.

### Phase Ordering Rationale

- Dependency direction matches architecture (bottom-up, every phase testable without consumers).
- Risk front-loaded: biggest unknowns (coord calibration P2; `hitData` shape P3) resolved before any UI.
- No UI until pipeline is green (Phase 4 renders JSON, not chart).
- Plotting is one phase, not scattered.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Geometry):** Coord constants are community-reported. Needs calibration task.
- **Phase 3 (HR Pipeline):** Exact `hitData` location within `playEvents`; full set of HR `result.eventType` values (including ITP, reversed).

Phases with standard patterns (skip research-phase): 0, 1, 4, 5, 6, 7.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified against April-2026 PyPI; all mutually compatible. |
| Features | HIGH | Domain well-trodden; PROJECT.md explicit on anti-features. |
| Architecture | HIGH | Cached HTTP + pure-function pipeline + ViewModel are canonical Streamlit idioms. |
| Pitfalls | MEDIUM–HIGH | Clear provenance. Unofficial API can drift silently; fixtures mitigate. |

**Overall confidence:** HIGH

### Gaps to Address

- Coord calibration against known HR's `totalDistance` in P2.
- `playId` availability for deferred video link-out differentiator.
- `fieldInfo` mid-season dimension changes (Camden Yards) — document as caveat.
- `gameType` filter decision (regular-season only vs include postseason).
- Plotly rendering of non-convex stadium polygons (verify in P5).

## Sources

### Primary (HIGH confidence)
- [Streamlit 2026 release notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2026)
- [Streamlit `st.cache_data` docs](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data)
- [Streamlit caching architecture](https://docs.streamlit.io/develop/concepts/architecture/caching)
- [plotly on PyPI](https://pypi.org/project/plotly/) — 6.7.0
- [streamlit on PyPI](https://pypi.org/project/streamlit/) — 1.56.0
- [uv docs: pip-to-uv migration](https://docs.astral.sh/uv/guides/migration/pip-to-project/)
- [Baseball Savant HR Tracking](https://baseballsavant.mlb.com/leaderboard/home-runs)
- [MLB StatsAPI venue example](https://statsapi.mlb.com/api/v1/venues/2681?hydrate=location,fieldInfo)
- [streamlit/streamlit #11528](https://github.com/streamlit/streamlit/issues/11528)
- [streamlit/streamlit #8308](https://github.com/streamlit/streamlit/issues/8308)

### Secondary (MEDIUM confidence)
- [andschneider.dev: Reverse engineering MLB Gameday](https://www.andschneider.dev/post/mlb-reverse-eng-part1/)
- [indiemaps: visualizing MLB hit locations](https://indiemaps.com/blog/2009/07/visualizing-mlb-hit-locations-on-a-google-map/)
- [Seamheads Ballparks Database](https://www.seamheads.com/ballparks/about.php)
- [FanGraphs: Camden Yards 2022 dimensions](https://blogs.fangraphs.com/wall-over-but-the-shoutin-camden-yards-gets-new-dimensions/)
- [ESPN: Orioles 2024→2025 wall move](https://www.espn.com/mlb/story/_/id/42413260/orioles-set-again-move-left-field-wall-camden-yards)

### Tertiary (LOW confidence — validate during implementation)
- Gameday coord origin `(~125, ~199)` and scale `~2.29–2.5` ft/unit — calibrate in P2.
- `playId`-to-MLB-Film-Room URL pattern.
