from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "backend" / "symphony_operator_rebuild_v926.py"
WORKFLOW = ROOT / ".github" / "workflows" / "superbet-market-refresh.yml"


def test_rebuild_uses_operator_aware_engine_not_old_filter_only_reproject():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "engine.build_report(legs=legs)" in text
    assert '"FULL_CURRENT_OPERATOR_CATALOGUE_REBUILD"' in text
    assert '"full_scenario_search_rerun": True' in text
    assert '"deep_model_raw_rerun": False' in text
    assert '"prices_used": False' in text


def test_hourly_refresh_rebuilds_symphony_after_current_operator_lines_are_injected():
    text = WORKFLOW.read_text(encoding="utf-8")
    inject = text.index("python backend/superbet_playable_v912.py project")
    rebuild = text.index("python backend/symphony_operator_rebuild_v926.py")
    compact = text.index("python scripts/compact_frontend_data_v853.py")
    assert inject < rebuild < compact
    assert "symphony.get('operator_reprojection_version') == 'v9.2.6'" in text
    assert "repro.get('full_scenario_search_rerun') is True" in text


def test_rebuild_keeps_model_math_and_deep_raw_out_of_lightweight_refresh():
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = [
        "_run_deep_bounded(",
        "final_score =",
        "adaptive_prod_score =",
        "prices_used = True",
    ]
    for token in forbidden:
        assert token not in text
