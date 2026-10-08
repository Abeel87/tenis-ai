"""Regression boundaries for research-only autonomous ensemble search."""
import copy
from datetime import datetime, timedelta, timezone

import pytest

from backend import self_evolution_shadow as agent

NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def fixture(days=30, matches_per_day=12):
    rows, settled = [], []
    start = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    for day in range(days):
        scheduled = start + timedelta(days=day)
        for i in range(matches_per_day):
            pid = f"pred_{day}_{i}"
            match = f"id:{day * matches_per_day + i + 1}"
            row = {"prediction_id": pid, "match_key": match, "candidate_key": "match_winner|p1",
                   "scheduled_time": scheduled.isoformat(), "captured_at": (scheduled - timedelta(hours=1)).isoformat(),
                   "score_semantics": "probability_0_1",
                   "model_scores": {"current": {"available": True, "value": .8},
                                    "catboost": {"available": True, "value": .5},
                                    "tabpfn": {"available": True, "value": .5}}}
            rows.append(row)
            settled.append({"prediction_id": pid, "match_key": match, "candidate_key": row["candidate_key"],
                            "scheduled_time": scheduled.isoformat(), "settlement": {"status": "SETTLED",
                            "result": "hit" if i % 2 else "miss", "settled_at": (scheduled + timedelta(hours=3)).isoformat()}})
    ledger = {"schema_version": "prediction-ledger-shadow-v1", "mode": "SHADOW_ONLY", "rows": rows}
    evidence = {"schema_version": "prediction-ledger-settlement-shadow-v1", "mode": "SHADOW_ONLY",
                "source_ledger_sha256": agent._digest(ledger), "rows": settled}
    return ledger, evidence


def test_trains_without_writing_production_or_mutating_inputs():
    ledger, evidence = fixture()
    snapshot = copy.deepcopy((ledger, evidence))
    result = agent.build_report(ledger, evidence, now=NOW)
    assert (ledger, evidence) == snapshot
    assert result["status"] == "SHADOW_EVIDENCE_POSITIVE"
    assert result["candidate"]["validation_delta_vs_current"] < 0
    assert result["candidate"]["holdout_delta_vs_current"] < 0
    assert sum(result["candidate"]["weights"].values()) == pytest.approx(1.0)
    assert all(result[k] is False for k in ("production_influence", "playable_influence", "symphony_influence", "ineed_influence", "auto_promote", "real_betting_enabled"))


def test_data_tampering_fails_closed():
    ledger, evidence = fixture()
    ledger["rows"][0]["model_scores"]["current"]["value"] = .1
    with pytest.raises(ValueError, match="digest mismatch"):
        agent.build_report(ledger, evidence, now=NOW)


def test_duplicate_settlement_identity_fails_closed():
    ledger, evidence = fixture()
    evidence["rows"].append(copy.deepcopy(evidence["rows"][0]))
    with pytest.raises(ValueError, match="duplicate settlement"):
        agent.build_report(ledger, evidence, now=NOW)


def test_incomplete_and_unverifiable_evidence_never_trains():
    ledger, evidence = fixture(days=4)
    evidence["rows"][0]["settlement"] = {"status": "N/D", "result": None}
    result = agent.build_report(ledger, evidence, now=NOW)
    assert result["candidate"] is None
    assert result["status"] == "COLLECTING_VERIFIED_HISTORY"
    assert result["excluded"]["NOT_BINARY_VERIFIED"] == 1


def test_late_settlement_excluded_from_earlier_train_window():
    ledger, evidence = fixture()
    # This result is now available, but would have been unknown at validation start.
    evidence["rows"][0]["settlement"]["settled_at"] = (datetime(2026, 8, 25, tzinfo=timezone.utc)).isoformat()
    result = agent.build_report(ledger, evidence, now=NOW)
    assert result["windows"]["train_rows"] < 18 * 12


def test_all_rows_one_fixture_cannot_fake_independent_match_sample():
    ledger, evidence = fixture()
    for row in ledger["rows"]:
        row["match_key"] = "id:1"
    for row in evidence["rows"]:
        row["match_key"] = "id:1"
    evidence["source_ledger_sha256"] = agent._digest(ledger)
    result = agent.build_report(ledger, evidence, now=NOW)
    assert result["candidate"] is None
    assert result["reason"] == "INSUFFICIENT_INDEPENDENT_MATCHES"


