---
phase: 04-controller-selectors-ui
plan: 01
subsystem: controller
tags: [infrastructure, types, services, test-scaffolding]
requirements: []
dependency-graph:
  requires:
    - mlb_park.pipeline (Phase 3 public surface)
    - mlb_park.geometry.verdict.VerdictMatrix (type reference only)
    - tests/pipeline/conftest.py::StubAPI
  provides:
    - mlb_park.services.mlb_api.get_team_hitting_stats (D-11 amended)
    - mlb_park.controller.ViewModel (frozen dataclass + to_dict)
    - mlb_park.pipeline.load_parks (re-export for D-02)
    - tests/controller/conftest.py::ControllerStubAPI + factory
    - 3 new team-stats fixtures for downstream filter/sort/empty tests
  affects:
    - Plan 04-02 (build_view implementation consumes these contracts)
    - Plan 04-03 (Streamlit selectboxes consume ViewModel)
tech-stack:
  added: []
  patterns:
    - services/_raw_* + @st.cache_data public wrapper pair (mirrors Phase 1)
    - frozen dataclass + to_dict() JSON projection (D-06, D-24 scope)
    - StubAPI subclass for dependency-injection controller tests
key-files:
  created:
    - src/mlb_park/controller.py
    - tests/controller/__init__.py
    - tests/controller/conftest.py
    - tests/controller/test_view_model.py
    - tests/services/__init__.py
    - tests/services/test_team_hitting_stats.py
    - tests/fixtures/team_stats_empty.json
    - tests/fixtures/team_stats_all_pitchers.json
    - tests/fixtures/team_stats_zero_hr_player.json
  modified:
    - src/mlb_park/services/mlb_api.py (added _raw_team_hitting_stats + get_team_hitting_stats)
    - src/mlb_park/pipeline/__init__.py (re-export load_parks, D-02)
