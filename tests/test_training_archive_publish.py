from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pytest

from scripts.publish_training_archive import (
    ArchivePublishError,
    batches,
    content_type,
    prepare_candidates,
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_prepare_candidates_rehashes_raw_inputs_and_dedupes_upload_sources(tmp_path: Path):
    cache = tmp_path / "cache"
    payload = gzip.compress(b"raw")
    _write(cache / "history" / "atp_2025.csv.gz", payload)
    _write(cache / "pbp_v7" / "matches" / "42.json.gz", payload)
    inventory = {
        "schema_version": 1,
        "summary": {
            "archive_candidate_files": 2,
            "archive_candidate_bytes": len(payload) * 2,
            "unique_archive_objects": 1,
            "unique_archive_bytes": len(payload),
        },
        "archive_candidates": [
            {
                "logical_path": "history/atp_2025.csv.gz",
                "class": "historical_csv_raw",
                "provider": "historical_csv_upstream",
                "size_bytes": len(payload),
                "sha256": _sha(payload),
            },
            {
                "logical_path": "pbp_v7/matches/42.json.gz",
                "class": "pbp_match_raw",
                "provider": "live_tennis_api",
                "size_bytes": len(payload),
                "sha256": _sha(payload),
            },
        ],
    }

    rows, by_sha = prepare_candidates(inventory, cache)
    assert len(rows) == 2
    assert len(by_sha) == 1
    assert list(by_sha) == [_sha(payload)]
    assert content_type(by_sha[_sha(payload)]) == "application/gzip"


def test_prepare_candidates_rejects_cache_changed_after_inventory(tmp_path: Path):
    cache = tmp_path / "cache"
    path = cache / "pbp_v7" / "players.json"
    _write(path, b"old")
    inventory = {
        "summary": {"archive_candidate_files": 1},
        "archive_candidates": [
            {
                "logical_path": "pbp_v7/players.json",
                "class": "pbp_state",
                "provider": "live_tennis_api_index",
                "size_bytes": 3,
                "sha256": _sha(b"old"),
            }
        ],
    }
    _write(path, b"new")
    with pytest.raises(ArchivePublishError, match="sha256 changed"):
        prepare_candidates(inventory, cache)


def test_batches_are_bounded_and_lossless():
    rows = [{"n": n} for n in range(401)]
    groups = list(batches(rows, 200))
    assert [len(group) for group in groups] == [200, 200, 1]
    assert [row for group in groups for row in group] == rows


def test_archive_infrastructure_is_private_oidc_pinned_and_service_role_only():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "supabase/migrations/20260916095147_durable_training_archive.sql").read_text(encoding="utf-8")
    edge = (root / "supabase/functions/training-archive-publish/index.ts").read_text(encoding="utf-8")

    assert "'tenis-ai-training-archive-private'" in migration
    assert "false," in migration
    assert "47185920" in migration
    assert "enable row level security" in migration.lower()
    assert "revoke all on table public.training_archive_manifests from public, anon, authenticated" in migration
    assert "grant execute on function public.training_archive_confirm_objects(uuid, text[])\n  to service_role" in migration
    assert "grant execute on function public.training_archive_finalize_manifest(uuid)\n  to service_role" in migration

    assert 'const AUDIENCE = "tenis-ai-training-archive-publisher"' in edge
    assert 'const REPOSITORY = "Abeel87/tenis-ai"' in edge
    assert 'const REPOSITORY_ID = "1339352577"' in edge
    assert 'const REPOSITORY_OWNER_ID = "198365428"' in edge
    assert 'const REF = "refs/heads/main"' in edge
    assert 'const WORKFLOW = ".github/workflows/training-archive-inventory.yml"' in edge
    assert "payload.workflow_ref !== EXPECTED_WORKFLOW_REF" in edge
    assert "createSignedUploadUrl(storagePath, { upsert: false })" in edge


def test_archive_prepare_repairs_missing_physical_objects_but_rejects_size_mismatch():
    root = Path(__file__).resolve().parents[1]
    probe = (root / "supabase/migrations/20260916102800_training_archive_self_healing_probe.sql").read_text(
        encoding="utf-8"
    )
    edge = (root / "supabase/functions/training-archive-publish/index.ts").read_text(encoding="utf-8")

    assert "create or replace function public.training_archive_probe_objects" in probe.lower()
    assert "left join storage.objects" in probe.lower()
    assert "s.bucket_id = 'tenis-ai-training-archive-private'" in probe
    assert "security definer" in probe.lower()
    assert "set search_path = pg_catalog, public, storage" in probe
    assert "revoke all on function public.training_archive_probe_objects(text[])" in probe
    assert "grant execute on function public.training_archive_probe_objects(text[])\n  to service_role" in probe

    assert 'supabase.rpc("training_archive_probe_objects"' in edge
    assert "if (health.present === true && health.size_matches !== true)" in edge
    assert "Archive object has unexpected physical size" in edge
    assert "if (health.present !== true) needsUpload.add(sha256);" in edge
    assert "filter((file) => needsUpload.has(file.sha256))" in edge
    assert "createSignedUploadUrl(storagePath, { upsert: false })" in edge


def test_archive_finalize_rechecks_physical_storage_before_complete():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "supabase/migrations/20260916102800_training_archive_self_healing_probe.sql").read_text(
        encoding="utf-8"
    )
    lower = migration.lower()

    assert "create or replace function public.training_archive_finalize_manifest" in lower
    assert "set search_path = pg_catalog, public, storage" in migration
    assert "left join storage.objects" in lower
    assert "v_missing bigint" in lower
    assert "v_size_mismatch bigint" in lower
    assert "or v_missing <> 0" in lower
    assert "or v_size_mismatch <> 0" in lower
    assert "s.bucket_id = 'tenis-ai-training-archive-private'" in migration
    assert "revoke all on function public.training_archive_finalize_manifest(uuid)" in migration
    assert "grant execute on function public.training_archive_finalize_manifest(uuid)\n  to service_role" in migration
