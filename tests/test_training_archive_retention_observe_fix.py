from pathlib import Path


MIGRATION = "supabase/migrations/20260916140500_training_archive_retention_observe_returning_fix.sql"


def _sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / MIGRATION).read_text(encoding="utf-8")


def test_retention_observer_aliases_audit_insert_for_returning():
    sql = _sql()
    lower = sql.lower()

    assert "insert into public.training_archive_retention_audit as audit" in lower
    assert "returning audit.observation_id into v_observation_id" in lower
    assert "returning observation_id into v_observation_id" not in lower


def test_hotfix_preserves_service_role_only_function_acl():
    sql = _sql()
    lower = sql.lower()

    assert "create or replace function public.training_archive_retention_observe" in lower
    assert "security definer" in lower
    assert "set search_path = pg_catalog, public" in lower
    assert "revoke all on function public.training_archive_retention_observe(integer, integer)" in lower
    assert "grant execute on function public.training_archive_retention_observe(integer, integer)\n  to service_role" in sql


def test_hotfix_is_non_destructive():
    lower = _sql().lower()

    assert "delete from public.training_archive" not in lower
    assert "delete from storage.objects" not in lower
    assert "storage.objects" not in lower
    assert ".remove(" not in lower
    assert "update public.training_archive_manifests" not in lower
    assert "update public.training_archive_entries" not in lower
    assert "update public.training_archive_objects" not in lower
    assert "drop table" not in lower
