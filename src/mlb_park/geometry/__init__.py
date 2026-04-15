"""Pure-function geometry layer: calibrated coord transform, Park model, verdict matrix.

No I/O, no network, no streamlit imports. Consumes already-loaded JSON.

Public API (import from this subpackage root):
    from mlb_park.geometry import (
        gameday_to_spray_and_distance, clamp_spray_angle,
        Park, load_parks,
        HitData, VerdictRecord, VerdictMatrix, compute_verdict_matrix,
    )
"""
from mlb_park.geometry.park import Park, load_parks
from mlb_park.geometry.transform import (
    clamp_spray_angle,
    gameday_to_spray_and_distance,
)
from mlb_park.geometry.verdict import (
    HitData,
    VerdictMatrix,
    VerdictRecord,
    compute_verdict_matrix,
)

__all__ = [
    "Park",
    "load_parks",
    "clamp_spray_angle",
    "gameday_to_spray_and_distance",
    "HitData",
    "VerdictMatrix",
    "VerdictRecord",
    "compute_verdict_matrix",
]
