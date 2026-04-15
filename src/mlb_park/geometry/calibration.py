"""Joint least-squares calibration of the Gameday coord transform.

Fitted against the 6 Judge 2026 HRs captured in tests/fixtures/feed_*.json.
Reproducible from fixtures via `python -m mlb_park.geometry.calibration`.

Committed constants below are the authoritative v1 values — per D-06/D-08.
Scipy-free by design (D-07, CLAUDE.md: keep it boring).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np

# ----- Committed fitted values (regenerated via `python -m mlb_park.geometry.calibration`) -----
# Ground truth: 6 Judge HRs in tests/fixtures/feed_*.json as of 2026-04-14.
# Residuals all < 0.16 ft; seeded at community (125, 199, 2.35) and converged.
CALIB_OX: float = 125.608
CALIB_OY: float = 205.162
CALIB_S:  float = 2.3912
CALIB_RESIDUALS_FT: tuple[float, ...] = (0.04, 0.15, 0.15, 0.04, 0.09, 0.07)  # |fitted - totalDistance| per HR
CALIB_SOURCE_FIXTURES: tuple[int, ...] = (822998, 823241, 823243, 823563, 823568)  # gamePks; 823563 contributes 2 HRs

JUDGE_PERSON_ID = 592450  # duplicated from mlb_park.config to keep geometry I/O-free of config side-effects


def fit_calibration(
    X: Iterable[float],
    Y: Iterable[float],
    D: Iterable[float],
    seed: tuple[float, float, float] = (125.0, 199.0, 2.35),
) -> tuple[float, float, float, list[float]]:
    """Joint least-squares fit of (Ox, Oy, s) minimizing SSR of computed distance vs D.

    Closed-form optimal scale for any fixed origin reduces the problem to a 2-D search
    over (Ox, Oy). Coarse grid then two refinement passes. Deterministic, no scipy.

    Returns (Ox, Oy, s, per_hr_residuals_ft) where residuals are |s*r - D| per input.
    """
    X_arr = np.asarray(list(X), dtype=float)
    Y_arr = np.asarray(list(Y), dtype=float)
    D_arr = np.asarray(list(D), dtype=float)
    if X_arr.shape != Y_arr.shape or X_arr.shape != D_arr.shape or X_arr.size == 0:
        raise ValueError("X, Y, D must be non-empty and same length")

    def _cost(Ox: float, Oy: float) -> tuple[float, float]:
        r = np.sqrt((X_arr - Ox) ** 2 + (Oy - Y_arr) ** 2)
        denom = float(r @ r)
        if denom <= 0:
            return float("inf"), seed[2]
        s = float((r @ D_arr) / denom)
        cost = float(np.sum((s * r - D_arr) ** 2))
        return cost, s

    Ox0, Oy0, _ = seed
    best_cost = float("inf")
    best_Ox, best_Oy, best_s = Ox0, Oy0, seed[2]

    # Coarse grid: ±10 units in each direction, 41 samples per axis.
    for Ox in np.linspace(Ox0 - 10.0, Ox0 + 10.0, 41):
        for Oy in np.linspace(Oy0 - 10.0, Oy0 + 10.0, 41):
            c, s = _cost(float(Ox), float(Oy))
            if c < best_cost:
                best_cost, best_Ox, best_Oy, best_s = c, float(Ox), float(Oy), s

    # Two refinement passes, each shrinking the window by 10x.
    half = 0.5
    for _ in range(2):
        for Ox in np.linspace(best_Ox - half, best_Ox + half, 21):
            for Oy in np.linspace(best_Oy - half, best_Oy + half, 21):
                c, s = _cost(float(Ox), float(Oy))
                if c < best_cost:
                    best_cost, best_Ox, best_Oy, best_s = c, float(Ox), float(Oy), s
        half /= 10.0

    r = np.sqrt((X_arr - best_Ox) ** 2 + (best_Oy - Y_arr) ** 2)
    residuals = list(np.abs(best_s * r - D_arr).tolist())
    return best_Ox, best_Oy, best_s, residuals


def extract_hrs_from_feeds(
    fixtures_dir: Path | str,
    batter_id: int = JUDGE_PERSON_ID,
) -> list[dict]:
    """Parse feed_*.json files in fixtures_dir and return HR records for the given batter.

    This is a fixture / script helper — NOT part of any runtime import path.
    Callers: tests/ and `python -m mlb_park.geometry.calibration`.
    """
    fixtures_dir = Path(fixtures_dir)
    out: list[dict] = []
    for feed_path in sorted(fixtures_dir.glob("feed_*.json")):
        feed = json.loads(feed_path.read_text(encoding="utf-8"))
        game_pk = int(feed_path.stem.split("_")[1])
        all_plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", []) or []
        for play in all_plays:
            if play.get("result", {}).get("eventType") != "home_run":
                continue
            if play.get("matchup", {}).get("batter", {}).get("id") != batter_id:
                continue
            hit_data = None
            for event in reversed(play.get("playEvents", []) or []):
                if isinstance(event.get("hitData"), dict):
                    hit_data = event["hitData"]
                    break
            if hit_data is None:
                continue
            coords = hit_data.get("coordinates", {}) or {}
            if "coordX" not in coords or "coordY" not in coords or "totalDistance" not in hit_data:
                continue
            out.append({
                "gamePk": game_pk,
                "coordX": float(coords["coordX"]),
                "coordY": float(coords["coordY"]),
                "totalDistance": float(hit_data["totalDistance"]),
            })
    return out


def _main() -> None:  # pragma: no cover - CLI utility
    """Re-fit calibration from tests/fixtures/ and print current vs committed constants."""
    repo_root = Path(__file__).resolve().parents[3]
    fixtures = repo_root / "tests" / "fixtures"
    hrs = extract_hrs_from_feeds(fixtures)
    if not hrs:
        raise SystemExit(f"No HRs found under {fixtures}")
    X = [h["coordX"] for h in hrs]
    Y = [h["coordY"] for h in hrs]
    D = [h["totalDistance"] for h in hrs]
    Ox, Oy, s, residuals = fit_calibration(X, Y, D)
    print(f"Fitted:    Ox={Ox:.3f}  Oy={Oy:.3f}  s={s:.4f}")
    print(f"Committed: Ox={CALIB_OX:.3f}  Oy={CALIB_OY:.3f}  s={CALIB_S:.4f}")
    print(f"Residuals (ft): {['%.2f' % r for r in residuals]}")
    print(f"Max residual: {max(residuals):.3f} ft")


if __name__ == "__main__":  # pragma: no cover
    _main()
