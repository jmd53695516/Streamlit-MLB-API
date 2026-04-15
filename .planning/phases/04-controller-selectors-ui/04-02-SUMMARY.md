---
phase: 04-controller-selectors-ui
plan: 02
subsystem: controller
tags: [composition, pipeline, verdict-matrix, tdd]
requirements: [UX-01, UX-02]
dependency-graph:
  requires:
    - mlb_park.controller.ViewModel            (Plan 04-01 contract)
    - mlb_park.services.mlb_api.get_team_hitting_stats (Plan 04-01)
    - mlb_park.pipeline.extract_hrs            (Phase 3)
    - mlb_park.pipeline.hr_event_to_hit_data   (Phase 3)
    - mlb_park.pipeline.compute_verdict_matrix (Phase 2)
    - mlb_park.pipeline.load_parks             (D-02 re-export)
  provides:
    - mlb_park.controller.build_view
    - mlb_park.controller._sorted_teams
    - mlb_park.controller._sorted_hitters
    - mlb_park.controller._clears_for_venue    (private; lookup column of VerdictMatrix.cleared)
    - mlb_park.controller._compute_totals      (private; 5-key D-09 dict)
  affects:
    - Plan 04-03 (Streamlit shell calls build_view + uses the two _sorted_* helpers)
tech-stack:
  added: []
  patterns:
    - Dependency injection at module boundary (api: Any = None, lazy services import)
    - Positional alignment of VerdictMatrix columns (D-08) — no identifier keying
    - Defensive fallbacks for missing StatsAPI fields (position, homeRuns)
key-files:
  created:
    - tests/controller/test_build_view.py
    - tests/controller/test_helpers.py
    - tests/controller/test_purity.py
  modified:
    - src/mlb_park/controller.py
decisions:
  - D-21 soft cap (≤200 LOC) exceeded by 5 LOC at code-only count (205) / 351 raw; declined the pre-approved package split — the overage is docstring-heavy heritage from Plan 04-01 and splitting for 5 LOC is churn without benefit. Flagged for future revisit.
  - Stadium-flip test uses Yankee Stadium ↔ Citi Field (not Fenway). Judge's 6 real 2026 HRs all clear Yankee + Fenway identically; only Citi Field (venue 19) in the fixture set has one HR that falls short, making the bool-tuple difference detectable. A CITI_FIELD constant + inline comment documents the reason.
  - Local `from mlb_park.services import mlb_api as api` lives INSIDE build_view (only when api is None) rather than at module top. This keeps controller.py importable without Streamlit's cache_data shims during isolated unit tests.
metrics:
  duration: ~40 min
  completed: 2026-04-15
  tasks_completed: 2
  tests_added: 18 (9 helpers + 2 purity + 7 build_view)
  full_suite: 92 passed
---

# Phase 04 Plan 02: build_view + Controller Helpers Summary

**One-liner:** Landed `build_view(team_id, player_id, venue_id, *, season, api)` — the pure composition entry-point that fuses services, the Phase 3 HR pipeline, and the Phase 2 verdict matrix into a `ViewModel` — plus the `_sorted_teams` / `_sorted_hitters` UI helpers, all TDD-driven with 18 new tests (92/92 full suite green, zero streamlit coupling).

## Commits

| Task | Commit    | Message |
|------|-----------|---------|
| 1 RED   | `21edbcb` | `test(04-02): add failing tests for _sorted_teams, _sorted_hitters, purity guard` |
| 1 GREEN | `15932af` | `feat(04-02): implement _sorted_teams and _sorted_hitters helpers` |
| 2 RED   | `fc8fc99` | `test(04-02): add failing tests for build_view composition` |
| 2 GREEN | `38da5bb` | `feat(04-02): implement build_view composing services + pipeline + verdict matrix` |

## build_view Algorithm — Steps 1–6