decisions:
  - ViewModel.verdict_matrix serialized via controller-scoped summary (shape/venue_ids/cleared_per_park) rather than adding a to_dict() to the geometry dataclass (D-24).
  - totals field typed dict[str, int|float] — no dedicated Totals dataclass (D-09 Claude's-discretion).
  - VerdictMatrix imported from mlb_park.geometry.verdict as a type reference only; runtime calls route through mlb_park.pipeline (D-02 spirit preserved).
  - get_team_hitting_stats TTL="1h" (D-14, matches gameLog TTL; hydrated hitting stats refresh with same cadence as per-game logs).
metrics:
  duration: ~30 min
  completed: 2026-04-15
  tasks_completed: 3
  tests_added: 9 (4 services + 5 controller)
  full_suite: 74 passed
---

# Phase 04 Plan 01: Controller Infrastructure Summary

**One-liner:** Landed the type-level Phase 4 foundations — new services wrapper `get_team_hitting_stats` (D-11 amended endpoint), frozen `ViewModel` dataclass with JSON-safe `to_dict()` (D-06 schema), and controller test scaffolding (ControllerStubAPI + 3 synthetic team-stats fixtures), so Plan 04-02's `build_view` can be implemented against frozen contracts.

## Commits

| Task | Commit  | Message |
|------|---------|---------|
| 1 RED   | `5ce5e8d` | `test(04-01): add failing tests for get_team_hitting_stats wrapper` |
| 1 GREEN | `c03f58d` | `feat(04-01): add get_team_hitting_stats services wrapper (D-11 amended)` |
| 2 RED   | `b466dd1` | `test(04-01): add failing tests for ViewModel + load_parks re-export` |
| 2 GREEN | `5b0aa57` | `feat(04-01): add ViewModel dataclass + load_parks re-export (D-02, D-06)` |
| 3       | `045551e` | `test(04-01): scaffold controller test infra + 3 team-stats fixtures` |

## New Services Wrapper

**Signature** (src/mlb_park/services/mlb_api.py):

```python
@st.cache_data(ttl="1h", show_spinner=False)
def get_team_hitting_stats(team_id: int, season: int) -> list[dict]:
    """Active roster hydrated with per-player single-season hitting stats."""
    return _raw_team_hitting_stats(team_id, season)

def _raw_team_hitting_stats(team_id: int, season: int) -> list[dict]:
    # GET /teams/{team_id}/roster
    #   ?rosterType=active
    #   &hydrate=person(stats(type=statsSingleSeason,season={season},group=hitting))
```

- SSRF guard (T-4-01): `team_id` and `season` asserted `int`.
- Empty-roster (D-15) short-circuit: `resp.get("roster", [])` returns `[]` without KeyError.
- TTL = `"1h"` (D-14, matches gameLog).

## ViewModel Schema (verbatim D-06)

```python
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
```

### `to_dict()` JSON Projection

- Scalars → pass-through with coercion (`int/str/bool/float`).
- `events`, `plottable_events` → `list[dict]` (HREvent fields; `game_date.isoformat()`).
- `verdict_matrix` → RESEARCH-prescribed summary (or `None`):
  ```python
  {
      "shape": list(matrix.cleared.shape),              # [n_hrs, 30]
      "venue_ids": [int(v) for v in matrix.venue_ids],  # 30 ints
      "cleared_per_park": {
          int(vid): int(matrix.cleared[:, j].sum())
          for j, vid in enumerate(venue_ids)
      },
  }
  ```
  D-24 scope: geometry layer remains unchanged — no `VerdictMatrix.to_dict()` method added.
- `errors` → `list[{game_pk: int|None, endpoint: str, message: str}]`.
- Tuples → lists; `json.dumps(vm.to_dict())` is guaranteed safe.

## `load_parks` Re-export (D-02)

`src/mlb_park/pipeline/__init__.py` now re-exports `load_parks` from `mlb_park.geometry.park`. Phase 4 controllers import everything runtime-relevant from `mlb_park.pipeline`; `VerdictMatrix` is imported from `mlb_park.geometry.verdict` as a type annotation reference only.

## Test Infrastructure

**`tests/controller/conftest.py::ControllerStubAPI`** subclasses `tests/pipeline/conftest.py::StubAPI` and adds:

- `get_teams() -> list[dict]` — returns canned teams list (empty default).
- `get_team_hitting_stats(team_id, season) -> list[dict]` — keyed by `team_id`; season arg ignored.
- `MLBAPIError` class attribute inherited, so `except api.MLBAPIError:` works on stub-raised errors.

Factory fixture `make_controller_stub_api` mirrors the Phase 3 pattern.

Session-scoped fixture loaders (T-4-04 hard-constrained to `tests/fixtures/`):
- `team_stats_nyy_2026` → real Yankees 2026 roster (37 entries).
- `team_stats_empty` → `[]`.
- `team_stats_all_pitchers` → 13 NYY pitchers (subset of the real fixture).
- `team_stats_zero_hr_player` → 1 outfielder with `homeRuns=0`.

## Fixture Inventory

| Fixture                                 | Shape | Count | Purpose |
|-----------------------------------------|-------|-------|---------|
| team_stats_147_2026.json (existing)     | `{"roster": [...]}` | 37 | Real Yankees + hitting stats — happy path |
| team_stats_empty.json (NEW)             | `{"roster": []}`    | 0  | D-15 empty-roster edge |
| team_stats_all_pitchers.json (NEW)      | `{"roster": [...]}` | 13 | Hitter-filter test (all filtered out) |
| team_stats_zero_hr_player.json (NEW)    | `{"roster": [...]}` | 1  | 0-HR-player edge (sort/empty UI branch) |

## Deviations from Plan

None — plan executed as written. Minor note: `conftest.py` imports from `tests.pipeline.conftest` (package import) rather than re-authoring the `StubAPI` class, preserving a single source of truth for the stub surface.

## Verification

- `pytest tests/services/test_team_hitting_stats.py -q` → 4 passed
- `pytest tests/controller/test_view_model.py -q` → 5 passed
- `pytest tests/ -q` → **74 passed** (full regression guard green)
- `python -c "from mlb_park.pipeline import load_parks; print(load_parks)"` → no ImportError
- No `import streamlit` line in `src/mlb_park/controller.py` (docstring mention only)

## Success Criteria

- [x] `get_team_hitting_stats(team_id, season)` importable from `mlb_park.services.mlb_api`, decorated `@st.cache_data(ttl="1h")`, returns the `roster` list (D-11 amended).
- [x] `load_parks` re-exported via `mlb_park.pipeline` (D-02).
- [x] `ViewModel` frozen dataclass matches D-06 schema exactly.
- [x] `ViewModel.to_dict()` round-trips through `json.dumps` and emits the RESEARCH-prescribed `verdict_matrix` summary shape.
- [x] `ControllerStubAPI` factory + 4 team-stats fixture loaders in `tests/controller/conftest.py`.
- [x] Three new synthetic fixtures valid JSON with a `roster` root key.
- [x] Full test suite green (74 passed).

## Known Stubs

None — this plan lands infrastructure only. `build_view` (Plan 04-02) is deliberately not present per the plan's scope ("Do NOT implement `build_view` or helpers in this plan").

## Self-Check: PASSED

Files verified on disk:
- `src/mlb_park/controller.py` FOUND
- `src/mlb_park/services/mlb_api.py` FOUND (with `_raw_team_hitting_stats` + `get_team_hitting_stats`)
- `src/mlb_park/pipeline/__init__.py` FOUND (with `load_parks` in `__all__`)
- `tests/controller/__init__.py` FOUND
- `tests/controller/conftest.py` FOUND
- `tests/controller/test_view_model.py` FOUND
- `tests/services/__init__.py` FOUND
- `tests/services/test_team_hitting_stats.py` FOUND
- `tests/fixtures/team_stats_empty.json` FOUND
- `tests/fixtures/team_stats_all_pitchers.json` FOUND
- `tests/fixtures/team_stats_zero_hr_player.json` FOUND

Commits verified:
- `5ce5e8d` FOUND
- `c03f58d` FOUND
- `b466dd1` FOUND
- `5b0aa57` FOUND
- `045551e` FOUND
