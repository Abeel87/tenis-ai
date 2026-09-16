from pathlib import Path


def _workflow() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "training-archive-inventory.yml"
    ).read_text(encoding="utf-8")


def test_archive_workflow_uses_oidc_and_exact_restored_cache_provenance():
    text = _workflow()

    assert "id-token: write" in text
    assert "id: cache" in text
    assert "steps.cache.outputs.cache-matched-key" in text
    assert "MATCHED_CACHE_KEY" in text
    assert "TRAINING_ARCHIVE_SOURCE_CACHE_KEY" in text
    assert "TRAINING_ARCHIVE_PRODUCER_RUN_ID" in text
    assert "TRAINING_ARCHIVE_PRODUCER_HEAD_SHA" in text
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text
    assert "SUPABASE_SECRET_KEYS" not in text


def test_archive_workflow_publishes_only_after_inventory_and_preserves_runs():
    text = _workflow()

    inventory = "python backend/training_archive_inventory.py"
    publish = "python scripts/publish_training_archive.py"
    assert inventory in text and publish in text
    assert text.index(inventory) < text.index(publish)
    assert "cancel-in-progress: false" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text


def test_archive_activation_push_is_narrow_and_self_bootstrapping():
    text = _workflow()

    assert "push:" in text
    assert "branches: [main]" in text
    assert "'.github/workflows/training-archive-inventory.yml'" in text
    assert "'scripts/publish_training_archive.py'" in text
    assert "'supabase/functions/training-archive-publish/**'" in text
    assert "'supabase/migrations/20260916095147_durable_training_archive.sql'" in text

    # The archive trigger must not take ownership of model/runtime producer paths.
    assert "backend/update.py" not in text
    assert "frontend/data/**" not in text
