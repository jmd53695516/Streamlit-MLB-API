---
phase: 3
slug: hr-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already installed from Phase 2) |
| **Config file** | `pyproject.toml` / existing `tests/conftest.py` |
| **Quick run command** | `pytest tests/pipeline/ -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~5 seconds (pipeline tests only); ~15s full suite |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/pipeline/ -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green, no network calls
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

Filled in by planner. Each task below lists the requirement it advances, the synthetic fixture(s) it depends on, and the command that proves it green.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-XX-XX | TBD | 0 | — | test infra | `pytest tests/pipeline/ -q` | ❌ W0 | ⬜ pending |

*Planner fills full matrix during plan creation.*

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/pipeline/__init__.py` — package marker
- [ ] `tests/pipeline/conftest.py` — stub-api factory + synthetic fixture builders
- [ ] `tests/pipeline/fixtures/` — synthetic JSON fixtures covering DATA-05 degradation:
  - `feed_missing_hitdata.json` — play with no `hitData` in any playEvent (has_distance/has_coords/has_launch_stats all False)
  - `feed_itp.json` — play with `result.description` containing "inside-the-park"
  - `feed_partial_hitdata.json` — play with `totalDistance` present but `coordinates` missing
  - `feed_non_batter_hr.json` — feed containing another batter's HR (verify batter filter excludes it)
  - `feed_terminal_lacks_hitdata.json` — terminal `playEvents[-1]` lacks hitData but earlier event carries it (verify D-10 fallback)
  - `feed_count_mismatch.json` — gameLog says 2 HRs but feed only surfaces 1 matching play
- [ ] `tests/pipeline/test_extract_hrs.py` — happy path against committed Judge fixtures
- [ ] `tests/pipeline/test_degradation.py` — DATA-05 flag coverage using synthetic fixtures
- [ ] `tests/pipeline/test_error_handling.py` — PipelineError collection when a feed fetch raises MLBAPIError

*Existing pytest infrastructure from Phase 2 covers the framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live-API smoke: `extract_hrs(592450, 2026)` against real MLB StatsAPI | DATA-01, DATA-02 | Verifying actual network behavior + real feed structure matches fixtures; cannot run in CI | 1. Clear `data/venues_cache.json` and `.streamlit` cache. 2. Run a Python REPL: `from mlb_park.pipeline import extract_hrs; r = extract_hrs(592450, 2026); print(len(r.events), len(r.errors))`. 3. Expect >=6 Judge HRs, 0 errors for completed games. |
| Disk-backed venue cache cold-start reuse | DATA-03 | Timing-dependent across process restarts | 1. Delete `data/venues_cache.json`. 2. Run pipeline → verify file created. 3. Re-run with network disabled (e.g., offline) → verify no failure. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (synthetic fixtures for DATA-05)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter after planner fills task matrix

**Approval:** pending
