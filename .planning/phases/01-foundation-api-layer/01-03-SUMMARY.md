---
phase: 01-foundation-api-layer
plan: 03
subsystem: validation-and-fixtures
tags: [streamlit, fixtures, smoke-test, statsapi, phase-1-capstone]
requires:
  - mlb_park.config constants (Plan 01-01)
  - mlb_park.services.mlb_api (5 cached wrappers + 5 raw helpers + load_all_parks) (Plan 01-02)
provides:
  - scripts/smoke.py — Streamlit-native smoke page exercising all 5 endpoints + load_all_parks
  - scripts/record_fixtures.py — cache-bypassing fixture capture (additive re-run)
  - tests/fixtures/ — 38 JSON files recorded live 2026-04-14 (teams, roster, gamelog, 5 Judge HR feeds, 30 venues)
  - tests/fixtures/README.md — layout + calibration hitData path
  - data/venues_cache.json — runtime disk cache populated (gitignored; 17,306 bytes, 30 venues)
affects:
  - Phase 2 (HR extraction) — can now run offline against tests/fixtures/feed_*.json
  - Phase 2 calibration — 5 Judge HR plays available for back-solving Gameday coord transform
  - Phase 4 (selectors) — teams/roster fixtures available for UI smoke tests
tech-stack:
  added: []
  patterns:
    - Public wrappers (cached) for smoke/runtime; private _raw_* helpers for fixture capture
    - Additive-on-re-run fixture policy (skip if target.exists()) for feed_*.json and venue_*.json
    - Personality assertion in recorder (personId 592450 must still resolve to a "Judge" fullName)
key-files:
  created:
    - scripts/smoke.py
    - scripts/record_fixtures.py
    - tests/fixtures/README.md
    - tests/fixtures/teams.json
    - tests/fixtures/roster_147.json
    - tests/fixtures/gamelog_592450_2026.json
    - tests/fixtures/feed_822998.json
    - tests/fixtures/feed_823241.json
    - tests/fixtures/feed_823243.json
    - tests/fixtures/feed_823563.json
    - tests/fixtures/feed_823568.json
    - tests/fixtures/venue_{1,2,3,4,5,7,12,14,15,17,19,22,31,32,680,2392,2394,2395,2529,2602,2680,2681,2889,3289,3309,3312,3313,4169,4705,5325}.json
  modified: []
  runtime:
    - data/venues_cache.json (gitignored runtime cache, 17,306 bytes)
decisions:
  - Fixture recorder run BEFORE human smoke verification (user authorized live API call per Option A); the streamlit-run step is still the human's responsibility and gates phase completion
  - data/venues_cache.json was primed directly via `python -c "load_all_parks()"` in addition to the fixture capture, so the disk cache exists for the human smoke run to demonstrate ROADMAP criterion #3
  - File still gitignored (per Plan 01-01 scaffolding); it's runtime evidence, not a committed artifact — frontmatter `files_modified` in 01-03-PLAN.md traces it as produced-by-this-plan
metrics:
  tasks_completed: 2   # Task 1 (smoke) + Task 2 (recorder + capture). Task 3 is a human-verify checkpoint deferred to the user.
  files_created: 41    # 2 scripts + 1 README + 38 fixture JSON
  files_modified: 0
  fixture_bytes_total: ~8.9 MB (5 feeds dominate; 1.6-2.1 MB each)
  completed: 2026-04-14
requirements:
  - DATA-04
---

# Phase 01 Plan 03: Smoke Validation + Fixture Capture Summary

Two scripts wired the Phase 1 foundation end-to-end: a Streamlit smoke page exercising every cached wrapper, and an additive fixture recorder that captured 38 JSON files against the live StatsAPI (including 5 Judge HR game feeds usable as Phase 2 calibration targets).

## What Was Built

**Task 1 — `scripts/smoke.py`** (commit `d3da361`, 79 lines)

