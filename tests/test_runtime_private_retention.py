from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260916064000_runtime_private_object_limit.sql"
).read_text(encoding="utf-8")
GC_FUNCTION = (
    ROOT / "supabase" / "functions" / "runtime-data-gc" / "index.ts"
).read_text(encoding="utf-8")
GC_CLIENT = (ROOT / "scripts" / "gc_runtime_private.py").read_text(encoding="utf-8")


def test_database_enforces_private_object_safety_margin_for_new_rows():
    assert "size_bytes <= 47185920" in MIGRATION
    assert "not valid" in MIGRATION.lower()
    assert "validate after stale pre-chunking generations" in MIGRATION


def test_gc_is_bound_to_exact_repo_owner_main_and_runtime_workflow():
    assert 'const REPOSITORY = "Abeel87/tenis-ai"' in GC_FUNCTION
    assert 'const REPOSITORY_ID = "1339352577"' in GC_FUNCTION
    assert 'const REPOSITORY_OWNER_ID = "198365428"' in GC_FUNCTION
    assert 'const REF = "refs/heads/main"' in GC_FUNCTION
    assert 'const WORKFLOW = ".github/workflows/runtime-private-delivery.yml"' in GC_FUNCTION
    assert "repository_id" in GC_FUNCTION
    assert "repository_owner_id" in GC_FUNCTION
    assert "workflow_ref" in GC_FUNCTION


def test_gc_never_deletes_active_head_and_preserves_one_rollback_generation():
    assert "runtime_data_heads" in GC_FUNCTION
    assert "RETIRED_KEEP_PER_LAYER = 1" in GC_FUNCTION
    assert "STAGED_GRACE_MS = 6 * 60 * 60 * 1000" in GC_FUNCTION
    assert 'row.status === "retired" || row.status === "staged"' in GC_FUNCTION
    assert '.in("status", ["retired", "staged"])' in GC_FUNCTION
    assert "supabase.storage.from(BUCKET).remove" in GC_FUNCTION
    assert "dry_run" in GC_FUNCTION


def test_gc_client_uses_distinct_oidc_audience_and_no_service_secret():
    assert 'AUDIENCE = "tenis-ai-runtime-gc"' in GC_CLIENT
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" in GC_CLIENT
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" in GC_CLIENT
    assert "SUPABASE_SERVICE_ROLE_KEY" not in GC_CLIENT
    assert "--dry-run" in GC_CLIENT