def test_brier_is_fixture_balanced_not_candidate_count_weighted():
    samples = (
        [{"match_key": "id:1", "p": (1.0, 0.0, 0.0), "y": 0} for _ in range(100)]
        + [{"match_key": "id:2", "p": (0.0, 0.0, 0.0), "y": 0}]
    )
    assert agent._metric(samples, (1.0, 0.0, 0.0)) == 0.5


def test_nightly_workflow_generates_settlement_after_restore():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/self-evolution-shadow.yml").read_text(encoding="utf-8")
    restore = workflow.index("python scripts/history_publication_chunks.py restore")
    settle = workflow.index("python backend/prediction_ledger_settlement_shadow.py")
    research = workflow.index("python backend/self_evolution_shadow.py")
    assert restore < settle < research



def test_market_specialist_has_independent_training_and_no_profit_claim():
    ledger, evidence = fixture()
    for row in ledger["rows"]:
        row["market"] = "set1_total"
    evidence["source_ledger_sha256"] = agent._digest(ledger)
    report = agent.build_report(ledger, evidence, now=NOW)
    assert report["status"] == "SHADOW_EVIDENCE_POSITIVE"
    research = report["market_research"]
    assert research["status"] == "EXPLORATORY_SHADOW_ONLY"
    assert research["holdout_used_for_selection"] is False
    assert research["auto_promote"] is False
    assert len(research["studies"]) == 1
    specialist = research["studies"][0]
    assert specialist["market"] == "set1_total"
    assert specialist["status"] == "EVALUATED_SHADOW_ONLY"
    assert specialist["windows"]["train"]["independent_matches"] == 18 * 12
    assert specialist["candidate"]["validation_better_than_current"] is True
    assert report["quote_provenance"]["economic_learning_authorized"] is False
    assert report["quote_provenance"]["eligible_roi_observations"] is None


def test_market_specialist_never_selects_on_holdout():
    ledger, evidence = fixture()
    for row in ledger["rows"]:
        row["market"] = "match_winner"
    evidence["source_ledger_sha256"] = agent._digest(ledger)
    first = agent.build_report(ledger, evidence, now=NOW)
    for row in evidence["rows"]:
        if row["scheduled_time"] >= "2026-08-25":
            row["settlement"]["result"] = (
                "hit" if row["settlement"]["result"] == "miss" else "miss"
            )
    second = agent.build_report(ledger, evidence, now=NOW)
    one = first["market_research"]["studies"][0]["candidate"]
    two = second["market_research"]["studies"][0]["candidate"]
    assert one["weights"] == two["weights"]
    assert one["scores"]["holdout"] != two["scores"]["holdout"]


def test_specialists_fail_closed_on_missing_or_unsupported_market_labels():
    ledger, evidence = fixture()
    for row in ledger["rows"]:
        row["market"] = "../fictional-market"
    evidence["source_ledger_sha256"] = agent._digest(ledger)
    report = agent.build_report(ledger, evidence, now=NOW)
    assert report["market_research"]["status"] == "NO_VERIFIED_MARKET_LABELS"
    assert report["market_research"]["studies"] == []
    assert report["candidate"] is not None  # Global research is still independent.


def test_specialists_minimum_is_independent_matches_not_candidate_rows():
    ledger, evidence = fixture()
    for row in ledger["rows"]:
        row["market"] = "set1_total" if row["match_key"] in {"id:1", "id:2"} else "match_winner"
    evidence["source_ledger_sha256"] = agent._digest(ledger)
    result = agent.build_report(ledger, evidence, now=NOW)
    by_market = {s["market"]: s for s in result["market_research"]["studies"]}
    assert by_market["match_winner"]["status"] == "EVALUATED_SHADOW_ONLY"
    # A rare market with too little eligible evidence never gets a fabricated champion.
    sparse = agent._market_research(
        [{"match_key": "id:1", "market": "set1_total", "p": (.5, .5, .5), "y": 1}],
        [{"match_key": "id:2", "market": "set1_total", "p": (.5, .5, .5), "y": 1}],
        [{"match_key": "id:3", "market": "set1_total", "p": (.5, .5, .5), "y": 1}],
    )["studies"][0]
    assert sparse["candidate"] is None
    assert sparse["status"] == "INSUFFICIENT_EVIDENCE"
