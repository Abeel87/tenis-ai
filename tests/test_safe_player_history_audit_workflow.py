from pathlib import Path


def _workflow() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "safe-player-history-audit.yml"
    ).read_text(encoding="utf-8")


def test_identity_audit_restores_existing_cache_and_never_receives_live_api_secret():
    text = _workflow()

    assert "actions/cache/restore@v4" in text
    assert "tennis-history-${{ runner.os }}-" in text
    assert "data/cache/pbp_v7/players.json" in text
    assert "data/cache/pbp_v7/matches" in text
    assert "provider_identity_evidence.py" in text
    assert "secrets.LIVE_TENNIS_API_KEY" not in text
    assert "LIVE_TENNIS_API_KEY: ''" in text
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text


def test_identity_audit_runs_full_regression_before_real_cache_measurement():
    text = _workflow()

    regression = "python -m pytest -q"
    restore = "actions/cache/restore@v4"
    audit = "python backend/provider_identity_evidence.py"
    assert regression in text and restore in text and audit in text
    assert text.index(regression) < text.index(restore) < text.index(audit)


def test_identity_audit_uploads_evidence_without_publishing_runtime_data():
    text = _workflow()

    assert "actions/upload-artifact@v4" in text
    assert "artifacts/provider_identity_evidence.json" in text
    assert "git push" not in text
    assert "frontend/data" not in text
    assert "id-token: write" not in text
