from datetime import datetime, timezone, timedelta
import copy
import json

from backend import superbet_quote_evidence as arch

NOW = datetime(2026, 10, 8, 12, 30, tzinfo=timezone.utc)


def _sources():
    observed = (NOW - timedelta(minutes=1)).isoformat()
    scheduled = (NOW + timedelta(hours=2)).isoformat()
    match = {
        "match_id": "m1", "event_id": "12345", "p1": "A", "p2": "B",
        "scheduled_time": scheduled, "direct_match_verified": True,
        "canonical_selections": [
            {"operator_selection_id": "a1", "market": "set1_total", "pick": "over",
             "line": 8.5, "operator_price": 1.75, "operator_price_verified": True,
             "operator_available": True, "operator_selection_status": "active"},
        ],
    }
    direct = {"mode": "SHADOW_SUPERBET_DIRECT_SELECTED_MATCH_FEED", "status": "OK",
              "generated_at": observed, "prices_used": False, "matches": [match]}
    prepriced = {
        "mode": "SHADOW_SUPERBET_EXACT_BUILDER_QUOTE_FEED", "status": "OK",
        "generated_at": observed, "prices_used": False, "synthetic_prices": False,
        "operator": "superbet.pl",
        "matches": [{"match_id": "m1", "event_id": "12345", "quotes": [{
            "operator_selection_id": "combo1", "source_event_id": "12345",
            "operator_verified": True, "freshness_verified": True,
            "odds_timestamp": observed, "combined_odds": 2.55,
            "component_selection_ids": ["a1", "a2"],
        }]}],
    }
    dynamic = {
        "mode": "SHADOW_SUPERBET_DYNAMIC_BUILDER_QUOTE_FEED", "status": "OK",
        "generated_at": observed, "prices_used": False, "synthetic_prices": False,
        "operator": "superbet.pl",
        "matches": [{"match_id": "m1", "event_id": "12345", "composition_id": "c1",
                     "quote": {"operator_combination_selection_id": "sga1",
                               "operator_verified": True, "freshness_verified": True,
                               "odds_timestamp": observed, "combined_odds": 2.4,
                               "component_selection_ids": ["a1", "a2"]}}],
    }
    return direct, prepriced, dynamic


def test_real_prematch_single_and_two_bb_quote_types_are_only_metadata():
    source = _sources()
    frozen = copy.deepcopy(source)
    report = arch.build_snapshot(*source, now=NOW, run_id="777")
    assert report["status"] == "CAPTURED_VERIFIED_PREMATCH_QUOTES"
    assert report["observed_quotes"] == 3
    assert {x["kind"] for x in report["rows"]} == {
        "SINGLE", "BET_BUILDER_PREPRICED", "BET_BUILDER_DYNAMIC"
    }
    assert report["evidence_sha256"]
    assert report["history_scope"] == "THIS_SINGLE_RUN_ONLY_NOT_RETROACTIVE"
    assert report["join_to_frozen_prediction_ledger_verified"] is False
    assert report["economic_roi_evaluated"] is False
    assert report["new_requests"] == 0
    assert report["real_betting_enabled"] is False
    assert source == frozen


def test_stale_or_postmatch_sources_do_not_become_historical_prices():
    direct, prepriced, dynamic = _sources()
    direct["generated_at"] = (NOW - timedelta(days=2)).isoformat()
    prepriced["matches"][0]["quotes"][0]["odds_timestamp"] = (
        NOW + timedelta(hours=3)).isoformat()
    dynamic["matches"][0]["quote"]["odds_timestamp"] = (
        NOW + timedelta(hours=3)).isoformat()
    report = arch.build_snapshot(direct, prepriced, dynamic, now=NOW, run_id="778")
    assert report["status"] == "NO_VERIFIED_PREMATCH_QUOTES"
    assert report["rows"] == []


def test_missing_direct_identity_blocks_all_builder_quotes():
    direct, prepriced, dynamic = _sources()
    direct["matches"][0]["direct_match_verified"] = False
    report = arch.build_snapshot(direct, prepriced, dynamic, now=NOW, run_id="779")
    assert report["observed_quotes"] == 0
    assert report["rejected_reasons"]["PREPRICED_NO_EXACT_DIRECT_MATCH"] == 1
    assert report["rejected_reasons"]["DYNAMIC_NO_EXACT_DIRECT_MATCH"] == 1


def test_conflicting_selection_identity_fails_closed():
    direct, prepriced, dynamic = _sources()
    duplicate = copy.deepcopy(direct["matches"][0]["canonical_selections"][0])
    duplicate["operator_price"] = 9.99
    direct["matches"][0]["canonical_selections"].append(duplicate)
    report = arch.build_snapshot(direct, prepriced, dynamic, now=NOW, run_id="780")
    assert report["observed_quotes"] == 2
    assert report["rejected_reasons"]["AMBIGUOUS_OPERATOR_SELECTION"] == 1
    assert not any(x["kind"] == "SINGLE" for x in report["rows"])


def test_unverified_price_and_missing_quote_timestamp_are_not_zero():
    direct, prepriced, dynamic = _sources()
    direct["matches"][0]["canonical_selections"][0]["operator_price_verified"] = False
    prepriced["matches"][0]["quotes"][0]["odds_timestamp"] = None
    dynamic["matches"][0]["quote"]["combined_odds"] = None
    report = arch.build_snapshot(direct, prepriced, dynamic, now=NOW, run_id="781")
    assert report["status"] == "NO_VERIFIED_PREMATCH_QUOTES"
    assert report["observed_quotes"] == 0
    assert report["rows"] == []
    assert report["economic_roi_evaluated"] is False


def test_report_provenance_is_reproducible_and_inputs_untouched():
    sources = _sources()
    a = arch.build_snapshot(*sources, now=NOW, run_id="782")
    b = arch.build_snapshot(*sources, now=NOW, run_id="782")
    assert a == b
    assert a["source_evidence"]["direct"]["sha256"] == arch._digest(sources[0])
    assert a["evidence_sha256"] == arch._digest({k:v for k,v in a.items() if k != "evidence_sha256"})
    assert json.dumps(a, allow_nan=False)


def test_runtime_workflow_persists_archival_artifact_outside_main():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    wf = (root / ".github/workflows/superbet-market-refresh.yml").read_text(encoding="utf-8")
    assert "python backend/superbet_quote_evidence.py" in wf
    assert "superbet-quote-evidence-" in wf
    assert "actions/upload-artifact@v4" in wf
    assert "if-no-files-found: error" in wf
    assert "github.event_name != 'pull_request'" in wf


def test_ambiguous_direct_fixture_removes_first_seen_single_price():
    direct, prepriced, dynamic = _sources()
    direct["matches"].append(copy.deepcopy(direct["matches"][0]))
    report = arch.build_snapshot(direct, prepriced, dynamic, now=NOW, run_id="783")
    assert report["rows"] == []
    assert report["rejected_reasons"]["DUPLICATE_DIRECT_FIXTURE"] == 1
    assert report["status"] == "NO_VERIFIED_PREMATCH_QUOTES"
