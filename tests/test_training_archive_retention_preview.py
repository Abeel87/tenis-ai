from pathlib import Path


MIGRATION = "supabase/migrations/20260916133500_training_archive_retention_preview.sql"


def _sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / MIGRATION).read_text(encoding="utf-8")


def test_retention_preview_adds_private_service_role_pins():
    sql = _sql()
    lower = sql.lower()

    assert "create table if not exists public.training_archive_manifest_pins" in lower
    assert "references public.training_archive_manifests(manifest_id) on delete restrict" in lower
    assert "enable row level security" in lower
    assert "revoke all on table public.training_archive_manifest_pins" in lower
    assert "from public, anon, authenticated" in lower
    assert "to service_role" in lower
    assert "where released_at is null" in lower


def test_retention_preview_keeps_latest_pins_and_inflight_manifests():
    sql = _sql()
    lower = sql.lower()

    assert "create or replace function public.training_archive_retention_preview" in lower
    assert "p_keep_latest integer default 2" in lower
    assert "p_keep_latest < 2" in lower
    assert "row_number() over (order by m.created_at desc" in lower
    assert "active_pinned_manifests" in lower
    assert "retained_complete" in lower
    assert "where m.status <> 'complete'" in lower
    assert "eventual_reclaimable_objects" in lower
    assert "eventual_reclaimable_bytes" in lower
    assert "security definer" in lower
    assert "set search_path = pg_catalog, public" in lower
    assert "revoke all on function public.training_archive_retention_preview(integer)" in lower
    assert "grant execute on function public.training_archive_retention_preview(integer)\n  to service_role" in sql


def test_retention_phase_is_preview_only_and_cannot_delete_archive_data():
    lower = _sql().lower()

    assert "delete from public.training_archive" not in lower
    assert "storage.objects" not in lower
    assert ".remove(" not in lower
    assert "drop table" not in lower
    assert "update public.training_archive_manifests" not in lower
