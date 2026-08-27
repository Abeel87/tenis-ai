import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calibration_guard_v78d import build_calibration_report, add_calibration_to_matches
from history_tracker import history_stats, MODEL_VERSION


def signal(result, score=82, line=8.5):
    return {"market":"set1_total","label":"1. set · OVER 8.5","pick":"over","line":line,"score":score,"result":result}


def entry(version, results, tour="ATP"):
    return [{"model_version":version,"tour":tour,"signals":[signal(x)],"status":"settled","match_key":f"{version}-{i}-{tour}"} for i,x in enumerate(results)]


def test_current_version_is_not_mixed_with_legacy():
    assert MODEL_VERSION == "v7.8D-calibration-guard"
    rows = [
        *entry(MODEL_VERSION, ["hit"] * 8 + ["miss"] * 4),
        *entry("v7.8A-adaptive-hygiene", ["hit"] * 40 + ["miss"] * 10),
    ]
    stats = history_stats(rows)
    assert stats["overall"]["settled"] == 12
    assert stats["overall"]["accuracy"] == 66.7
    assert stats["legacy_overall"]["settled"] == 50
    assert stats["legacy_overall"]["accuracy"] == 80.0
    assert stats["all_versions_overall"]["settled"] == 62


def test_small_current_sample_is_nd_but_legacy_is_reference():
    rows = [
        *entry(MODEL_VERSION, ["hit"] * 4 + ["miss"] * 2),
        *entry("v7.8A-adaptive-hygiene", ["hit"] * 30 + ["miss"] * 10),
    ]
    report = build_calibration_report(rows, MODEL_VERSION)
    key = "set1_total|8.5|over"
    current = report["current"]["by_key"][key]
    legacy = report["legacy_reference"]["by_key"][key]
    assert current["settled"] == 6
    assert current["usable"] is False
    assert current["display_accuracy"] is None
    assert current["evidence"] == "N/D"
    assert legacy["settled"] == 40
    assert legacy["accuracy"] == 75.0


def test_minimum_sample_becomes_usable():
    rows = [*entry(MODEL_VERSION, ["hit"] * 7 + ["miss"] * 3)]
    report = build_calibration_report(rows, MODEL_VERSION)
    row = report["current"]["by_key"]["set1_total|8.5|over"]
    assert row["settled"] == 10
    assert row["usable"] is True
    assert row["display_accuracy"] == 70.0


def test_matches_receive_calibration_without_changing_model_score():
    rows = [*entry(MODEL_VERSION, ["hit"] * 7 + ["miss"] * 3)]
    report = build_calibration_report(rows, MODEL_VERSION)
    match = {"p1":"A","p2":"B","over_under":{"8.5":{"over":82.0,"under":18.0}},"match_win":{"A":65.0,"B":35.0}}
    out = add_calibration_to_matches([match], report)[0]
    cal = out["calibration_v78d"]
    assert cal["status"] == "READY"
    assert cal["signals"][0]["score"] == 82.0
    assert cal["signals"][0]["current"]["display_accuracy"] == 70.0
    assert match["over_under"]["8.5"]["over"] == 82.0


def test_equivalent_first_set_lines_are_not_two_independent_samples():
    from copy import deepcopy
    from history_sampling import unique_signals
    match = {"match_key":"one", "model_version":MODEL_VERSION,
             "result":{"status":"completed","sets":[[7,5],[6,4]]},
             "signals":[signal('hit',line=11.5), signal('hit',line=10.5)]}
    before = deepcopy(match)
    assert len(list(unique_signals(match))) == 1
    stats = history_stats([match])
    assert stats['overall']['settled'] == 1
    assert stats['raw_settled_signals'] == 2
    assert build_calibration_report([match], MODEL_VERSION)['current']['overall']['settled'] == 1
    assert match == before
    match['result']['sets'][0] = [6,5]  # unfinished/nonstandard: no equivalence assumption
    assert len(list(unique_signals(match))) == 2
