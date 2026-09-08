import gzip
import json

import pandas as pd

from backend.player_dna_service_split_source_readiness import (
    MODE,
    audit_history,
    audit_identity_namespace,
)


def _row(**overrides):
    base = {
        "tourney_date": 20260901,
        "winner_id": 101,
        "loser_id": 202,
        "winner_name": "Alpha",
        "loser_name": "Beta",
        "w_svpt": 60,
        "l_svpt": 55,
        "w_1stIn": 38,
        "l_1stIn": 34,
        "w_1stWon": 27,
        "l_1stWon": 21,
        "w_2ndWon": 12,
        "l_2ndWon": 10,
        "w_ace": 7,
        "l_ace": 4,
        "w_df": 3,
        "l_df": 5,
        "w_SvGms": 10,
        "l_SvGms": 10,
    }
    base.update(overrides)
    return base


def test_service_split_audit_recognizes_stable_id_first_and_second_serve_source():
    report = audit_history(pd.DataFrame([_row()]))

    assert report["mode"] == MODE
    assert report["rows"] == 1
    assert report["identity_time_coverage"]["canonical_identity_time_rows"] == 1

    first = report["derived_matchup_source_readiness"]["first_serve_vs_first_return"]
    second = report["derived_matchup_source_readiness"]["second_serve_vs_second_return"]
    assert first["canonical_match_rows"] == 1
    assert first["source_ready"] is True
    assert first["return_split_derivable_from_opponent_serve_counts"] is True
    assert second["canonical_match_rows"] == 1
    assert second["source_ready"] is True
    assert second["return_split_derivable_from_opponent_serve_counts"] is True


def test_service_split_audit_requires_stable_provider_ids_and_valid_date():
    raw = pd.DataFrame([
        _row(winner_id=None),
        _row(tourney_date="bad-date", winner_id=303, loser_id=404),
    ])

    report = audit_history(raw)

    assert report["rows"] == 2
    assert report["identity_time_coverage"]["canonical_identity_time_rows"] == 0
    assert (
        report["derived_matchup_source_readiness"]["first_serve_vs_first_return"][
            "canonical_match_rows"
        ]
        == 0
    )


def test_service_split_audit_rejects_invalid_split_denominators():
    # first serve won exceeds first serves in; second serve won exceeds
    # total second-serve attempts. The source row exists but is not safe to derive.
    report = audit_history(
        pd.DataFrame([
            _row(w_1stWon=50, w_2ndWon=30),
        ])
    )

    paired = report["paired_metric_coverage"]
    assert paired["first_serve_points_won_rate_ready"]["canonical_match_rows"] == 0
    assert paired["second_serve_points_won_rate_ready"]["canonical_match_rows"] == 0


def test_service_split_audit_keeps_contact_and_return_pressure_unproven():
    report = audit_history(pd.DataFrame([_row()]))

    readiness = report["derived_matchup_source_readiness"]
    assert readiness["ace_tendency"]["source_ready"] is True
    assert readiness["double_fault_tendency"]["source_ready"] is True
    assert readiness["ace_vs_contact_return"]["source_ready"] is False
    assert readiness["double_fault_vs_return_pressure"]["source_ready"] is False

    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["profile_build_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False

    contract = report["contract"]
    assert contract["source_readiness_only"] is True
    assert contract["stable_provider_ids_required"] is True
    assert contract["day_precision_same_day_must_be_excluded"] is True
    assert contract["no_name_or_fuzzy_identity_for_canonical_profiles"] is True
    assert contract["no_profile_values_published"] is True
    assert contract["no_model_fit"] is True
    assert contract["no_threshold_tuning"] is True
    assert contract["coverage_is_not_predictive_signal"] is True


def test_empty_service_split_audit_stays_audit_only():
    report = audit_history(pd.DataFrame())

    assert report["mode"] == MODE
    assert report["rows"] == 0
    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["profile_build_enabled"] is False
    assert report["training_join_enabled"] is False



def test_cross_source_id_namespace_uses_names_only_as_diagnostic_evidence(tmp_path):
    payload = {
        "match": {
            "players": {
                "p1": {"id": 101, "name": "Alpha"},
                "p2": {"id": 202, "name": "Beta"},
            }
        }
    }
    with gzip.open(tmp_path / "m1.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)

    report = audit_identity_namespace(pd.DataFrame([_row()]), tmp_path)

    assert report["historical_unique_stable_ids"] == 2
    assert report["pbp_unique_stable_ids"] == 2
    assert report["shared_numeric_ids"] == 2
    assert report["shared_ids_with_exact_normalized_name_agreement"] == 2
    assert report["shared_ids_with_name_mismatch"] == 0
    assert report["diagnostic_name_matching_only"] is True
    assert report["name_matching_used_for_join"] is False
    assert report["fuzzy_matching_used"] is False
    assert report["direct_id_join_authorized"] is False
    # Tiny synthetic sample must not satisfy the real compatibility gate.
    assert report["id_namespace_evidence_strong"] is False


def test_cross_source_id_namespace_detects_same_numeric_id_name_conflict(tmp_path):
    payload = {
        "match": {
            "players": {
                "p1": {"id": 101, "name": "Different Person"},
                "p2": {"id": 999, "name": "Other"},
            }
        }
    }
    with gzip.open(tmp_path / "m1.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)

    report = audit_identity_namespace(pd.DataFrame([_row()]), tmp_path)

    assert report["shared_numeric_ids"] == 1
    assert report["shared_ids_with_exact_normalized_name_agreement"] == 0
    assert report["shared_ids_with_name_mismatch"] == 1
    assert report["exact_normalized_name_agreement_rate"] == 0.0
    assert report["id_namespace_evidence_strong"] is False


def test_master_plan_high_ace_rate_vs_weak_returner_cannot_fake_contact_adjustment_without_source():
    raw = pd.DataFrame([
        _row(
            w_ace=18,
            l_ace=1,
            w_svpt=64,
            l_svpt=58,
        )
    ])
    report = audit_history(raw)
    readiness = report["derived_matchup_source_readiness"]

    # Raw ace tendency is measurable, but "weak returner/contact" adjustment is
    # not established by this source. The system must fail closed rather than
    # treating a high ace count as opponent-adjusted evidence.
    assert readiness["ace_tendency"]["source_ready"] is True
    assert readiness["ace_tendency"]["canonical_match_rows"] == 1
    assert readiness["ace_vs_contact_return"]["source_ready"] is False
    assert "contact" in readiness["ace_vs_contact_return"]["reason"].casefold()

    assert report["runtime_scoring_enabled"] is False
    assert report["profile_build_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