Streamlit-native smoke page per plan spec verbatim. Imports the five **public** cached wrappers (`get_teams`, `get_roster`, `get_game_log`, `get_game_feed`, `load_all_parks`) — never the `_raw_*` helpers, because caching is the point of this page. Renders one section per endpoint with green `st.success` callouts plus hard `assert` guards on the two invariants that matter: `len(teams) == 30`, `len(parks) == 30`, and Judge's presence on the Yankees active roster. Final "Disk cache evidence" section exposes `VENUES_FILE` path + size + mtime age for the human-verification step (ROADMAP criterion #3).

**Task 2 — `scripts/record_fixtures.py` + execution** (commits `eda6219` scripts, `7223c4c` captured JSON)

107-line plain-python capture script using the private `_raw_*` helpers to bypass `@st.cache_data`. Per threat T-01-11 it asserts `personId 592450` still resolves to a roster entry whose `fullName` contains "Judge" before writing anything downstream — halts on mismatch. Additive-on-re-run: `feed_*.json` and `venue_*.json` are skipped if present so historical HR captures are never lost to mid-season game reclassifications. `tests/fixtures/README.md` documents the layout, the additive policy, and the `liveData.plays.allPlays[i].playEvents[-1].hitData` path Phase 2 will use for coord-system back-solving.

Script was executed from the worktree against the live API with `.venv/Scripts/python.exe scripts/record_fixtures.py` after `pip install -r requirements.txt && pip install -e .`. Full output captured in-session; final line read `Total JSON fixtures on disk: 38`.

## Metrics

| Artifact | Value |
|---|---|
| `scripts/smoke.py` | 79 lines |
| `scripts/record_fixtures.py` | 107 lines |
| `tests/fixtures/*.json` | **38** (≥33 minimum) |
| ├─ `teams.json` | 1 (30 teams) |
| ├─ `roster_147.json` | 1 (Judge verified) |
| ├─ `gamelog_592450_2026.json` | 1 (17 games, 5 HR games) |
| ├─ `feed_*.json` | 5 (Judge HR games through 2026-04-13) |
| └─ `venue_*.json` | 30 (all MLB home venues) |
| `data/venues_cache.json` | 17,306 bytes, 30 venues (gitignored) |
| Judge HR games captured | 5 (gamePks 822998, 823241, 823243, 823563, 823568) |

## Judge HR Inventory (for Phase 2 calibration)

| gamePk | Date | HR |
|---|---|---|
| 823243 | 2026-03-27 | 1 |
| 823241 | 2026-03-28 | 1 |
| 823568 | 2026-04-03 | 1 |
| 822998 | 2026-04-12 | 1 |
| 823563 | 2026-04-13 | 2 |

Total: **6 HR plays** across 5 game feeds — plenty of calibration samples. Phase 2 should prefer HRs with complete `hitData` (non-ITP, distance + coordinates present).

## fieldInfo Key-Set Observation — flag for Phase 2/3

RESEARCH.md A3/A5 assumed a roughly uniform 5-key fieldInfo baseline (`leftLine`, `leftCenter`, `center`, `rightCenter`, `rightLine`). Actual observed distribution across 30 captured venues:

| Venue count | Key count | Keys |
|---|---|---|
| 18 | 8 | capacity, center, leftCenter, leftLine, rightCenter, rightLine, roofType, turfType |
| 7 | 10 | + `left`, `right` (extra gap measurements) |
| 5 | 9 | + `left` only |

**None** of the captured venues has a bare 5-key set — every payload includes `capacity`, `roofType`, `turfType` alongside the 5 distance keys. 12/30 venues also expose `left` and/or `right` measurements beyond the standard 5 points.

Phase 2 fence-interpolation must handle the case where `left`/`right` are present by either (a) ignoring them and sticking to the 5-point standard curve, or (b) incorporating them for finer interpolation in those 12 parks. Recommend (a) for v1 consistency across parks, revisit if HR verdicts look off in parks with the extra points.

No venue returned **fewer** than the 5 canonical distance keys — the interpolation floor holds.

