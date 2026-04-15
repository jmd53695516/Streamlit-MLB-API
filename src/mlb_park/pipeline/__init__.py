"""Phase 3 HR pipeline: player_id -> PipelineResult[HREvent].

Public re-exports only (D-18). Logic lives in events.py and extract.py.
"""
from mlb_park.pipeline.events import HREvent, PipelineError, PipelineResult

__all__ = ["HREvent", "PipelineError", "PipelineResult"]
