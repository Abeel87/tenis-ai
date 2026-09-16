from pathlib import Path


def test_training_archive_budget_gate_is_server_side_and_fail_closed():
    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "supabase/migrations/20260916131500_training_archive_budget_gate.sql"
    ).read_text(encoding="utf-8")
    lower = migration.lower()

    assert "create or replace function public.training_archive_enforce_budget()" in lower
    assert "returns trigger" in lower
    assert "security definer" in lower
    assert "set search_path = pg_catalog, public, storage" in migration
    assert "from public.training_archive_objects" in lower
    assert "from storage.objects" in lower
    assert "new.expected_unique_bytes" in lower
    assert "250000000" in migration
    assert "750000000" in migration
    assert "v_archive_missing_reserved_bytes" in migration
    assert "raise exception" in lower
    assert "before insert on public.training_archive_manifests" in lower
    assert "execute function public.training_archive_enforce_budget()" in lower
    assert "revoke all on function public.training_archive_enforce_budget()" in lower
    assert "grant execute on function public.training_archive_enforce_budget()\n  to service_role" in migration


def test_budget_gate_does_not_modify_training_or_runtime_code():
    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "supabase/migrations/20260916131500_training_archive_budget_gate.sql"
    ).read_text(encoding="utf-8")
    lower = migration.lower()

    assert "update public.training_archive" not in lower
    assert "delete from" not in lower
    assert "drop table" not in lower
    assert "alter table" not in lower
    assert "training_archive_manifests" in lower
    assert "training_archive_objects" in lower
