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
| 7-01-01 | 01 | 1 | SEASON-07 | unit | `pytest tests/test_config.py -k season` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 1 | SEASON-01 | unit | `pytest tests/test_app.py -k season` | ❌ W0 | ⬜ pending |
| 7-01-03 | 01 | 1 | SEASON-02 | unit | `pytest tests/test_app.py -k cascade` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | SEASON-03 | unit | `pytest tests/test_mlb_api.py -k roster` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | SEASON-04 | unit | `pytest tests/test_mlb_api.py -k ttl` | ❌ W0 | ⬜ pending |
| 7-02-03 | 02 | 1 | SEASON-05 | unit | `pytest tests/test_mlb_api.py -k max_entries` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_season_selector.py` — stubs for SEASON-01, SEASON-02
- [ ] `tests/test_historical_roster.py` — stubs for SEASON-03
- [ ] `tests/test_season_caching.py` — stubs for SEASON-04, SEASON-05

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
