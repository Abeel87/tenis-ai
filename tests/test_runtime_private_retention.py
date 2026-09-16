from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260916064000_runtime_private_object_limit.sql"
).read_text(encoding="utf-8")
VALIDATION_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260916074200_validate_runtime_private_object_limit.sql"
).read_text(encoding="utf-8")
GC_FUNCTION = (
    ROOT / "supabase" / "functions" / "runtime-data-gc" / "index.ts"
).read_text(encoding="utf-8")
GC_CLIENT = (ROOT / "scripts" / "gc_runtime_private.py").read_text(encoding="utf-8")
WORKFLOW = (
    ROOT / ".github" / "workflows" / "runtime-private-delivery.yml"
).read_text(encoding="utf-8")


def test_database_enforces_private_object_safety_margin_for_new_rows():
    assert "size_bytes <= 47185920" in MIGRATION
    assert "not valid" in MIGRATION.lower()
    assert "validate after stale pre-chunking generations" in MIGRATION
    assert "validate constraint runtime_data_objects_size_bytes_check" in VALIDATION_MIGRATION.lower()


def test_gc_is_bound_to_exact_repo_owner_main_and_runtime_workflow():
    assert 'const REPOSITORY = "Abeel87/tenis-ai"' in GC_FUNCTION
    assert 'const REPOSITORY_ID = "1339352577"' in GC_FUNCTION
    assert 'const REPOSITORY_OWNER_ID = "198365428"' in GC_FUNCTION
    assert 'const REF = "refs/heads/main"' in GC_FUNCTION
    assert 'const WORKFLOW = ".github/workflows/runtime-private-delivery.yml"' in GC_FUNCTION
    assert 'new Set(["workflow_run", "workflow_dispatch", "push"])' in GC_FUNCTION
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


def test_gc_immediately_reaps_structurally_invalid_staged_generation():
    assert "MAX_OBJECT_BYTES = 47185920" in GC_FUNCTION
    assert "size_bytes: number" in GC_FUNCTION
    assert 'logical_path,storage_path,size_bytes' in GC_FUNCTION
    assert "invalidStaged" in GC_FUNCTION
    assert "Number(obj.size_bytes) > MAX_OBJECT_BYTES" in GC_FUNCTION
    assert "if (invalidStaged.has(k)) continue" in GC_FUNCTION
    assert 'invalid_staged_over_limit: "delete_immediately"' in GC_FUNCTION
    assert "invalid_staged_generations" in GC_FUNCTION


def test_gc_paginates_every_metadata_source_deterministically():
    assert "QUERY_PAGE_SIZE = 500" in GC_FUNCTION
    assert "async function paged" in GC_FUNCTION
    assert ".range(from, to)" in GC_FUNCTION
    assert '.from("runtime_data_generations")' in GC_FUNCTION
    assert '.from("runtime_data_heads")' in GC_FUNCTION
    assert '.from("runtime_data_objects")' in GC_FUNCTION
    assert '.order("logical_path", { ascending: true })' in GC_FUNCTION
    assert "scanned:" in GC_FUNCTION


def test_gc_client_uses_distinct_oidc_audience_and_no_service_secret():
    assert 'AUDIENCE = "tenis-ai-runtime-gc"' in GC_CLIENT
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" in GC_CLIENT
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" in GC_CLIENT
    assert "SUPABASE_SERVICE_ROLE_KEY" not in GC_CLIENT
    assert "--dry-run" in GC_CLIENT


def test_gc_runs_for_merge_rollout_and_every_successful_private_delivery_event():
    assert "push:" in WORKFLOW
    assert "branches: [main]" in WORKFLOW
    assert "github.event_name == 'push'" in WORKFLOW
    assert "github.event_name == 'workflow_dispatch'" in WORKFLOW
    assert "github.event_name == 'workflow_run'" in WORKFLOW
    assert "github.event.workflow_run.conclusion == 'success'" in WORKFLOW
    assert "github.event.workflow_run.head_branch == 'main'" in WORKFLOW
    assert "python scripts/gc_runtime_private.py --dry-run" in WORKFLOW
    assert "python scripts/gc_runtime_private.py\n" in WORKFLOW
    assert WORKFLOW.index("gc_runtime_private.py --dry-run") < WORKFLOW.rindex(
        "gc_runtime_private.py"
    )
    assert "contents: write" not in WORKFLOW


def test_gc_is_serialized_after_publish_without_losing_push_cleanup():
    gc_block = WORKFLOW.split("\n  gc:\n", 1)[1]
    assert "    needs: publish\n" in gc_block
    assert "      always() &&\n" in gc_block
    assert "needs.publish.result == 'success'" in gc_block
    assert "github.event_name == 'push' ||" in gc_block
    assert gc_block.index("github.event_name == 'push' ||") < gc_block.index(
        "needs.publish.result == 'success'"
    )
