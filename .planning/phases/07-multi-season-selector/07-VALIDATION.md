---
phase: 7
slug: multi-season-selector
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `python -m pytest tests/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | SEASON-01 | unit | `pytest tests/test_config_season.py -k season` | W0 (TDD task creates it) | pending |
| 7-01-02 | 01 | 1 | SEASON-01 | unit | `pytest tests/controller/test_callbacks.py -k season` | Partial (file exists, test added in task) | pending |
| 7-01-02 | 01 | 1 | SEASON-02 | unit | `pytest tests/controller/test_callbacks.py -k cascade` | Partial (file exists, test added in task) | pending |
| 7-02-00 | 02 | 1 | SEASON-03 | integration | `python scripts/test_historical_roster.py` | W0 (Task 0 creates it) | pending |
| 7-02-01 | 02 | 1 | SEASON-03 | unit | `pytest tests/services/test_team_hitting_stats.py -k roster` | Partial (file exists, test added in task) | pending |
| 7-02-01 | 02 | 1 | SEASON-04 | unit | `pytest tests/services/test_mlb_api_season.py -k ttl` | W0 (TDD task creates it) | pending |
| 7-02-01 | 02 | 1 | SEASON-05 | unit | `pytest tests/services/test_mlb_api_season.py -k max_entries` | W0 (TDD task creates it) | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config_season.py` — covers SEASON-01: `AVAILABLE_SEASONS` length, current year at index 0, `CURRENT_SEASON` matches `AVAILABLE_SEASONS[0]` (created by 07-01 Task 1 TDD red phase)
- [ ] `tests/services/test_mlb_api_season.py` — covers SEASON-04 and SEASON-05: TTL dispatcher routing, `max_entries` introspection (created by 07-02 Task 1 TDD red phase)
- [ ] `tests/controller/test_callbacks.py` — extend with `test_on_season_change_nulls_all_three_children` (created by 07-01 Task 2)
- [ ] `tests/services/test_team_hitting_stats.py` — extend with `test_historical_season_uses_full_season_roster_type` (created by 07-02 Task 1)
- [ ] `scripts/test_historical_roster.py` — live API validation of `rosterType=fullSeason&season=2024` response shape (created by 07-02 Task 0; not a pytest test — requires network, used once for D-03 validation)

*Existing test infrastructure (pytest, conftest.py, fixtures) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Season selectbox visible and defaults to current year | SEASON-01 | UI widget rendering | Run `streamlit run src/mlb_park/app.py`, verify selectbox appears above Team |
| Historical roster shows correct players | SEASON-03 | Requires live API | Select NYY 2024, verify Judge appears in roster |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
