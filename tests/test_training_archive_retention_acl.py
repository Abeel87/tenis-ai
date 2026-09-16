from pathlib import Path


MIGRATION = "supabase/migrations/20260916141500_training_archive_retention_acl_hardening.sql"


def _sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / MIGRATION).read_text(encoding="utf-8")


def test_service_role_is_read_only_on_retention_metadata_tables():
    sql = _sql()
    lower = sql.lower()

    assert "revoke all on table public.training_archive_gc_candidates\n  from service_role" in lower
    assert "grant select on table public.training_archive_gc_candidates\n  to service_role" in lower
    assert "revoke all on table public.training_archive_retention_audit\n  from service_role" in lower
    assert "grant select on table public.training_archive_retention_audit\n  to service_role" in lower


def test_retention_audit_sequence_has_no_direct_client_or_service_role_grants():
    lower = _sql().lower()

    assert "revoke all on sequence public.training_archive_retention_audit_observation_id_seq" in lower
    assert "from public, anon, authenticated, service_role" in lower
    assert "grant" not in lower.split("revoke all on sequence", 1)[1]


def test_acl_hardening_is_non_destructive():
    lower = _sql().lower()

    assert "delete from" not in lower
    assert "drop table" not in lower
    assert "drop function" not in lower
    assert "storage.objects" not in lower
    assert ".remove(" not in lower
