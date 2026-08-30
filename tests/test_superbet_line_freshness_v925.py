from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "playable-line-freshness-v925.js"
META = ROOT / "frontend" / "app-meta.js"


def test_actionable_superbet_snapshot_uses_bounded_pipeline_safe_freshness():
    text = JS.read_text(encoding="utf-8")
    match = re.search(r"MAX_OPERATOR_AGE_MS=(\d+)\*60\*1000", text)
    assert match, "freshness TTL constant missing"
    ttl_minutes = int(match.group(1))
    # Hourly operator refresh + current rebuild/deploy takes longer than 12 min,
    # so the UI TTL must survive publication but still remain bounded.
    assert 60 <= ttl_minutes <= 90
    assert "base.active?.(match,now)===true&&sourceFresh(match,now)&&startAligned(match)" in text
    assert "strictCompositionPlayable" in text
    assert "legs.every(leg=>strictIsPlayable(match,leg))" in text


def test_freshness_wrapper_does_not_touch_model_math():
    text = JS.read_text(encoding="utf-8")
    for token in ["final_score =", "probability =", "joint_probability =", "adaptive_prod_score =", "weights ="]:
        assert token not in text
    assert "MODEL/RAW" in text


def test_freshness_gate_loads_before_symphony_save_layer():
    text = META.read_text(encoding="utf-8")
    freshness = text.index("playable-line-freshness-v925.js?v=925")
    save = text.index("symphony-superbet-save-v924.js?v=925")
    # Source declares save first as a callback, but execution chain must call freshness
    # and pass save as its onload callback.
    assert "const freshness=()=>load('playable-line-freshness-v925.js?v=925','playable-line-freshness-v925',save);" in text
    assert "load('playable-ui-coherence-v917.js?v=925','playable-ui-coherence-v917',freshness)" in text
    assert freshness > 0 and save > 0
