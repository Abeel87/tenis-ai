from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "TENIS_AI_READINESS_REQUIREMENT_MATRIX.md"
TOKEN = re.compile(r"(?<![A-Za-z0-9_])model_ready(?![A-Za-z0-9_])")

EXPECTED_LINE_SITES = {
    "backend/history_tracker.py": {145},
    "backend/market_lab_v741.py": {112},
    "backend/pbp_cache_recovery.py": {61, 95},
    "backend/pbp_enrich.py": {1224, 1290},
    "backend/autolearn_v84.py": {1223},
    "backend/specialist_learning_v79b.py": {465},
    "backend/shadow_lab_v78e6.py": {109, 125, 148},
    "backend/update.py": {372, 382},
    "backend/prediction_integrity_v78a.py": {152},
    "frontend/app.js": {30, 63, 75, 82, 98},
}


def _token_lines(relative: str) -> set[int]:
    text = (ROOT / relative).read_text(encoding="utf-8")
    return {
        index
        for index, line in enumerate(text.splitlines(), start=1)
        if TOKEN.search(line)
    }


def test_requirement_matrix_covers_every_phase3_consumer_source_line():
    matrix = MATRIX.read_text(encoding="utf-8")
    assert sum(len(lines) for lines in EXPECTED_LINE_SITES.values()) == 19
    for relative, expected_lines in EXPECTED_LINE_SITES.items():
        assert _token_lines(relative) == expected_lines
        for line in sorted(expected_lines):
            assert f"`{relative}:L{line}`" in matrix


def test_requirement_matrix_freezes_exact_token_count_and_unknown_semantics():
    total_tokens = sum(
        len(TOKEN.findall((ROOT / relative).read_text(encoding="utf-8")))
        for relative in EXPECTED_LINE_SITES
    )
    matrix = MATRIX.read_text(encoding="utf-8")
    assert total_tokens == 22
    assert "22 exact `model_ready` tokens on 19 source lines" in matrix
    assert "UNKNOWN / NO MIGRATION" in matrix
    assert "never inferred `READY` or `NOT_READY`" in matrix


def test_requirement_matrix_keeps_distinct_contracts_and_selects_observability_only():
    matrix = MATRIX.read_text(encoding="utf-8")
    assert "market_evidence_v940.market_ready" in matrix
    assert "learning_model_ready" in matrix
    assert "Superbet operator availability" in matrix
    assert "FIRST OBSERVABILITY CANDIDATE" in matrix
    assert "backend/update.py:L372" in matrix
    assert "backend/update.py:L382" in matrix
    assert "must preserve `meta.model_ready`" in matrix
    assert "No runtime/learning consumer is approved for gate replacement" in matrix


def test_phase3_audit_still_has_zero_shadow_runtime_wiring():
    for relative in EXPECTED_LINE_SITES:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "readiness_engine_shadow" not in text
        assert "readiness_engine_shadow.json" not in text
