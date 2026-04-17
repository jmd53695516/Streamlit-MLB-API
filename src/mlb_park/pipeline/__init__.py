"""Phase 3 HR pipeline: player_id -> PipelineResult[HREvent].

Public API (import from here, not from submodules):
  - extract_hrs(player_id, season=None, *, api=...) -> PipelineResult
  - hr_event_to_hit_data(ev: HREvent) -> HitData | None  (D-06 adapter)
  - HREvent, PipelineResult, PipelineError  (D-05, D-13 dataclasses)
  - load_all_parks()  (re-export of services.mlb_api.load_all_parks for DATA-03)

Convenience re-exports (for Phase 4 single-import-origin consumers):
  - HitData, compute_verdict_matrix  (Phase 2 geometry layer entry points)
  - MLBAPIError                       (Phase 1 service-layer exception type)
  - CURRENT_SEASON                    (Phase 3 season default, D-16)
"""
from mlb_park.config import AVAILABLE_SEASONS, CURRENT_SEASON
from mlb_park.geometry.park import load_parks
from mlb_park.geometry.verdict import HitData, compute_verdict_matrix
from mlb_park.pipeline.events import HREvent, PipelineError, PipelineResult
from mlb_park.pipeline.extract import extract_hrs, hr_event_to_hit_data
from mlb_park.services.mlb_api import MLBAPIError, load_all_parks

__all__ = [
    # Plan 03-03 required surface (D-06 + DATA-03)
    "extract_hrs",
    "hr_event_to_hit_data",
    "HREvent",
    "PipelineError",
    "PipelineResult",
    "load_all_parks",
    # Convenience re-exports for Phase 4 controller (D-02 single import origin)
    "HitData",
    "compute_verdict_matrix",
    "load_parks",
    "MLBAPIError",
    "CURRENT_SEASON",
    "AVAILABLE_SEASONS",
]
