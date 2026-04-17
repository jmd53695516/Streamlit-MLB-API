---
phase: 8
slug: cloud-deployment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | DEPLOY-03 | — | N/A | integration | `python -m pytest tests/ -x -q -k "not test_venue"` | ✅ | ⬜ pending |
| 08-01-02 | 01 | 1 | DEPLOY-04 | — | N/A | file-check | `test -f .streamlit/config.toml` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | DEPLOY-02 | — | N/A | file-check | `test -f data/venues_cache.json && python -c "import json; json.load(open('data/venues_cache.json'))"` | ✅ | ⬜ pending |
| 08-02-02 | 02 | 2 | DEPLOY-01 | — | N/A | manual | See manual verifications | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing infrastructure covers all phase requirements. No new test framework or stubs needed.
- Existing `tests/` directory has pytest configured via `pyproject.toml`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| App loads in browser via shared URL | DEPLOY-01 | Requires Streamlit Community Cloud deployment | 1. Open the shared URL in an incognito browser window 2. Verify all selectors load and spray chart renders 3. Verify no error banners appear |
| Cold-start venue data loads immediately | DEPLOY-02 | Requires fresh Cloud deployment with no cache | 1. Deploy to Cloud 2. Open URL immediately 3. Verify venue selector populates without delay |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
