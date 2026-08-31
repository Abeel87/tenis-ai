from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRESHNESS_JS = ROOT / "frontend" / "playable-line-freshness-v925.js"
WORKFLOW = ROOT / ".github" / "workflows" / "superbet-market-refresh.yml"
SYMPHONY = ROOT / "frontend" / "data" / "symphony2_current.json"


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


def test_current_symphony2_report_has_runtime_contract() -> None:
    report = json.loads(SYMPHONY.read_text(encoding="utf-8"))
    assert report.get("architecture") == "CURRENT_SUPERBET_OFFER -> SUPERVISED_EXACT_LINE_P -> SHARED_STATE_JOINT -> SYMPHONY2"
    matches = [m for m in (report.get("matches") or []) if isinstance(m, dict)]
    assert isinstance(matches, list)
    for match in matches:
        for row in match.get("selections") or []:
            if row.get("line") is not None:
                assert row.get("fixture_line_verified") is True
        for comp in match.get("compositions") or []:
            assert comp.get("joint_status") == "EXACT_SHARED_STATE"


def test_freshness_wrapper_keeps_exact_playable_gate() -> None:
    text = FRESHNESS_JS.read_text(encoding="utf-8")
    assert "base.isPlayable?.(match,row)===true" in text
    assert "sourceFresh(match,now)" in text
    assert "startAligned(match)" in text