```
build_view(team_id, player_id, venue_id, *, season=None, api=None)
  │
  ├─ 1. Selection-context lookups
  │     teams              = api.get_teams()
  │     team_abbr          = team.abbreviation
  │     player_home_venue  = team.venue.id
  │     roster             = api.get_team_hitting_stats(team_id, season)
  │     player_name        = roster[player_id].person.fullName
  │     parks_dict         = api.load_all_parks()  → {venue_id: venue_dict}
  │     venue_name         = parks_dict[venue_id].name
  │
  ├─ 2. Run Phase 3 pipeline
  │     result             = extract_hrs(player_id, season=season, api=api)
  │                        → PipelineResult{events, errors, season, player_id}
  │
  ├─ 3. Filter plottable (D-07)
  │     plottable = tuple(ev for ev in events if ev.has_distance and ev.has_coords)
  │
  ├─ 4. Verdict matrix (D-10: None when plottable is empty)
  │     if plottable:
  │         hit_data_list  = [hr_event_to_hit_data(ev) for ev in plottable]
  │         park_objs      = load_parks(parks_dict)           # dict[int, Park]
  │         matrix         = compute_verdict_matrix(hit_data_list, park_objs)
  │     else:
  │         matrix         = None
  │
  ├─ 5. clears_selected_park  (D-08, _clears_for_venue)
  │     Positional lookup: find j s.t. matrix.venue_ids[j] == venue_id,
  │     then return tuple(bool(x) for x in matrix.cleared[:, j]).
  │     result[i] aligns with plottable[i] (same order fed to compute_verdict_matrix).
  │
  ├─ 6. totals (D-09, _compute_totals)
  │     {total_hrs, plottable_hrs, avg_parks_cleared, no_doubters, cheap_hrs}
  │
  └─ ViewModel(...)   — immutable, JSON-safe via to_dict()
```

## `_clears_for_venue` — Positional Lookup Mechanism (D-08)

```python
def _clears_for_venue(matrix: VerdictMatrix, venue_id: int) -> tuple[bool, ...]:
    venue_ids_list = matrix.venue_ids.tolist()
    try:
        j = venue_ids_list.index(int(venue_id))
    except ValueError as e:
        raise KeyError(f"venue_id {venue_id} not in verdict matrix") from e
    return tuple(bool(x) for x in matrix.cleared[:, j])
```

**Key insight:** `matrix.cleared` is dense (n_hrs × n_parks). Row `i` corresponds to `matrix.hrs[i]`, which is the i-th `HitData` fed into `compute_verdict_matrix` — and we built that list from `plottable_events` in order, so `result[i]` aligns with `plottable_events[i]`. Column `j` corresponds to `matrix.venue_ids[j]`. The lookup flips the selected park by re-slicing the same matrix by column — no re-computation, O(n_parks) for the index scan.

