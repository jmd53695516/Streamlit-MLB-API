# Roadmap — Streamlit MLB HR Park Factor Explorer

Version: v1
Created: 2026-04-14
Granularity: standard (5-8 phases, 3-5 plans each)
Source requirements: .planning/REQUIREMENTS.md (18 v1 REQ-IDs)

## Project Goal

Given any MLB hitter, quickly answer "how cheap or no-doubt were their home runs this season?" by comparing each HR's distance and spray angle against every MLB park's fence dimensions — rendered as a spray chart over a selected stadium's outline.

## Phases

- [ ] **Phase 1: Foundation & API Layer** — Pin deps, scaffold module layout, stand up cached HTTP wrappers for all five StatsAPI endpoints with disk-backed venue cache and recorded fixtures.
- [ ] **Phase 2: Models & Geometry** — Pure-function `Park` dataclass, empirically-calibrated coord-to-feet transform, piecewise-linear fence interpolation, per-park HR verdict. Unit-tested, no I/O.
- [ ] **Phase 3: HR Pipeline** — End-to-end `player_id → HREvent[]`: gameLog filter, game-feed walk, null-safe `hitData` extraction with ITP / partial-data flags.
- [ ] **Phase 4: Controller & Selectors UI** — `controller.build_view` + Streamlit shell with cascading Team → Player → Stadium selectors driven by `session_state`; renders raw ViewModel (no chart yet).
- [ ] **Phase 5: Spray Chart Visualization** — Plotly rendering of selected stadium outline, HR scatter color-coded by verdict, hover tooltips.
- [ ] **Phase 6: Summary, Rankings & Polish** — Summary metrics card, best/worst parks ranking, loading spinners, friendly error messages. Ship v1.

## Phase Details

### Phase 1: Foundation & API Layer
**Goal**: A working Python project with five cached HTTP endpoint wrappers, a disk-backed venue cache, and recorded JSON fixtures — validated via a scratch script, no UI.
**Depends on**: Nothing (first phase)
**Requirements**: DATA-04
**Success Criteria** (what must be TRUE):
  1. Running a scratch script hits all five endpoints (`teams`, `roster`, `gameLog`, `game_feed`, `venue`) and returns parsed JSON.
  2. Every endpoint wrapper is decorated with `@st.cache_data` and an explicit per-endpoint TTL (venues 24h / 30d disk, teams 24h, roster 6h, gameLog 1h, completed feeds 7d).
  3. A cold second run loads all 30 venues from `data/venues_cache.json` without hitting the network.
  4. `tests/fixtures/` contains recorded JSON for at least one team, roster, gameLog, game feed, and venue — usable by later phases without network access.
  5. `requirements.txt` pins streamlit>=1.55,<2.0, requests 2.32.x, plotly 6.7, pandas 2.2.x, and installs cleanly in a fresh venv.
**Plans**: 3 plans
- [x] 01-01-PLAN.md — Scaffold package, pin deps, config constants (Wave 1)
- [x] 01-02-PLAN.md — Five cached HTTP wrappers + disk-backed venue cache (Wave 2)
- [x] 01-03-PLAN.md — Smoke page, fixture recorder, human-verified end-to-end (Wave 3)

### Phase 2: Models & Geometry
**Goal**: Pure-function, I/O-free geometry layer with an empirically-calibrated coordinate transform, fence interpolation, and per-park verdict — 100% unit-testable without any network.
**Depends on**: Phase 1 (fixtures provide a known HR to calibrate against)
**Requirements**: GEO-01, GEO-02, GEO-03
**Success Criteria** (what must be TRUE):
  1. `coords_to_feet(coordX, coordY)` produces a distance within ~10% of `hitData.totalDistance` for a known HR fixture (calibration task — origin and ft-per-unit documented in `config.py`).
  2. `fence_distance_at(park, angle_deg)` returns exact fence values at the six/seven labeled angles and piecewise-linearly interpolated values between them, clamped at ±45°.
  3. `clears_fence(hr_distance, spray_deg, park)` returns a bool matching hand-computed verdicts for fixture HRs at 3+ parks (one home, one cheap, one pitcher-friendly).
  4. All geometry functions run with zero imports from `requests` or `streamlit` (verified by import check).
**Plans**: 3 plans
- [ ] 02-01-PLAN.md — pytest harness + scipy-free calibration fit + committed CALIB_* constants (Wave 1)
- [ ] 02-02-PLAN.md — transform (gameday→angle/distance) + Park dataclass + load_parks + 5pt/7pt fence interp (Wave 2)
- [ ] 02-03-PLAN.md — HitData + VerdictMatrix + compute_verdict_matrix + 6×30 integration golden test (Wave 3)

