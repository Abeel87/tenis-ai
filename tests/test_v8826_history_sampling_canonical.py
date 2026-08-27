from copy import deepcopy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from history_sampling import unique_signals
from history_tracker import MODEL_VERSION, history_stats


def standard_entry(signals):
    return {
        "match_key": "id:test",
        "model_version": MODEL_VERSION,
        "tour": "ATP",
        "status": "settled",
        "result": {"status": "completed", "sets": [[6, 4], [6, 3]]},
        "signals": signals,
    }


def test_standard_set_11_5_is_reported_as_canonical_10_5_without_mutating_archive():
    entry = standard_entry([
        {"market": "set1_total", "label": "1. set · UNDER 11.5", "pick": "under", "line": 11.5,
         "score": 77, "result": "hit", "source_model": "adaptive"}
    ])
    original = deepcopy(entry)
    rows = list(unique_signals(entry))
    assert rows[0]["line"] == 10.5
    assert rows[0]["label"] == "1. set · UNDER 10.5"
    assert entry == original


def test_standard_set_10_5_and_11_5_are_counted_once():
    entry = standard_entry([
        {"market": "set1_total", "label": "1. set · UNDER 10.5", "pick": "under", "line": 10.5,
         "score": 78, "result": "hit", "source_model": "adaptive"},
        {"market": "set1_total", "label": "1. set · UNDER 11.5", "pick": "under", "line": 11.5,
         "score": 79, "result": "hit", "source_model": "adaptive"},
    ])
    rows = list(unique_signals(entry))
    assert len(rows) == 1
    assert rows[0]["line"] == 10.5


def test_history_stats_no_longer_splits_standard_11_5_label():
    entry = standard_entry([
        {"market": "set1_total", "label": "1. set · UNDER 11.5", "pick": "under", "line": 11.5,
         "score": 77, "result": "hit", "source_model": "adaptive"}
    ])
    stats = history_stats([entry])
    assert "1. set · UNDER 11.5" not in stats["by_market"]
    assert stats["by_market"]["1. set · UNDER 10.5"]["settled"] == 1


def test_nonstandard_or_unfinished_set_keeps_original_line():
    entry = standard_entry([
        {"market": "set1_total", "label": "1. set · UNDER 11.5", "pick": "under", "line": 11.5,
         "score": 77, "result": "hit", "source_model": "adaptive"}
    ])
    entry["result"] = {"status": "completed", "sets": [[7, 4], [6, 3]]}
    rows = list(unique_signals(entry))
    assert rows[0]["line"] == 11.5
    assert rows[0]["label"] == "1. set · UNDER 11.5"
