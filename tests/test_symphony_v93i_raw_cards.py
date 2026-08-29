from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compact_frontend_data_v853.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("compact_frontend_data_v853_v93i_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _deep_source():
    return {
        "version": "v9.3H",
        "mode": "MODEL_RAW_ANALYSIS_ONLY",
        "matches": [{
            "id": 77,
            "match_key": "id:77",
            "p1": "Alpha",
            "p2": "Beta",
            "best_of": 3,
            "path_engine": "DEEP_EXACT_SET1_SET2",
            "recommended_leg_count": 3,
            "compositions": {
                "3": {
                    "legs": 3,
                    "story_type": "COMEBACK_AFTER_SET1",
                    "scenario_narrative": "Przegrany 1. set, potem odwrócenie meczu.",
                    "symphony_score": 87.4,
                    "joint_probability": 23.1,
                    "path_coverage": 1.0,
                    "exact_path_scope": "SET1+SET2+MATCH",
                    "selection": [
                        {
                            "key": "a",
                            "label": "A",
                            "market": "set1_winner",
                            "pick": "Beta",
                            "operator_playable": True,
                        },
                        {
                            "key": "b",
                            "label": "B",
                            "market": "match_winner",
                            "pick": "Alpha",
                            "operator_playable": False,
                        },
                        {
                            "key": "c",
                            "label": "C",
                            "market": "match_total",
                            "pick": "over",
                            "line": 21.5,
                        },
                    ],
                    "top_paths": [{
                        "path": "1S 1:1 -> 2:2 -> 3:3 -> 6:7 · 2S 1:1 -> 3:1 -> 4:2 -> 6:3 -> mecz 2:1",
                        "set1": "6:7",
                        "set2": "6:3",
                        "match_score": "2:1",
                        "total_games": 29,
                        "probability_mass": 4.2,
                    }],
                }
            },
        }],
    }


def test_raw_cards_are_built_from_deep_model_report_and_force_non_playable(tmp_path):
    module = _load_module()
    source = tmp_path / "symphony_model_v93.json"
    target = tmp_path / "symphony_match_cards_v90.json"
    source.write_text(json.dumps(_deep_source()), encoding="utf-8")

    module.ROOT = tmp_path
    module.SYMPHONY_REPORT = source
    module.SYMPHONY_MATCH_CARDS = target
    result = module.build_symphony_match_cards()
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert result["status"] == "ok"
    assert result["layer"] == "MODEL_RAW_DEEP"
    assert result["analysis_only"] is True
    assert result["operator_playable"] is False
    assert result["external_requests"] == 0

    assert payload["source_report"] == "symphony_model_v93.json"
    assert payload["source_mode"] == "MODEL_RAW_ANALYSIS_ONLY"
    assert payload["layer"] == "MODEL_RAW_DEEP"
    assert payload["analysis_only"] is True
    assert payload["operator_playable"] is False
    assert payload["prices_used"] is False
    assert payload["external_requests"] == 0

    row = payload["matches"][0]
    comp = row["composition"]
    assert row["operator_playable"] is False
    assert comp["operator_playable"] is False
    assert comp["story_type"] == "COMEBACK_AFTER_SET1"
    assert comp["scenario_narrative"].startswith("Przegrany 1. set")
    assert comp["exact_path_scope"] == "SET1+SET2+MATCH"
    assert len(comp["top_paths"]) == 1
    assert all(leg["operator_playable"] is False for leg in comp["selection"])
    assert all(leg["analysis_only"] is True for leg in comp["selection"])


def test_operator_aware_source_is_rejected_without_overwriting_existing_raw_cards(tmp_path):
    module = _load_module()
    source = tmp_path / "symphony_model_v93.json"
    target = tmp_path / "symphony_match_cards_v90.json"
    source.write_text(json.dumps({
        "version": "v9.1",
        "mode": "ANALYSIS_ONLY",
        "matches": [],
    }), encoding="utf-8")
    target.write_text('{"sentinel":"keep-last-good-raw"}', encoding="utf-8")

    module.ROOT = tmp_path
    module.SYMPHONY_REPORT = source
    module.SYMPHONY_MATCH_CARDS = target
    result = module.build_symphony_match_cards()

    assert result["status"] == "source-rejected"
    assert result["reason"] == "RAW_CARD_SOURCE_MUST_BE_MODEL_RAW"
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "sentinel": "keep-last-good-raw"
    }