### Phase 3: HR Pipeline
**Goal**: Given a `player_id`, produce a list of `HREvent` objects with per-HR degradation flags, validated end-to-end against fixtures before any UI exists.
**Depends on**: Phase 1 (API client), Phase 2 (models)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-05
**Success Criteria** (what must be TRUE):
  1. `extract_hrs(player_id, season)` filters gameLog to `homeRuns >= 1` games *before* fetching any game feed, and returns one `HREvent` per HR attributed to that batter.
  2. HRs with missing or partial `hitData` (inside-the-park, pre-Statcast, review-reversed) are retained with explicit flags (`has_distance`, `has_coords`, `is_itp`), not dropped or crashed on.
  3. A disk-backed venue cache (`data/venues_cache.json`, 30-day TTL) is populated on first run and reused on subsequent cold starts.
  4. Pipeline is testable with a stub `api` module — fixture-driven tests pass without network access.
**Plans**: TBD

### Phase 4: Controller & Selectors UI
**Goal**: Thinnest Streamlit app that proves the three cascading selectors + ViewModel pipeline work end-to-end, rendering a raw JSON/dataframe dump (deferring the chart).
**Depends on**: Phase 3
**Requirements**: UX-01, UX-02, UX-03, UX-04
**Success Criteria** (what must be TRUE):
  1. User can select any of the 30 MLB teams from a dropdown.
  2. After selecting a team, the player dropdown shows that team's non-pitcher hitters sorted by current-season HR count descending.
  3. After selecting a player, the stadium dropdown defaults to the player's home park; user can override to any of the 30 parks.
  4. Changing the team clears the player selection; changing the player resets the stadium to the player's home park (managed via `st.session_state`).
  5. A raw `ViewModel` dump (JSON or dataframe) renders below the selectors, proving the controller pipeline is wired end-to-end.
**Plans**: TBD
**UI hint**: yes

### Phase 5: Spray Chart Visualization
**Goal**: Render the ViewModel as a Plotly spray chart: selected stadium outline in feet, all HRs plotted and color-coded by whether they clear that stadium, hover tooltips with per-HR detail.
**Depends on**: Phase 4
**Requirements**: VIZ-01, VIZ-02, VIZ-03
**Success Criteria** (what must be TRUE):
  1. Selected stadium's outline (home plate → 6 fence points → home) plus foul lines render correctly scaled in feet, with LF/CF/RF orientation.
  2. Every player HR appears as a dot at its `(spray_angle, totalDistance)` location on the chart.
  3. Each HR dot is green if it clears the selected stadium's fence, red if not.
  4. Hovering an HR dot shows a tooltip with date, opponent, distance (ft), exit velocity, launch angle, and "parks cleared out of 30".
**Plans**: TBD
**UI hint**: yes

### Phase 6: Summary, Rankings & Polish
**Goal**: Ship v1 — summary metrics card, best/worst parks ranking, loading spinners, friendly error messages. Complete the user-observable surface.
**Depends on**: Phase 5
**Requirements**: VIZ-04, VIZ-05, UX-05
**Success Criteria** (what must be TRUE):
  1. A summary card (`st.metric`) displays total HRs, average parks cleared (of 30), count of no-doubters (30/30), and count of cheap HRs (≤5/30).
  2. A "best and worst parks for this player" section ranks the top 3 parks where the most of this player's HRs clear and the bottom 3 where the fewest clear.
  3. While data is being fetched (gameLog, game feeds), a loading spinner is visible to the user.
  4. When an API fetch fails, a friendly `st.error` explains what happened and offers a retry action that clears the offending cache entry.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & API Layer | 0/3 | Not started | - |
| 2. Models & Geometry | 0/3 | Not started | - |
| 3. HR Pipeline | 0/? | Not started | - |
| 4. Controller & Selectors UI | 0/? | Not started | - |
| 5. Spray Chart Visualization | 0/? | Not started | - |
| 6. Summary, Rankings & Polish | 0/? | Not started | - |

## Coverage Validation

All 18 v1 requirements mapped to exactly one phase:

| Category | REQ-IDs | Phase |
|----------|---------|-------|
| UX | UX-01, UX-02, UX-03, UX-04 | Phase 4 |
| UX | UX-05 | Phase 6 |
| DATA | DATA-04 | Phase 1 |
| DATA | DATA-01, DATA-02, DATA-03, DATA-05 | Phase 3 |
| GEO | GEO-01, GEO-02, GEO-03 | Phase 2 |
| VIZ | VIZ-01, VIZ-02, VIZ-03 | Phase 5 |
| VIZ | VIZ-04, VIZ-05 | Phase 6 |

Total: 18/18 requirements mapped, no orphans, no duplicates.

## Research Flags

- **Phase 2** contains a **coord-calibration task**: the Gameday coordinate origin (~125, ~199) and ft-per-unit scale (2.29–2.5) are community-reported, not official. Must calibrate empirically against a known HR fixture's `totalDistance` during planning.
- **Phase 3** needs deeper research on exact `hitData` location within `playEvents` and the full set of HR `result.eventType` values (including ITP / reversed plays).

---
*Last updated: 2026-04-14 after initial roadmap creation*
