---
phase: 01-foundation-api-layer
plan: 01
subsystem: scaffolding
tags: [packaging, config, gitignore]
requires: []
provides:
  - mlb_park package (editable installable)
  - mlb_park.config constants (BASE URLs, TTLs, HTTP_TIMEOUT, USER_AGENT, VENUES_FILE, VENUES_STALE_DAYS, YANKEES_TEAM_ID, JUDGE_PERSON_ID)
  - pinned dependency set (streamlit, requests, plotly, pandas)
  - .gitignore rules for data/ runtime cache and .streamlit/
affects:
  - All Phase 1 plans 02/03 (import mlb_park.config)
  - All downstream phases (import mlb_park.services.*)
tech-stack:
  added:
    - streamlit>=1.55,<2.0
    - requests>=2.32,<3.0
    - plotly>=6.7,<7.0
    - pandas>=2.2,<3.0
  patterns:
    - src/ layout with PEP 621 pyproject.toml + setuptools.packages.find
    - requirements.txt + pyproject.toml kept in sync (dual declaration)
    - Config module with zero I/O imports (safe at import time)
key-files:
  created:
    - requirements.txt
    - pyproject.toml
    - .gitignore
    - src/mlb_park/__init__.py
    - src/mlb_park/services/__init__.py
    - src/mlb_park/app.py
    - src/mlb_park/config.py
  modified: []
decisions:
  - requirements.txt and pyproject.toml both declare the same 4 pinned deps (ROADMAP criterion #5 tests requirements.txt literally; pyproject.toml needed for editable install in Plan 03)
  - config.py resolves VENUES_FILE via Path(__file__).resolve().parents[2] — two levels up from src/mlb_park/config.py lands at repo root
  - app.py is a runnable placeholder (imports streamlit, renders title + info banner) so `streamlit run src/mlb_park/app.py` works from the start
metrics:
  tasks_completed: 2
  files_created: 7
  files_modified: 0
  completed: 2026-04-14
---

# Phase 01 Plan 01: Project Scaffolding & Config Constants Summary

Installable `mlb_park` package skeleton with pinned deps and a pure-constants config module that every downstream plan imports.

## What Was Built

Two atomic tasks produced a seven-file scaffolding layer:

**Task 1 — Dependency pins + package declaration** (commit `ac0ef51`)
- `requirements.txt`: 4 lines, each with a `>=x.y,<major+1` pin per ROADMAP criterion #5.
- `pyproject.toml`: PEP 621 `[project]` section with `name = "mlb-park"`, `requires-python = ">=3.12"`, `[tool.setuptools.packages.find] where = ["src"]` for src-layout discovery, and a `[project].dependencies` list mirroring `requirements.txt` exactly.
- `.gitignore`: blocks `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `.venv/`/`venv/`, `.streamlit/`, `data/`, `.DS_Store`, `Thumbs.db`.

**Task 2 — Package skeleton + config module** (commit `cddf875`)
- `src/mlb_park/__init__.py` — docstring-only package marker.
- `src/mlb_park/services/__init__.py` — docstring-only subpackage marker.
- `src/mlb_park/app.py` — 4-line Streamlit stub (title + info banner); runnable with `streamlit run src/mlb_park/app.py`.
- `src/mlb_park/config.py` — 12 named constants verbatim from plan interface spec:
  - `BASE_URL_V1 = "https://statsapi.mlb.com/api/v1"`
  - `BASE_URL_V11 = "https://statsapi.mlb.com/api/v1.1"`
  - `HTTP_TIMEOUT = (5, 15)`
  - `USER_AGENT = "mlb-park-explorer/0.1 (+https://github.com/local/hobby)"`
  - `TTL_TEAMS="24h"`, `TTL_ROSTER="6h"`, `TTL_GAMELOG="1h"`, `TTL_VENUE="24h"`, `TTL_FEED="7d"`
  - `VENUES_FILE = _ROOT / "data" / "venues_cache.json"` (resolved via `Path(__file__).resolve().parents[2]`)
  - `VENUES_STALE_DAYS = 30`
  - `YANKEES_TEAM_ID = 147`, `JUDGE_PERSON_ID = 592450`

## File Line Counts

| File | Lines |
|---|---|
| requirements.txt | 4 |
| pyproject.toml | 15 |
| .gitignore | 15 |
| src/mlb_park/__init__.py | 1 |
| src/mlb_park/services/__init__.py | 1 |
| src/mlb_park/app.py | 5 |
| src/mlb_park/config.py | 31 |

## Verification

All plan-specified `<verify>` commands pass:
- Task 1: `requirements.txt`, `pyproject.toml`, `.gitignore` exist; streamlit pin present in both; `[tool.setuptools.packages.find]` with `where = ["src"]`; `data/` in gitignore.
- Task 2: All four package files exist; `TTL_VENUE="24h"`, `TTL_FEED="7d"`, `BASE_URL_V11="https://statsapi.mlb.com/api/v1.1"`, `VENUES_STALE_DAYS=30`, `JUDGE_PERSON_ID=592450` all present; `grep -c 'TTL_' src/mlb_park/config.py` returns 5 matching lines.

**Zero I/O imports confirmed in config.py:** `grep -c 'import requests'` returns 0; `grep -c 'import streamlit'` returns 0. Module is safely importable without network or Streamlit context.

## Deviations from Plan

None — plan executed exactly as written. All 12 constants match the `<interfaces>` spec verbatim; all file contents match the inline templates in each task's `<action>`.

## Threat Model Compliance

| Threat ID | Disposition | Status |
|---|---|---|
| T-01-01 (PII in UA) | mitigate | Done — UA uses `github.com/local/hobby`, no personal email |
| T-01-02 (cached venue JSON in git) | mitigate | Done — `.gitignore` line 12 `data/` |
| T-01-03 (unbounded HTTP timeout) | mitigate | Done — `HTTP_TIMEOUT = (5, 15)` centralized in `config.py` |
| T-01-04 (unpinned deps) | accept | Done — ranged pins with major-version upper bounds |

## Self-Check: PASSED

Files verified:
- FOUND: requirements.txt
- FOUND: pyproject.toml
- FOUND: .gitignore
- FOUND: src/mlb_park/__init__.py
- FOUND: src/mlb_park/services/__init__.py
- FOUND: src/mlb_park/app.py
- FOUND: src/mlb_park/config.py

Commits verified:
- FOUND: ac0ef51 (Task 1 — chore(01-01): pin dependencies and declare mlb-park package)
- FOUND: cddf875 (Task 2 — feat(01-01): scaffold mlb_park package with config constants)
