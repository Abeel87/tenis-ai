"""The performance migration must not rewrite grace or destructive state changes."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase/migrations"
NEW = (MIGRATIONS / "20261025224109_training_archive_gc_query_plan.sql").read_text()


def body(sql, name):
    function = re.search(
        rf"create or replace function public\.{name}\b[\s\S]*?as (\$\w*\$)([\s\S]*?)\1",
        sql, re.IGNORECASE,
    )
    assert function, name
    return re.sub(r"--[^\n]*", "", function[2])


@pytest.mark.parametrize("name,old_file,end", [
    ("training_archive_retention_observe", "20260916140500_training_archive_retention_observe_returning_fix.sql",
     "update public.training_archive_gc_candidates"),
    ("training_archive_gc_prepare", "20260922203000_training_archive_gc_apply.sql", "v_expired :="),
])
def test_query_optimization_leaves_validation_grace_and_mutation_code_identical(name, old_file, end):
    def outside_query(sql):
        code = body(sql, name)
        start = code.index("with ranked_complete")
        finish = code.index(end, start)
        return " ".join((code[:start] + code[finish:]).split())

    assert outside_query(NEW) == outside_query((MIGRATIONS / old_file).read_text())


def test_migration_replaces_only_the_two_existing_gc_query_owners():
    assert re.findall(r"create or replace function public\.(\w+)", NEW, re.IGNORECASE) == [
        "training_archive_retention_observe", "training_archive_gc_prepare",
    ]
