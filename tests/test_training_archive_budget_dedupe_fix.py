from pathlib import Path


MIGRATION = "20260919114500_training_archive_budget_dedupe_fix.sql"


def _sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "supabase" / "migrations" / MIGRATION).read_text(encoding="utf-8")


def test_budget_fix_moves_enforcement_to_actual_object_reservations():
    sql = _sql()
    lower = sql.lower()

    assert "create or replace function public.training_archive_enforce_budget()" in lower
    assert "new.expected_unique_bytes" not in lower
    assert "create or replace function public.training_archive_enforce_object_budget()" in lower
    assert "from public.training_archive_objects" in lower
    assert "from storage.objects" in lower
    assert "250000000" in sql
    assert "750000000" in sql
    assert "pg_advisory_xact_lock(1339352577, 20260919)" in sql
    assert "after insert on public.training_archive_objects" in lower
    assert "for each statement" in lower
    assert "execute function public.training_archive_enforce_object_budget()" in lower


def test_budget_fix_is_non_destructive_and_keeps_manifest_guard():
    lower = _sql().lower()

    assert "before insert on public.training_archive_manifests" in lower
    assert "execute function public.training_archive_enforce_budget()" in lower
    assert "delete from" not in lower
    assert "truncate" not in lower
    assert "drop table" not in lower
    assert "update public.training_archive" not in lower
