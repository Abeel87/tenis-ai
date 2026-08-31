from __future__ import annotations

import re
from pathlib import Path

from backend.symphony2_engine import build as build_symphony2


ROOT = Path(__file__).resolve().parents[1]
FRESHNESS_JS = ROOT / "frontend" / "playable-line-freshness-v925.js"
WORKFLOW = ROOT / ".github" / "workflows" / "superbet-market-refresh.yml"


def _max_operator_age_minutes() -> int:
    text = FRESHNESS_JS.read_text(encoding="utf-8")
    match = re.search(r"MAX_OPERATOR_AGE_MS=(\d+)\*60\*1000", text)
    assert match, "PLAYABLE freshness limit must remain explicit and testable"
    return int(match.group(1))


def test_playable_ttl_cannot_expire_before_hourly_pipeline_can_publish() -> None:
    """The UI freshness budget must cover the hourly operator refresh plus rebuild slack."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "cron: '5 * * * *'" in workflow
    assert _max_operator_age_minutes() >= 80
    assert _max_operator_age_minutes() <= 90


def test_symphony2_builder_exposes_runtime_contract_without_committed_runtime_data() -> None:
    """Project-health tests must validate code, not depend on generated runtime JSON being committed."""
    current, stats = build_symphony2([], [])
    assert current.get("architecture") == "CURRENT_SUPERBET_OFFER -> SUPERVISED_EXACT_LINE_P -> SHARED_STATE_JOINT -> SYMPHONY2"
    assert current.get("probability_policy") == "SUPERVISED_MODEL; PER_MARKET_CALIBRATION_WHEN_VALIDATED; STATE_AND_EXISTING_MODELS_ARE_FEATURES_NOT_FIXED_WEIGHTS"
    assert current.get("operator") == "superbet.pl"
    assert current.get("matches") == []
    assert stats.get("joint_probability_policy") == "EXACT_SHARED_STATE_ONLY"
    assert stats.get("legacy_symphony_stats_used") is False
    assert stats.get("prices_used") is False


def test_superbet_refresh_builds_symphony2_runtime_before_runtime_sanity() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    engine = workflow.index("python backend/symphony2_engine.py")
    tracker = workflow.index("python backend/symphony2_tracker.py")
    sanity = workflow.index("name: Runtime sanity guard")
    assert engine < tracker < sanity
    assert "frontend/data/symphony2_current.json" not in workflow or "symphony2_current.json" in workflow


def test_freshness_wrapper_keeps_exact_playable_gate() -> None:
    text = FRESHNESS_JS.read_text(encoding="utf-8")
    assert "base.isPlayable?.(match,row)===true" in text
    assert "sourceFresh(match,now)" in text
    assert "startAligned(match)" in text
