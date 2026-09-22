import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/20260922203000_training_archive_gc_apply.sql").read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/training-archive-gc/index.ts").read_text(encoding="utf-8")
CLIENT = (ROOT / "scripts/gc_training_archive.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/training-archive-gc.yml").read_text(encoding="utf-8")
INVENTORY_WORKFLOW = (ROOT / ".github/workflows/training-archive-inventory.yml").read_text(encoding="utf-8")
DOC = (ROOT / "docs/training-archive-gc.md").read_text(encoding="utf-8")


def test_apply_phase_preserves_manifest_provenance_and_seven_day_policy():
    lower = MIGRATION.lower()
    assert "status in ('staged', 'complete', 'expired')" in lower
    assert "expired_at timestamptz" in lower
    assert "p_keep_latest integer default 2" in lower
    assert "p_grace_hours integer default 168" in lower
    assert "training_archive_retention_observe(p_keep_latest, p_grace_hours)" in lower
    assert "where m.status <> 'complete'" in lower
    assert "set status = 'expired', expired_at = v_now" in lower
    assert "delete from public.training_archive_entries" in lower
    assert "delete from public.training_archive_manifests" not in lower


def test_manifest_expiry_requires_grace_ready_candidate_and_exact_storage_size():
    lower = MIGRATION.lower()
    assert "g.current_eligible" in lower
    assert "g.grace_until <= v_now" in lower
    assert "join storage.objects s" in lower
    assert "s.bucket_id = 'tenis-ai-training-archive-private'" in lower
    assert "coalesce((s.metadata ->> 'size')::bigint, -1) = o.size_bytes" in lower
    assert "retained_references" in lower
    assert "training_archive_manifest_pins" in lower


def test_object_delete_is_two_phase_fail_closed_and_reference_safe():
    lower = MIGRATION.lower()
    claim_start = lower.index("create or replace function public.training_archive_gc_claim_object")
    finalize_start = lower.index("create or replace function public.training_archive_gc_finalize_object")
    skip_start = lower.index("create or replace function public.training_archive_gc_skip_object")
    claim = lower[claim_start:finalize_start]
    finalize = lower[finalize_start:skip_start]
    assert "training_archive_entries" in claim
    assert "current_eligible" in claim
    assert "grace_until > now()" in claim
    assert "remove_started_at" in claim
    assert "missing_unexpected" in claim
    assert "resume_finalize" in claim
    assert "training_archive_entries" in finalize
    assert "grace_until <= now()" in finalize
    assert "storage.objects" in finalize
    assert "remove_started_at is null" in finalize
    assert finalize.index("delete from public.training_archive_gc_candidates") < finalize.index(
        "delete from public.training_archive_objects"
    )


def test_apply_audit_is_private_and_records_object_level_terminal_state():
    lower = MIGRATION.lower()
    assert "create table if not exists public.training_archive_gc_apply_audit" in lower
    assert "create table if not exists public.training_archive_gc_apply_objects" in lower
    assert "remove_started_at timestamptz" in lower
    assert "deleted_at timestamptz" in lower
    assert "skipped_at timestamptz" in lower
    assert lower.count("enable row level security") >= 2
    assert "grant select on table public.training_archive_gc_apply_audit to service_role" in lower
    assert "grant select on table public.training_archive_gc_apply_objects to service_role" in lower
    assert "grant insert" not in lower
    assert "grant update" not in lower
    assert "grant delete" not in lower


def test_edge_function_is_exactly_oidc_bound_and_never_exposes_service_secret_to_caller():
    assert 'const AUDIENCE = "tenis-ai-training-archive-gc"' in EDGE
    assert 'const REPOSITORY = "Abeel87/tenis-ai"' in EDGE
    assert 'const REPOSITORY_ID = "1339352577"' in EDGE
    assert 'const REPOSITORY_OWNER_ID = "198365428"' in EDGE
    assert 'const REF = "refs/heads/main"' in EDGE
    assert 'const WORKFLOW = ".github/workflows/training-archive-gc.yml"' in EDGE
    assert 'new Set(["schedule", "workflow_dispatch"])' in EDGE
    assert "repository_id" in EDGE and "repository_owner_id" in EDGE and "workflow_ref" in EDGE
    assert "SUPABASE_SERVICE_ROLE_KEY" not in CLIENT
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" in CLIENT


def test_edge_and_client_share_source_derived_fail_closed_contract():
    edge_match = re.search(r'const CONTRACT_REVISION = "(sha256:[0-9a-f]{64})";', EDGE)
    client_match = re.search(r'EXPECTED_CONTRACT_REVISION = "(sha256:[0-9a-f]{64})"', CLIENT)
    assert edge_match is not None
    assert client_match is not None
    assert edge_match.group(1) == client_match.group(1)
    normalized = re.sub(
        r'const CONTRACT_REVISION = "sha256:[0-9a-f]{64}";',
        'const CONTRACT_REVISION = "sha256:<SOURCE>";',
        EDGE,
        count=1,
    )
    expected = "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    assert edge_match.group(1) == expected
    assert "deployed training-archive-gc contract is stale" in CLIENT


def test_workflows_serialize_publish_and_gc_and_preview_before_apply():
    assert "group: training-archive-maintenance" in WORKFLOW
    assert "group: training-archive-maintenance" in INVENTORY_WORKFLOW
    assert "cancel-in-progress: false" in WORKFLOW
    assert "cron: '20 2,8,14,20 * * *'" in WORKFLOW
    assert "id-token: write" in WORKFLOW
    assert "python scripts/gc_training_archive.py --dry-run" in WORKFLOW
    assert "python scripts/gc_training_archive.py\n" in WORKFLOW
    assert WORKFLOW.index("--dry-run") < WORKFLOW.rindex("gc_training_archive.py")


def test_docs_keep_hard_safety_boundary_visible():
    lower = DOC.lower()
    assert "168 hours" in lower
    assert "2 newest" in lower
    assert "never hard-deletes a retained manifest" in lower
    assert "remove_started_at" in lower
    assert "contract_revision" in lower
