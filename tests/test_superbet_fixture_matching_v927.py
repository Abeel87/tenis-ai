from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend import superbet_fixture_matching as matching
from backend import superbet_market_core as base


ROOT = Path(__file__).resolve().parents[1]


def _match(p1="Alexander Zverev", p2="Jannik Sinner", when="2026-08-29T12:00:00Z"):
    return {"p1": p1, "p2": p2, "scheduled_time": when}


def _fixture(
    p1="Zverev, Alexander",
    p2="Sinner, Jannik",
    when="2026-08-29T12:10:00Z",
    fixture_id="f-1",
):
    return {
        "participant1Name": p1,
        "participant2Name": p2,
        "startTime": when,
        "fixtureId": fixture_id,
    }


def _cached_fixture(
    p1="Zverev, Alexander",
    p2="Sinner, Jannik",
    when="2026-08-29T12:10:00Z",
    fixture_id="f-1",
):
    return {"p1": p1, "p2": p2, "start_time": when, "fixture_id": fixture_id}


def setup_function():
    matching.reset_telemetry()


def test_exact_normalized_pair_keeps_legacy_priority():
    row = _fixture(p1="Zverev, Alexander (1997)", p2="Sinner, Jannik")
    got = matching.best_fixture_for_match(_match(), [row])
    assert got is row
    assert matching.report()["live"]["exact"] == 1


def test_initial_alias_is_accepted_for_both_players_with_time_guard():
    row = _fixture(p1="A. Zverev", p2="J. Sinner")
    got = matching.best_fixture_for_match(_match(), [row])
    assert got is row
    telemetry = matching.report()["live"]
    assert telemetry["relaxed"] == 1
    assert telemetry["unmatched"] == 0


def test_middle_name_omission_is_safe_alias_not_fuzzy_guess():
    row = _fixture(p1="Cerundolo, Juan M.", p2="Thiago Wild")
    match = _match("Juan Manuel Cerundolo", "Thiago Seyboth Wild")
    assert matching.best_fixture_for_match(match, [row]) is row
    assert matching.person_score("Juan Manuel Cerundolo", "Cerundolo, Juan M.") >= matching.MIN_PERSON_SCORE
    assert matching.person_score("Thiago Seyboth Wild", "Thiago Wild") >= matching.MIN_PERSON_SCORE


def test_reversed_participant_order_is_supported():
    row = _fixture(p1="J. Sinner", p2="A. Zverev")
    assert matching.best_fixture_for_match(_match(), [row]) is row


def test_wrong_first_initial_is_rejected_even_when_surname_matches():
    row = _fixture(p1="M. Zverev", p2="J. Sinner")
    assert matching.best_fixture_for_match(_match(), [row]) is None
    assert matching.report()["live"]["unmatched"] == 1


def test_relaxed_alias_outside_existing_four_hour_guard_is_rejected():
    row = _fixture(p1="A. Zverev", p2="J. Sinner", when="2026-08-29T18:30:00Z")
    assert matching.best_fixture_for_match(_match(), [row]) is None
    assert matching.report()["live"]["time_rejected"] == 1


def test_relaxed_alias_requires_app_scheduled_time():
    row = _fixture(p1="A. Zverev", p2="J. Sinner")
    assert matching.best_fixture_for_match(_match(when=None), [row]) is None
    assert matching.report()["live"]["time_rejected"] == 1


def test_near_tied_relaxed_candidates_are_rejected_instead_of_guessed():
    rows = [
        _fixture(p1="A. Zverev", p2="J. Sinner", when="2026-08-29T12:00:00Z", fixture_id="f-a"),
        _fixture(p1="A. Zverev", p2="J. Sinner", when="2026-08-29T12:05:00Z", fixture_id="f-b"),
    ]
    match = _match(when="2026-08-29T12:02:00Z")
    assert matching.best_fixture_for_match(match, rows) is None
    assert matching.report()["live"]["ambiguous_rejected"] == 1


def test_near_tied_exact_candidates_are_rejected_instead_of_fixture_id_tiebreak():
    rows = [
        _fixture(p1="Alexander Zverev", p2="Jannik Sinner", when="2026-08-29T12:00:00Z", fixture_id="exact-a"),
        _fixture(p1="Jannik Sinner", p2="Alexander Zverev", when="2026-08-29T12:05:00Z", fixture_id="exact-b"),
    ]
    match = _match(when="2026-08-29T12:02:00Z")
    assert matching.best_fixture_for_match(match, rows) is None
    telemetry = matching.report()["live"]
    assert telemetry["ambiguous_rejected"] == 1
    assert telemetry["exact"] == 0


def test_cached_index_scans_aliases_when_exact_pair_key_is_missing():
    row = _cached_fixture(p1="A. Zverev", p2="J. Sinner")
    index = {base._pair_key(row["p1"], row["p2"]): [row]}
    got = matching.best_cached_fixture(_match(), index)
    assert got is row
    assert matching.report()["cached"]["relaxed"] == 1


def test_matching_rollout_forces_one_live_refresh_then_delegates():
    calls = []

    def original(previous, now):
        calls.append((previous, now))
        return False

    now = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)
    assert matching.availability_due(original, {}, now) is True
    assert calls == []

    previous = {
        "fixture_matching_v927": {"version": matching.VERSION},
        "operator_rows_in_horizon": 0,
        "operator_rows_in_horizon_with_requested_bookmaker": 0,
        "operator_rows_with_requested_bookmaker": 0,
        "operator_fixture_ids_in_neutral_catalogue": 0,
    }
    assert matching.availability_due(original, previous, now) is False
    assert len(calls) == 1


def test_matching_contract_adds_zero_requests_and_never_uses_prices():
    report = matching.report()
    assert report["version"] == "v9.2.7"
    assert report["additional_external_requests"] == 0
    assert report["prices_used"] is False
    assert report["contract"]["model_math_unchanged"] is True
    assert report["contract"]["ambiguous_relaxed_match_is_rejected"] is True
    assert report["contract"]["ambiguous_exact_match_is_rejected"] is True


def test_superbet_refresh_runs_after_full_build_without_parallel_write():
    workflow = (ROOT / ".github" / "workflows" / "superbet-market-refresh.yml").read_text(encoding="utf-8")
    assert "workflow_run:" in workflow
    assert "workflows: ['Update tennis data and deploy Pages']" in workflow
    assert "types: [completed]" in workflow
    assert "|| 'tennis-data-build'" in workflow
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow


def test_lightweight_superbet_refresh_does_not_retrain_surface_elo_without_db():
    workflow = (ROOT / ".github" / "workflows" / "superbet-market-refresh.yml").read_text(encoding="utf-8")
    assert "python -m py_compile backend/surface_elo_integration_v893.py" in workflow
    assert "python backend/surface_elo_integration_v893.py" not in workflow


def test_availability_due_forces_one_refresh_when_operator_contract_fields_are_missing():
    previous = {
        "fixture_matching_v927": {"version": matching.VERSION},
        "generated_at": "2026-09-04T08:00:00+00:00",
    }
    assert matching.availability_due(lambda _previous, _now: False, previous, None) is True

    previous.update({
        "operator_rows_in_horizon": 0,
        "operator_rows_in_horizon_with_requested_bookmaker": 0,
        "operator_rows_with_requested_bookmaker": 0,
        "operator_fixture_ids_in_neutral_catalogue": 0,
    })
    assert matching.availability_due(lambda _previous, _now: False, previous, None) is False