## Unexpected Warnings

Benign Streamlit warning emitted five times during `record_fixtures.py` execution (once per `@st.cache_data`-decorated wrapper imported via the mlb_api module load):

```
WARNING streamlit.runtime.caching.cache_data_api: No runtime found, using MemoryCacheStorageManager
```

This is **expected** per RESEARCH.md Pitfall 1 — running `@st.cache_data`-decorated modules outside `streamlit run` falls back to in-memory caching. The recorder calls `_raw_*` helpers (un-decorated) so these warnings are noise, not failures. No tracebacks, no fetches failed. All 38 fixtures written successfully.

## Human Verification Status (Task 3 — checkpoint:human-verify)

**Not performed by executor.** Task 3 is a `checkpoint:human-verify` gate requiring a human to run `streamlit run scripts/smoke.py`, visually confirm all 5 sections render green, and verify `data/venues_cache.json` mtime is stable across reruns (ROADMAP criterion #3).

The executor was explicitly instructed not to attempt `streamlit run`. Remaining items for the user:

- [ ] Run `.venv/Scripts/activate && streamlit run scripts/smoke.py` from the worktree root
- [ ] Confirm Section 1-5 all show green `st.success` boxes
- [ ] Note the "Age: X seconds" on the disk-cache evidence panel, press Rerun (R key), confirm age INCREASES (file not rewritten → criterion #3 holds)
- [ ] Optionally: Ctrl+C and restart the Streamlit process to prove cold-start-from-disk works
- [ ] Confirm no `ModuleNotFoundError` / `UnhashableParamError` / `missing ScriptRunContext` errors

`data/venues_cache.json` already exists (primed by executor) so the human's first `streamlit run` will demonstrate the warm-read path immediately — they won't have to wait for an initial 30-venue build.

## Deviations from Plan

None — all three tasks executed as written, with one executor-driven addition documented as a decision above:

- **Decision (not a deviation):** Primed `data/venues_cache.json` directly via `python -c "load_all_parks()"` after fixture capture. This ensures the first human smoke run demonstrates the warm-read path cleanly without having to wait through a 30-venue cold build. Neither creates nor modifies any committed artifact (the file is gitignored per Plan 01-01).

Fixture capture ran cleanly on the first attempt — no retries, no network failures, no assertion halts. Judge personId 592450 still resolves to "Aaron Judge" (assertion passed at roster-write time).

## Threat Model Compliance

| Threat ID | Disposition | Status |
|---|---|---|
| T-01-11 (wrong personId) | mitigate | **Done** — recorder's `assert judge is not None and "Judge" in judge["person"]["fullName"]` passed at capture time |
| T-01-12 (PII in fixtures) | accept | No action needed — all data is public MLB stats |
| T-01-13 (torn fixture write) | accept | `path.write_text` used as designed; single-session capture, git diff catches corruption |
| T-01-14 (rate-limit trip) | mitigate | **Done** — 38 sequential calls over ~16 seconds elapsed; well under the ~20 req/s threshold flagged in RESEARCH.md A4 |

## Self-Check: PASSED

Files verified:
- FOUND: scripts/smoke.py
- FOUND: scripts/record_fixtures.py
- FOUND: tests/fixtures/README.md
- FOUND: tests/fixtures/teams.json (30 teams)
- FOUND: tests/fixtures/roster_147.json (Judge present)
- FOUND: tests/fixtures/gamelog_592450_2026.json
- FOUND: 30 venue_*.json files
- FOUND: 5 feed_*.json files
- FOUND: data/venues_cache.json (runtime, gitignored)

Commits verified:
- FOUND: d3da361 (Task 1 — feat(01-03): add scripts/smoke.py — Streamlit page exercising all 5 wrappers)
- FOUND: eda6219 (Task 2 scripts — feat(01-03): add fixture recorder script + README)
- FOUND: 7223c4c (Task 2 data — chore(01-03): capture Phase 1 fixtures from live statsapi.mlb.com)
