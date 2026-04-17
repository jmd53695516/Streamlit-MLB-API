# Phase 8: Cloud Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 08-cloud-deployment
**Areas discussed:** Streamlit config, Dependency cleanup, Venues cache strategy, Deploy workflow

---

## Streamlit Config

| Option | Description | Selected |
|--------|-------------|----------|
| Wide | Full browser width — better for spray charts | ✓ |
| Centered | Narrow centered column — standard default | |

**User's choice:** Wide layout
**Notes:** Better for spray charts and side-by-side content

---

| Option | Description | Selected |
|--------|-------------|----------|
| Default theme | Standard Streamlit light/dark auto-detect | |
| Baseball-themed | Custom primary/secondary colors | ✓ |
| You decide | Claude picks something clean | |

**User's choice:** Baseball-themed

---

| Option | Description | Selected |
|--------|-------------|----------|
| Classic MLB | Navy #002D72, red #D50032, white background | ✓ |
| Dark ballpark | Dark background with green/cream accents | |
| You decide | Claude picks a clean baseball palette | |

**User's choice:** Classic MLB branding colors
**Notes:** Navy primary, red accent, white background — matches MLB league branding

---

| Option | Description | Selected |
|--------|-------------|----------|
| MLB HR Park Explorer | Short and descriptive | ✓ |
| HR Park Factor Explorer | Matches the project name | |
| You decide | Claude picks | |

**User's choice:** MLB HR Park Explorer

---

## Dependency Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Remove from requirements.txt | Remove pytest, keep in pyproject.toml optional | ✓ |
| Split into two files | requirements.txt + requirements-dev.txt | |
| You decide | Claude picks cleanest approach | |

**User's choice:** Remove pytest from requirements.txt, keep in pyproject.toml as optional dep

---

| Option | Description | Selected |
|--------|-------------|----------|
| Keep pyproject.toml | Already has pytest config, move pytest to optional | ✓ |
| Remove pyproject.toml | Go pure requirements.txt per CLAUDE.md | |

**User's choice:** Keep pyproject.toml

---

## Venues Cache Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| data/venues_cache.json (keep current) | Same path, change .gitignore | ✓ |
| src/mlb_park/data/venues_cache.json | Move inside package | |
| You decide | Claude picks simplest | |

**User's choice:** Keep current path, narrow .gitignore

---

| Option | Description | Selected |
|--------|-------------|----------|
| Run app locally, commit file | Simple and verified | ✓ |
| Add a generation script | More repeatable | |

**User's choice:** Run app locally once, commit the resulting file

---

## Deploy Workflow

| Option | Description | Selected |
|--------|-------------|----------|
| main | Standard deploy branch, merge master first | ✓ |
| master | Deploy from current branch | |

**User's choice:** Deploy from main branch

---

| Option | Description | Selected |
|--------|-------------|----------|
| No secrets needed | Public API, no auth | ✓ |
| Yes, there are secrets | | |

**User's choice:** No secrets needed

---

| Option | Description | Selected |
|--------|-------------|----------|
| Include instructions in plan | Step-by-step Cloud setup guide | ✓ |
| I'll figure it out | Plan only handles code changes | |

**User's choice:** Include step-by-step instructions as non-autonomous task

---

## Claude's Discretion

- Exact .streamlit/config.toml structure and additional server settings
- Whether runtime.txt or packages.txt needed for Cloud
- Git merge strategy for master→main

## Deferred Ideas

None — discussion stayed within phase scope
