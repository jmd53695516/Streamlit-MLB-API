# Phase 1: Foundation & API Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 01-foundation-api-layer
**Areas discussed:** Project layout & entry point, Fixtures strategy, gameType scope

---

## Project layout & entry point

### Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Flat package at root: `mlb_park/` | Clean imports, no pyproject ceremony | |
| `src/` layout: `src/mlb_park/` | Standard Python packaging, requires `pyproject.toml` | ✓ |
| Totally flat (root modules) | Simplest, messiest as files grow | |

**User's choice:** src/mlb_park/ layout.

### Entry point

| Option | Description | Selected |
|--------|-------------|----------|
| `src/mlb_park/app.py` | Runs via `streamlit run src/mlb_park/app.py` | ✓ |
| `Home.py` at root (multi-page convention) | Overkill for a single-page app | |

**User's choice:** src/mlb_park/app.py.

### Fixtures location

| Option | Description | Selected |
|--------|-------------|----------|
| `tests/fixtures/` | Standard test-asset location | ✓ |
| `src/mlb_park/data/fixtures/` | Inside the package | |

**User's choice:** tests/fixtures/.

### Disk cache location

| Option | Description | Selected |
|--------|-------------|----------|
| `data/venues_cache.json` at repo root | Gitignored, simple | ✓ |
| `~/.cache/mlb_park/venues.json` (XDG) | "Correct" for shared systems; overkill | |

**User's choice:** data/venues_cache.json at repo root.

---

## Fixtures strategy

### Calibration HR target

| Option | Description | Selected |
|--------|-------------|----------|
| Aaron Judge HR, Yankee Stadium LCF | High-profile, cleanly measured | ✓ |
| Shohei Ohtani HR | Two-way player has gameLog quirks | |
| Let Claude pick during execution | Any qualifying HR | |

**User's choice:** Aaron Judge HR (season reconciled to 2026 per subsequent answer).

### Fixture count / scope

| Option | Description | Selected |
|--------|-------------|----------|
| 3 games (typical + edge + partial) | Minimal + edge-case coverage | |
| 1 game only | Just calibration | |
| Whole player season (20+ games) | Heavier but complete | ✓ |

**User's choice:** Whole player season (2026 → naturally ~5-15 games in early April).

### Capture method

| Option | Description | Selected |
|--------|-------------|----------|
| Scripted live-API capture, committed as-is | `scripts/record_fixtures.py`, raw JSON | ✓ |
| Hand-crafted minimal JSON | Fast but misses real-API surprises | |

**User's choice:** Scripted capture.

### Season year

| Option | Description | Selected |
|--------|-------------|----------|
| 2025 — complete season | Full data available | |
| 2026 — current season | Matches running app | ✓ |

**User's choice:** 2026 current season.

---

## gameType scope

### gameLog filter

| Option | Description | Selected |
|--------|-------------|----------|
| Regular season only (R) | Cleanest "current season HRs" | ✓ |
| Regular + Postseason (R, F, D, L, W) | Include playoff HRs | |
| Everything except Spring (R, F, D, L, W, P, A) | Widest net; includes All-Star | |

**User's choice:** Regular season only (R).

### Same filter for verdict

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — single source of truth | One knob | ✓ |
| No — show all, verdict only regular | Added complexity, no benefit | |

**User's choice:** Yes — single filter drives both list and verdict.

---

## Claude's Discretion

- HTTP timeout / retry policy / User-Agent (reasonable defaults).
- Logging approach for scratch validation script.
- File naming conventions inside `tests/fixtures/`.
- Makefile/justfile (nice-to-have, not required).
- Test framework decision deferred to Phase 2.

## Deferred Ideas

- pytest scaffolding (Phase 2).
- ThreadPoolExecutor for concurrent feed fetching (post-v1).
- Postseason HR inclusion.
- Career / multi-season (out of scope).
