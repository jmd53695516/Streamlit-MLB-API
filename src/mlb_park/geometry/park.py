"""Park model + fence interpolation.

Frozen dataclass with angle-space piecewise-linear interpolation via numpy.interp.
D-10: 7-point curve when fieldInfo exposes BOTH `left` and `right` gap distances
(the 5 venues that expose only `left` fall back to the 5-point curve — v1
simplification; asymmetric 6-point adds complexity for minimal verdict gain).
D-11: standard points at ±45° (LF/RF line), ±22.5° (LCF/RCF), 0° (CF).
      Gap points at ±30° (RESEARCH.md §Fence Interpolation, empirically verified).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

FENCE_ANGLES_5PT: tuple[float, ...] = (-45.0, -22.5, 0.0, +22.5, +45.0)
GAP_ANGLE_DEG: float = 30.0
FENCE_ANGLES_7PT: tuple[float, ...] = (
    -45.0, -GAP_ANGLE_DEG, -22.5, 0.0, +22.5, +GAP_ANGLE_DEG, +45.0,
)

# fieldInfo keys in the 5-point canonical order.
_FIVE_POINT_KEYS: tuple[str, ...] = (
    "leftLine", "leftCenter", "center", "rightCenter", "rightLine",
)


@dataclass(frozen=True)
class Park:
    """A stadium's fence curve in angle-space. Immutable; built once via from_field_info."""

    venue_id: int
    name: str
    angles_deg: np.ndarray   # shape (5,) or (7,); strictly increasing; dtype float64
    fence_ft:   np.ndarray   # shape matches angles_deg; dtype float64

    @classmethod
    def from_field_info(cls, field_info: dict[str, Any], venue_id: int, name: str) -> "Park":
        """Build a Park from a venue's fieldInfo dict.

        Raises KeyError if any of the 5 canonical distance keys is missing.
        Uses the 7-point curve iff BOTH `left` AND `right` are present; otherwise 5-point
        (D-10 v1 simplification: asymmetric 6-point adds complexity for minimal gain).
        """
        missing = [k for k in _FIVE_POINT_KEYS if k not in field_info]
        if missing:
            raise KeyError(f"venue {venue_id} ({name}) missing fieldInfo keys: {missing}")

        five = tuple(float(field_info[k]) for k in _FIVE_POINT_KEYS)
        has_left = "left" in field_info
        has_right = "right" in field_info

        if has_left and has_right:
            left = float(field_info["left"])
            right = float(field_info["right"])
            angles = np.array(FENCE_ANGLES_7PT, dtype=float)
            fences = np.array(
                (five[0], left, five[1], five[2], five[3], right, five[4]),
                dtype=float,
            )
        else:
            angles = np.array(FENCE_ANGLES_5PT, dtype=float)
            fences = np.array(five, dtype=float)

        # Sanity — monotonic increasing angles (guarantees np.interp correctness).
        if not np.all(np.diff(angles) > 0):
            raise ValueError(f"non-monotonic fence angles for venue {venue_id}: {angles}")

        return cls(venue_id=int(venue_id), name=str(name), angles_deg=angles, fence_ft=fences)

    def fence_distance_at(self, angle_deg):
        """Interpolate fence distance at the given spray angle (scalar or ndarray).

        Clamps input to [-45°, +45°] via numpy.interp's native boundary behavior
        (returns angles_deg[0] / angles_deg[-1] for out-of-range inputs — matches D-14).
        """
        return np.interp(angle_deg, self.angles_deg, self.fence_ft)


def load_parks(venues: dict[int, dict]) -> dict[int, "Park"]:
    """Build a {venue_id: Park} mapping from an already-loaded venues dict (no I/O).

    Input shape: the dict produced by mlb_park.services.mlb_api.load_all_parks —
    each value must have top-level `id`, `name`, and `fieldInfo`.
    """
    parks: dict[int, Park] = {}
    for vid, venue in venues.items():
        field_info = venue.get("fieldInfo") or {}
        parks[int(vid)] = Park.from_field_info(
            field_info,
            venue_id=int(venue.get("id", vid)),
            name=str(venue.get("name", f"venue_{vid}")),
        )
    return parks
