from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compact_frontend_data_v853.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("compact_frontend_data_v853_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_raw_symphony_cards_are_built_from_deep_model_report(tmp_path):
    module = _load_module()
    source = tmp_path / "symphony_model_v93.json"
    target = tmp_path / "symphony_match_cards_v90.json"
    source.write_text(json.dumps({
        "version": "v9.3A",
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
                        {"key": "a", "label": "A", "market": "set1_winner", "pick": "Beta", "operator_playable": False},
                        {"key": "b", "label": "B", "market": "match_winner", "pick": "Alpha", "operator_playable": False},
                        {"key": "c", "label": "C", "market": "match_total", "pick": "over", "line": 21.5, "operator_playable": False},
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
    }), encoding="utf-8")

    module.SYMPHONY_REPORT = source
    module.SYMPHONY_MATCH_CARDS = target
    result = module.build_symphony_match_cards()
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert result["status"] == "ok"
    assert result["layer"] == "MODEL_RAW_DEEP"
    assert result["operator_playable"] is False
    assert result["external_requests"] == 0
    assert payload["source_report"] == "symphony_model_v93.json"
    assert payload["source_mode"] == "MODEL_RAW_ANALYSIS_ONLY"
    assert payload["layer"] == "MODEL_RAW_DEEP"
    assert payload["analysis_only"] is True
    assert payload["operator_playable"] is False
    assert payload["prices_used"] is False
    assert payload["external_requests"] == 0

    comp = payload["matches"][0]["composition"]
    assert comp["story_type"] == "COMEBACK_AFTER_SET1"
    assert comp["scenario_narrative"].startswith("Przegrany 1. set")
    assert comp["exact_path_scope"] == "SET1+SET2+MATCH"
    assert comp["operator_playable"] is False
    assert comp["top_paths"][0]["match_score"] == "2:1"
    assert len(comp["selection"]) == 3


def test_compact_script_no_longer_sources_raw_cards_from_operator_symphony():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "SYMPHONY_REPORT = DATA / 'symphony_model_v93.json'" in source
    assert "SYMPHONY_REPORT = DATA / 'symphony_v90.json'" not in source
    assert "SYMPHONY_CARD_LAYER = 'MODEL_RAW_DEEP'" in source
