from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "supabase/migrations/20260919114500_training_archive_budget_dedupe_fix.sql"
NEW = ROOT / "supabase/migrations/20260925104128_training_archive_budget_300mb.sql"


def test_archive_budget_increase_preserves_both_guard_bodies_and_project_ceiling():
    original = OLD.read_text(encoding="utf-8")
    migration = NEW.read_text(encoding="utf-8")
    original_guards = original.split("create or replace function", 1)[1].split(
        "drop trigger if exists", 1
    )[0]
    updated_guards = migration.split("create or replace function", 1)[1]
    assert original_guards.count("250000000") == 2
    assert updated_guards == original_guards.replace("250000000", "300000000")
    assert updated_guards.count("750000000") == 2
    assert "drop trigger" not in migration.lower()
