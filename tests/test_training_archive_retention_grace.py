from pathlib import Path


MIGRATION = "supabase/migrations/20260916135000_training_archive_retention_grace_audit.sql"


def _sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / MIGRATION).read_text(encoding="utf-8")


def test_grace_phase_adds_private_candidate_and_audit_tables():
    sql = _sql()
    lower = sql.lower()

    assert "create table if not exists public.training_archive_gc_candidates" in lower
    assert "references public.training_archive_objects(sha256) on delete restrict" in lower
    assert "create table if not exists public.training_archive_retention_audit" in lower
    assert lower.count("enable row level security") >= 2
    assert "revoke all on table public.training_archive_gc_candidates" in lower
    assert "revoke all on table public.training_archive_retention_audit" in lower
    assert "grant select on table public.training_archive_gc_candidates" in lower
    assert "grant select on table public.training_archive_retention_audit" in lower
    assert "to service_role" in lower


def test_observer_has_conservative_seven_day_default_and_retention_rules():
    sql = _sql()
    lower = sql.lower()

    assert "create or replace function public.training_archive_retention_observe" in lower
    assert "p_keep_latest integer default 2" in lower
    assert "p_grace_hours integer default 168" in lower
    assert "p_keep_latest < 2" in lower
    assert "p_grace_hours < 24" in lower
    assert "p_grace_hours > 720" in lower
    assert "row_number() over (order by m.created_at desc" in lower
    assert "where p.released_at is null" in lower
    assert "where m.status <> 'complete'" in lower
    assert "v_now + make_interval(hours => p_grace_hours)" in lower
    assert "grace_until <= v_now" in lower


def test_observer_restarts_grace_after_eligibility_is_lost_and_regained():
    sql = _sql()
    lower = sql.lower()

    assert "set current_eligible = false" in lower
    assert "eligibility_lost_at = v_now" in lower
    assert "when public.training_archive_gc_candidates.current_eligible" in lower
    assert "else excluded.first_eligible_at" in lower
    assert "else excluded.grace_until" in lower
    assert "greatest(" in lower
    assert "observation_count = public.training_archive_gc_candidates.observation_count + 1" in lower


def test_observer_is_service_role_only_and_audits_every_observation():
    sql = _sql()
    lower = sql.lower()

    assert "security definer" in lower
    assert "set search_path = pg_catalog, public" in lower
    assert "insert into public.training_archive_retention_audit" in lower
    assert "revoke all on function public.training_archive_retention_observe(integer, integer)" in lower
    assert "grant execute on function public.training_archive_retention_observe(integer, integer)\n  to service_role" in sql


def test_grace_phase_cannot_expire_or_delete_archive_data():
    lower = _sql().lower()

    assert "delete from public.training_archive" not in lower
    assert "delete from storage.objects" not in lower
    assert "storage.objects" not in lower
    assert ".remove(" not in lower
    assert "update public.training_archive_manifests" not in lower
    assert "update public.training_archive_entries" not in lower
    assert "update public.training_archive_objects" not in lower
    assert "drop table" not in lower
