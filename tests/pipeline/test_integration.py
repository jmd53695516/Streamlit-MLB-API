"""End-to-end pipeline -> verdict-matrix integration tests (Plan 03-03 capstone).

Composition under test:
    extract_hrs(player_id, season, api=stub)
        -> PipelineResult[HREvent]
        -> [hr_event_to_hit_data(ev) for ev in result.events]
        -> compute_verdict_matrix(hit_data_list, parks)
        -> VerdictMatrix(shape=(n_hrs, 30))

Zero network, zero monkey-patching: the StubAPI (Plan 01) is injected via the
documented `api=` kwarg, the real Judge fixtures (gameLog + 5 game feeds) drive
extraction, and Phase 2's `load_parks` builds the 30-park geometry from
`tests/fixtures/venue_*.json`.
"""
from __future__ import annotations

from mlb_park.geometry.park import load_parks
from mlb_park.geometry.verdict import compute_verdict_matrix
from mlb_park.pipeline import (
    HREvent,
    PipelineResult,
    extract_hrs,
    hr_event_to_hit_data,
)


def test_end_to_end_judge_happy_path(
    make_stub_api, judge_feeds, judge_gamelog, venues,
):
    """Real Judge fixtures: 6 HRs -> 6 HitData -> (6, 30) non-degenerate matrix."""
    # Arrange: stub API wraps the 5 real feeds + real gameLog.
    stub = make_stub_api(game_log=judge_gamelog, feeds=judge_feeds)

    # Act 1: extract HR events.
    result = extract_hrs(592450, 2026, api=stub)

    # Assert 1: PipelineResult with 6 Judge HRs and no errors.
    assert isinstance(result, PipelineResult)
    assert len(result.events) == 6
    assert len(result.errors) == 0
    assert all(isinstance(ev, HREvent) for ev in result.events)

    # Act 2: adapt every event to HitData (all 6 should convert — no drops).
    hit_data_list = [hr_event_to_hit_data(ev) for ev in result.events]
    assert all(hd is not None for hd in hit_data_list)
    assert len(hit_data_list) == 6

    # Assert 2: identifiers round-trip the (game_pk, play_idx) pair.
    for ev, hd in zip(result.events, hit_data_list):
        assert hd.identifier == (ev.game_pk, ev.play_idx)

    # Act 3: Phase 2 verdict matrix over 6 HRs x 30 parks.
    parks = load_parks(venues)
    vm = compute_verdict_matrix(hit_data_list, parks)

    # Assert 3: shape is (6, 30), non-degenerate (some clear, some don't).
    assert vm.cleared.shape == (6, 30)
    assert vm.fence_ft.shape == (6, 30)
    # Non-degenerate: proves real geometry ran (not a constant-output stub).
    assert vm.cleared.any()
    assert (~vm.cleared).any()

    # Assert 4: VerdictMatrix.hrs preserves the adapter's identifiers.
    for i, hd in enumerate(hit_data_list):
        assert vm.hrs[i].identifier == hd.identifier

    # Assert 5: iter_records yields cells whose identifier matches the source HR.
    records = list(vm.iter_records())
    assert len(records) == 6 * 30
    for rec in records:
        assert rec.identifier == hit_data_list[rec.hr_index].identifier


def test_end_to_end_with_feed_failure_still_produces_matrix(
    make_stub_api, judge_feeds, judge_gamelog, venues,
):
    """One bad feed (MLBAPIError) -> remaining HRs flow through to a (5, 30) matrix."""
    # Drop one feed (gamePk=823243 carries exactly 1 Judge HR).
    bad_pk = 823243
    feeds = {pk: f for pk, f in judge_feeds.items() if pk != bad_pk}

    StubMLBAPIError = type("StubMLBAPIError", (RuntimeError,), {})
    stub = make_stub_api(
        game_log=judge_gamelog,
        feeds=feeds,
        feed_errors={bad_pk: StubMLBAPIError("503 upstream")},
    )
    # Pitfall 6: extract_hrs catches `api.MLBAPIError`. Override the stub's
    # class attribute so it matches the exception type we just registered.
    stub.MLBAPIError = StubMLBAPIError

    result = extract_hrs(592450, 2026, api=stub)

    # 6 Judge HRs total; dropping the 1 HR in gamePk=823243 yields 5 events,
    # plus 1 PipelineError captured for the bad feed.
    assert len(result.events) == 5
    assert len(result.errors) == 1
    assert result.errors[0].game_pk == bad_pk
    assert result.errors[0].endpoint == "game_feed"

    hit_data_list = [hr_event_to_hit_data(ev) for ev in result.events]
    assert all(hd is not None for hd in hit_data_list)

    parks = load_parks(venues)
    vm = compute_verdict_matrix(hit_data_list, parks)
    assert vm.cleared.shape == (5, 30)
    # Sanity: no event in the matrix references the dropped game.
    for hd in vm.hrs:
        assert hd.identifier[0] != bad_pk