`KeyError` is raised if `venue_id` is not in `matrix.venue_ids` (shouldn't happen when `load_all_parks()` returns all 30 MLB venues; defensive guard for misconfiguration).

## `_compute_totals` Math (D-09)

| Key | Formula |
|-----|---------|
| `total_hrs`         | `len(events)` |
| `plottable_hrs`     | `len(plottable_events)` |
| `avg_parks_cleared` | `float(matrix.cleared.sum(axis=1).mean())` — 0.0 when matrix is None |
| `no_doubters`       | `int((per_hr_cleared == n_parks).sum())` — 0 when matrix is None |
| `cheap_hrs`         | `int((per_hr_cleared <= 5).sum())` — 0 when matrix is None |

`per_hr_cleared = matrix.cleared.sum(axis=1)` is the per-HR count of parks cleared; `n_parks = matrix.cleared.shape[1]`. For Judge 2026: `per_hr_cleared = [30, 30, 30, 29, 30, 30]` ⇒ `avg=29.83, no_doubters=5, cheap_hrs=0`.

## Helper Functions — `_sorted_teams` / `_sorted_hitters`

**`_sorted_teams`** — `sorted(teams, key=lambda t: t.get("name", ""))`. Stateless, no mutation, empty input → `[]`.

**`_sorted_hitters`** — two-pass: (1) drop entries whose `position.type == "Pitcher"`; (2) sort surviving entries by `(-homeRuns, fullName)`. Missing `position` key ⇒ WARNING via `logging.getLogger("mlb_park.controller")`, entry retained (treated as non-pitcher, D-12 fallback). Missing `person.stats` or `splits` ⇒ `homeRuns = 0` (D-13).

Extracted module-level helpers `_hr_of` and `_name_of` for the sort key to keep the lambda noise-free.

## controller.py LOC — D-21 Status

| Measure | Count | Cap | Result |
|---------|-------|-----|--------|
| Code-only (strip docstrings + comments)  | 205 | ≤ 200 | **+5 over** |
| Raw LOC (includes docstrings)            | 351 | — | informational |

**Decision:** Declined the pre-approved package-split refactor. Rationale:
- The overage is 5 LOC code-only — noise, not a maintainability signal.
- Plan 04-01 already landed ~135 LOC of serialization infrastructure (ViewModel + `to_dict()` + 3 projection helpers) that Plan 04-02 inherited, not introduced.
- Plan 04-02's own additions (`build_view`, `_clears_for_venue`, `_compute_totals`, `_sorted_*`, `_hr_of`, `_name_of`) total ~150 LOC — within a reasonable single-module envelope.
- The downstream consumer (Plan 04-03) imports the public surface (`build_view`, `ViewModel`, `_sorted_teams`, `_sorted_hitters`) from `mlb_park.controller` — a package split would be invisible to callers but introduce import churn.

Flagged for future revisit if Plan 04-03 adds meaningfully to controller.py.

## Phase 2 / Phase 3 Helpers — Nothing Missing

No Phase 2 or Phase 3 helpers were discovered missing. Every piece of what `build_view` composes was already shipped:
- `extract_hrs` + `hr_event_to_hit_data` (Phase 3, Plan 03-02/03)
- `compute_verdict_matrix` + `VerdictMatrix` (Phase 2, Plan 02-03)
- `load_parks` (Phase 2, re-exported from `mlb_park.pipeline` in Plan 04-01 for D-02)
- `get_team_hitting_stats` (Plan 04-01, D-11 amended endpoint)
- `ControllerStubAPI` + `make_controller_stub_api` factory (Plan 04-01)

## Deviations from Plan

### 1. Stadium-flip test — venue_id choice (fixture reality)

- **Found during:** Task 2 GREEN run
- **Issue:** Plan specified `Yankee Stadium (3313)` vs `Fenway (3)`. Judge's 6 real 2026 HRs clear both parks for all 6 HRs — bool tuples are identical `(True,)*6`, test assertion fails.
- **Fix:** Swapped the second venue to Citi Field (venue 19). It is the one park in the 30-venue fixture set where a Judge HR (the 29/30 no-doubters-except-Citi) falls short, making the cross-venue verdict flip observable.
- **Files modified:** `tests/controller/test_build_view.py` (added `CITI_FIELD = 19` constant + comment, replaced `FENWAY_PARK` with `CITI_FIELD` in `test_stadium_flip`).
- **Commit:** `38da5bb`
- **Rule classification:** Rule 1 (bug — test assumption didn't match fixture reality). Does NOT change the behavior under test: the implementation's column-flip mechanism is still what the test exercises.

### 2. D-21 soft-cap overage — declined the pre-approved package split

- **Found during:** Verification phase after Task 2
- **Issue:** `wc -l` = 351, code-only = 205, vs D-21's 200-LOC target.
- **Fix:** Documented the trade-off in the Decisions block above. Functional code is unchanged.
- **Rule classification:** Soft-cap decision, not a correctness issue. Plan 04-02 explicitly pre-approved a refactor pathway but gave the executor room to flag and defer; 5 LOC is noise-level.

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Controller suite          | `pytest tests/controller/ -q`                                        | **23 passed** |
| Full suite                | `pytest tests/ -q`                                                   | **92 passed** |
| Purity (source guard)     | `grep -n "streamlit\|session_state" src/mlb_park/controller.py`      | only docstring mentions (lines 4, 262, 282 — no imports, no runtime references) |
| LOC (raw)                 | `wc -l src/mlb_park/controller.py`                                   | 351 |
| LOC (code-only)           | inline measurement                                                   | 205 |

## Success Criteria

- [x] `build_view` signature matches D-05 exactly (`team_id, player_id, venue_id, *, season, api`).
- [x] All 7 D-29 test cases pass (happy, zero-HR, all-missing-hitData, one-feed-fails, stadium-flip, totals, selection-fields).
- [x] `_sorted_teams` + `_sorted_hitters` pass all 9 helper tests.
- [x] `src/mlb_park/controller.py` contains no `import streamlit` / `from streamlit` / `st.session_state` references.
- [x] `verdict_matrix is None` iff plottable_events empty (D-10).
- [x] `clears_selected_park` derived positionally via `matrix.cleared[:, col_for(venue_id)]`.
- [x] `totals` has exactly 5 keys per D-09.
- [x] Full test suite green (92/92).

## Known Stubs

None — Plan 04-02 lands pure composition logic. The Streamlit shell that wires `build_view` into session_state + selectboxes is Plan 04-03's scope.

## Self-Check: PASSED

Files verified on disk:
- `src/mlb_park/controller.py` FOUND
- `tests/controller/test_build_view.py` FOUND
- `tests/controller/test_helpers.py` FOUND
- `tests/controller/test_purity.py` FOUND

Commits verified (via `git log --oneline 2a8a4fc..HEAD`):
- `21edbcb` FOUND — `test(04-02): add failing tests for _sorted_teams, _sorted_hitters, purity guard`
- `15932af` FOUND — `feat(04-02): implement _sorted_teams and _sorted_hitters helpers`
- `fc8fc99` FOUND — `test(04-02): add failing tests for build_view composition`
- `38da5bb` FOUND — `feat(04-02): implement build_view composing services + pipeline + verdict matrix`
