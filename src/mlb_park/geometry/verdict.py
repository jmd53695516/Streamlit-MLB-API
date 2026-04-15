"""Per-HR-per-park verdict matrix — the Phase 2 capstone.

`compute_verdict_matrix(hrs, parks)` does all HR × park interpolation in one
vectorized sweep (D-15). Per-record access is supported via `iter_records()`
for Phase 5 hover tooltips; the underlying dense arrays are the canonical form.

Margin convention (D-16): margin_ft > 0 means the HR cleared the fence by that
many feet; margin_ft < 0 means it fell short. `cleared = margin_ft > 0`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence, Union

import numpy as np

from mlb_park.geometry.park import Park
from mlb_park.geometry.transform import gameday_to_spray_and_distance


@dataclass(frozen=True)
class HitData:
    """Minimum shape consumed by the geometry layer (D-17).

    Phase 3 supplies the objects; the geometry layer reads only these fields.
    `identifier` is an opaque pass-through (gamePk, play_uuid, batter_id dict, etc.)
    so Phase 5 can correlate records back to their source plays.
    """
    distance_ft: float
    coord_x: float
    coord_y: float
    identifier: Any = None


@dataclass(frozen=True)
class VerdictRecord:
    """One cell of the verdict matrix — per-(HR, park) record for iteration."""
    hr_index: int
    venue_id: int
    park_name: str
    cleared: bool
    fence_ft: float
    margin_ft: float
    identifier: Any = None


@dataclass(frozen=True)
class VerdictMatrix:
    """Dense (n_hrs, n_parks) verdict arrays + iterator over records.

    Invariants:
      - cleared[i, j] == (margin_ft[i, j] > 0)
      - margin_ft[i, j] == hrs[i].distance_ft - fence_ft[i, j]
      - fence_ft[i, j] == parks[j].fence_distance_at(spray_clamped_deg[i])
      - All float arrays are float64; cleared is bool.
    """
    hrs: tuple[HitData, ...]
    parks: tuple[Park, ...]
    venue_ids: np.ndarray
    spray_raw_deg: np.ndarray
    spray_clamped_deg: np.ndarray
    distance_ft: np.ndarray           # transform-computed (debug only — NOT used for margin)
    fence_ft: np.ndarray              # (n_hrs, n_parks)
    margin_ft: np.ndarray             # (n_hrs, n_parks)
    cleared: np.ndarray               # (n_hrs, n_parks) bool

    def iter_records(self) -> Iterator[VerdictRecord]:
        """Yield one VerdictRecord per (hr, park) cell, row-major."""
        n_hrs, n_parks = self.cleared.shape
        for i in range(n_hrs):
            identifier = self.hrs[i].identifier
            for j in range(n_parks):
                yield VerdictRecord(
                    hr_index=i,
                    venue_id=int(self.venue_ids[j]),
                    park_name=self.parks[j].name,
                    cleared=bool(self.cleared[i, j]),
                    fence_ft=float(self.fence_ft[i, j]),
                    margin_ft=float(self.margin_ft[i, j]),
                    identifier=identifier,
                )

    def parks_cleared(self, hr_index: int) -> int:
        """Count of parks this HR clears (out of n_parks)."""
        return int(self.cleared[hr_index].sum())


def _parks_as_ordered_tuple(
    parks: Union[Mapping[int, Park], Sequence[Park]],
) -> tuple[Park, ...]:
    if isinstance(parks, Mapping):
        return tuple(parks.values())
    return tuple(parks)


def compute_verdict_matrix(
    hrs: Sequence[HitData],
    parks: Union[Mapping[int, Park], Sequence[Park]],
) -> VerdictMatrix:
    """Vectorized verdict over all HRs and all parks.

    Shape: (n_hrs, n_parks). Uses np.interp per-park (already vectorized over HRs)
    — exactly n_parks numpy calls, zero nested Python loops over (hr, park) pairs.

    `parks` may be a Mapping[int, Park] (dict insertion order preserved per
    Python 3.7+) or an ordered Sequence[Park]. Column j of the result matches
    parks[j] in the iteration order of the input.
    """
    parks_tuple = _parks_as_ordered_tuple(parks)
    hrs_tuple = tuple(hrs)
    n_hrs = len(hrs_tuple)
    n_parks = len(parks_tuple)

    venue_ids = np.array([p.venue_id for p in parks_tuple], dtype=int)

    if n_hrs == 0 or n_parks == 0:
        empty_f = np.zeros((n_hrs, n_parks), dtype=float)
        empty_b = np.zeros((n_hrs, n_parks), dtype=bool)
        return VerdictMatrix(
            hrs=hrs_tuple,
            parks=parks_tuple,
            venue_ids=venue_ids,
            spray_raw_deg=np.zeros(n_hrs, dtype=float),
            spray_clamped_deg=np.zeros(n_hrs, dtype=float),
            distance_ft=np.zeros(n_hrs, dtype=float),
            fence_ft=empty_f,
            margin_ft=empty_f.copy(),
            cleared=empty_b,
        )

    # Per-HR transform: raw & clamped spray angles + transform-computed distance.
    raw = np.empty(n_hrs, dtype=float)
    clamped = np.empty(n_hrs, dtype=float)
    xform_dist = np.empty(n_hrs, dtype=float)
    reported = np.empty(n_hrs, dtype=float)
    for i, hr in enumerate(hrs_tuple):
        r, c, d = gameday_to_spray_and_distance(hr.coord_x, hr.coord_y)
        raw[i] = r
        clamped[i] = c
        xform_dist[i] = d
        reported[i] = hr.distance_ft

    # Per-park fence interpolation, vectorized across all HRs at once.
    fence_ft = np.empty((n_hrs, n_parks), dtype=float)
    for j, park in enumerate(parks_tuple):
        fence_ft[:, j] = np.interp(clamped, park.angles_deg, park.fence_ft)

    # Margin uses REPORTED totalDistance (D-15/16): margin > 0 ⇒ cleared.
    margin_ft = reported[:, None] - fence_ft
    cleared = margin_ft > 0

    return VerdictMatrix(
        hrs=hrs_tuple,
        parks=parks_tuple,
        venue_ids=venue_ids,
        spray_raw_deg=raw,
        spray_clamped_deg=clamped,
        distance_ft=xform_dist,
        fence_ft=fence_ft,
        margin_ft=margin_ft,
        cleared=cleared,
    )
