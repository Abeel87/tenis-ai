from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260916080500_scope_identity_helper_rpcs.sql"
).read_text(encoding="utf-8")


def test_identity_helpers_are_self_scoped_for_authenticated_callers():
    for name in ("can_access_community", "is_admin", "is_staff"):
        assert f"create or replace function public.{name}" in MIGRATION.lower()
    assert MIGRATION.count("check_uid = auth.uid()") == 3
    assert MIGRATION.count("coalesce(auth.role(), '') = 'service_role'") == 3
    assert MIGRATION.count("auth.uid() is not null") == 3


def test_identity_helpers_do_not_inherit_public_execute():
    for name in ("can_access_community", "is_admin", "is_staff"):
        signature = f"public.{name}(uuid)"
        assert f"revoke all on function {signature} from public;" in MIGRATION.lower()
        assert (
            f"grant execute on function {signature} to authenticated, service_role;"
            in MIGRATION.lower()
        )


def test_helper_semantics_and_ban_checks_are_preserved():
    assert "p.age_confirmed_at is not null" in MIGRATION.lower()
    assert "p.community_access = true" in MIGRATION.lower()
    assert MIGRATION.lower().count("p.banned_at is null") == 3
    assert "p.role = 'admin'" in MIGRATION.lower()
    assert "p.role in ('admin', 'moderator')" in MIGRATION.lower()
