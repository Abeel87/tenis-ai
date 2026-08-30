from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRESHNESS_JS = ROOT / "frontend" / "playable-line-freshness-v925.js"
WORKFLOW = ROOT / ".github" / "workflows" / "superbet-market-refresh.yml"
SYMPHONY = ROOT / "frontend" / "data" / "symphony_v90.json"


def _max_operator_age_minutes() -> int:
    text = FRESHNESS_JS.read_text(encoding="utf-8")
    match = re.search(r"MAX_OPERATOR_AGE_MS=(\d+)\*60\*1000", text)
    assert match, "PLAYABLE freshness limit must remain explicit and testable"
    return int(match.group(1))


def test_playable_ttl_cannot_expire_before_hourly_pipeline_can_publish() -> None:
    """Regression for v9.2.5: 12 min TTL + ~20 min rebuild blanked the whole UI.

    The operator source is refreshed hourly. The UI freshness budget therefore has
    to cover one full refresh interval plus bounded rebuild/deploy slack. Exact
    market/line matching remains a separate hard gate.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "cron: '5 * * * *'" in workflow
    assert _max_operator_age_minutes() >= 80
    assert _max_operator_age_minutes() <= 90


def test_current_symphony_report_is_not_structurally_empty() -> None:
    report = json.loads(SYMPHONY.read_text(encoding="utf-8"))
    matches = [m for m in (report.get("matches") or []) if isinstance(m, dict)]
    assert matches, "symphony_v90.json has no matches"

    useful = 0
    for match in matches:
        comps = match.get("compositions") or {}
        if any(
            isinstance(comp, dict) and len(comp.get("selection") or []) >= 2
            for comp in comps.values()
        ):
            useful += 1
    assert useful > 0, "operator-aware Symphony report has zero usable compositions"


def test_freshness_wrapper_keeps_exact_playable_gate() -> None:
    text = FRESHNESS_JS.read_text(encoding="utf-8")
    assert "base.isPlayable?.(match,row)===true" in text
    assert "sourceFresh(match,now)" in text
    assert "startAligned(match)" in text
