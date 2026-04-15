"""Constants: base URLs, TTLs, HTTP settings, disk-cache locations, known IDs.

Source values: research/STACK.md TTL guide + ROADMAP criterion #2 +
phase RESEARCH.md §Endpoint Contracts (verified live 2026-04-14).
"""
from pathlib import Path

BASE_URL_V1  = "https://statsapi.mlb.com/api/v1"
BASE_URL_V11 = "https://statsapi.mlb.com/api/v1.1"

HTTP_TIMEOUT = (5, 15)   # (connect, read) seconds — per PITFALLS.md §7
USER_AGENT   = "mlb-park-explorer/0.1 (+https://github.com/local/hobby)"

# TTLs — strings per st.cache_data native format. Values per ROADMAP criterion #2:
#   venues 24h in-memory (+ 30d disk), teams 24h, roster 6h, gameLog 1h,
#   completed feeds 7d.
TTL_TEAMS    = "24h"
TTL_ROSTER   = "6h"
TTL_GAMELOG  = "1h"
TTL_VENUE    = "24h"
TTL_FEED     = "7d"

# Disk cache — D-04: runtime disk cache at repo-root data/, gitignored.
# Path resolves from src/mlb_park/config.py up two levels to repo root.
_ROOT = Path(__file__).resolve().parents[2]
VENUES_FILE       = _ROOT / "data" / "venues_cache.json"
VENUES_STALE_DAYS = 30

# Known IDs (verified live 2026-04-14 via Yankees roster lookup)
YANKEES_TEAM_ID = 147
JUDGE_PERSON_ID = 592450

# Current season — Phase 3 entry point default (D-16).
CURRENT_SEASON = 2026
