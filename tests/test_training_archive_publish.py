from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pytest

import scripts.publish_training_archive as archive_publish
from scripts.publish_training_archive import (
    ArchivePublishError,
    batches,
    content_type,
    prepare_candidates,
    publisher_call,
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


def test_oidc_token_retries_transient_failure_and_reuses_cached_token(monkeypatch):
    responses = iter([(503, {}), (200, {"value": "oidc-token"})])
    calls = []
    sleeps = []
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://oidc.example/token")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-token")
    monkeypatch.setattr(archive_publish, "_oidc_cached_token", None)
    monkeypatch.setattr(archive_publish, "_oidc_cached_at", 0.0)
    monkeypatch.setattr(archive_publish, "_json_request", lambda *a, **k: (calls.append(1), next(responses))[1])
    monkeypatch.setattr(archive_publish.time, "sleep", lambda delay: sleeps.append(delay))

    assert archive_publish.oidc_token() == "oidc-token"
    assert archive_publish.oidc_token() == "oidc-token"
    assert len(calls) == 2
    assert sleeps == [1]


def test_publisher_call_surfaces_only_bounded_safe_error_detail(monkeypatch):
    def fake_request(*args, **kwargs):
        return 500, {
            "error": "training-archive-publish: error",
            "detail": {
                "code": "PGRST204",
                "name": "PostgrestError",
                "message": "schema\ncache mismatch",
                "token": "DO_NOT_LOG_TOKEN",
            },
            "raw_secret": "DO_NOT_LOG_RAW",
        }

    monkeypatch.setattr("scripts.publish_training_archive.oidc_token", lambda: "oidc-token")
    monkeypatch.setattr("scripts.publish_training_archive._json_request", fake_request)

    with pytest.raises(ArchivePublishError) as exc_info:
        publisher_call({"action": "start"})

    message = str(exc_info.value)
    assert "HTTP 500" in message
    assert "training-archive-publish: error" in message
    assert "code=PGRST204" in message
    assert "name=PostgrestError" in message
    assert "message=schema cache mismatch" in message
    assert "DO_NOT_LOG_TOKEN" not in message
    assert "DO_NOT_LOG_RAW" not in message


def test_publisher_call_does_not_log_unstructured_error_detail(monkeypatch):
    monkeypatch.setattr("scripts.publish_training_archive.oidc_token", lambda: "oidc-token")
    monkeypatch.setattr(
        "scripts.publish_training_archive._json_request",
        lambda *args, **kwargs: (500, {"error": "publisher failed", "detail": "DO_NOT_LOG_BODY"}),
    )

    with pytest.raises(ArchivePublishError) as exc_info:
        publisher_call({"action": "start"})

    assert str(exc_info.value) == "publisher start failed: HTTP 500: publisher failed"
    assert "DO_NOT_LOG_BODY" not in str(exc_info.value)


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


def test_oversized_json_is_losslessly_staged_without_mutating_cache(tmp_path, monkeypatch):
    payload = b'{"players":[' + b' {"id":42},' * 200 + b'null]}'
    cache = tmp_path / 'cache'
    source = cache / 'pbp_v7/players.json'
    _write(source, payload)
    inventory = {'summary': {'archive_candidate_files': 1}, 'archive_candidates': [{
        'logical_path': 'pbp_v7/players.json', 'class': 'pbp_state',
        'provider': 'live_tennis_api_index', 'size_bytes': len(payload),
        'sha256': _sha(payload),
    }]}
    monkeypatch.setattr(archive_publish, 'MAX_OBJECT_BYTES', 256)
    stage = tmp_path / 'stage'
    rows, sources = prepare_candidates(inventory, cache, staging_root=stage)
    row = rows[0]
    compressed = sources[row['sha256']].read_bytes()
    assert row['path'] == 'pbp_v7/players.json.gz'
    assert row['size_bytes'] == len(compressed) <= 256
    assert row['sha256'] == _sha(compressed)
    assert gzip.decompress(compressed) == payload
    assert source.read_bytes() == payload
    assert not source.with_suffix('.json.gz').exists()
    assert inventory['archive_candidates'][0]['sha256'] == _sha(payload)
    # Gzip header must not include a random temporary filename or wall-clock time.
    second, second_sources = prepare_candidates(inventory, cache, staging_root=tmp_path / 'other')
    assert second == rows
    assert second_sources[row['sha256']].read_bytes() == compressed


def test_archive_publish_uses_stored_sizes_and_keeps_stage_until_upload(tmp_path, monkeypatch):
    import json
    payload = b'{"players":[' + b' {"id":42},' * 200 + b'null]}'
    cache = tmp_path / 'cache'
    _write(cache / 'pbp_v7/players.json', payload)
    inventory = {'schema_version': 1, 'summary': {'archive_candidate_files': 1,
        'archive_candidate_bytes': len(payload), 'unique_archive_objects': 1,
        'unique_archive_bytes': len(payload)}, 'archive_candidates': [{
        'logical_path': 'pbp_v7/players.json', 'class': 'pbp_state',
        'provider': 'live_tennis_api_index', 'size_bytes': len(payload),
        'sha256': _sha(payload)}]}
    path = tmp_path / 'inventory.json'
    path.write_text(json.dumps(inventory))
    monkeypatch.setattr(archive_publish, 'MAX_OBJECT_BYTES', 256)
    calls, uploaded = [], []
    def call(body):
        calls.append(body)
        if body['action'] == 'start':
            return {'manifest_id': 'manifest'}
        if body['action'] == 'prepare_batch':
            return {'uploads': [{'sha256': body['files'][0]['sha256'], 'signed_url': 'mock-upload'}]}
        return {'ok': True}
    def upload(url, source):
        assert gzip.decompress(source.read_bytes()) == payload
        uploaded.append(source)
    monkeypatch.setattr(archive_publish, 'publisher_call', call)
    monkeypatch.setattr(archive_publish, 'upload_signed', upload)
    result = archive_publish.publish(path, cache)
    assert result['uploaded_objects'] == 1
    start, batch = calls[0], calls[1]
    assert start['expected_bytes'] == batch['files'][0]['size_bytes'] < len(payload)
    assert start['expected_unique_bytes'] == start['expected_bytes']
    assert start['expected_unique_objects'] == start['expected_files'] == 1
    assert all(not source.exists() for source in uploaded)
    assert (cache / 'pbp_v7/players.json').read_bytes() == payload


def test_oversized_existing_gzip_is_not_silently_recompressed(tmp_path, monkeypatch):
    cache = tmp_path / 'cache'
    payload = b'already-compressed-object'
    _write(cache / 'pbp_v7/matches/42.json.gz', payload)
    inventory = {'summary': {'archive_candidate_files': 1}, 'archive_candidates': [{
        'logical_path': 'pbp_v7/matches/42.json.gz', 'class': 'pbp_match_raw',
        'provider': 'live_tennis_api', 'size_bytes': len(payload), 'sha256': _sha(payload)}]}
    monkeypatch.setattr(archive_publish, 'MAX_OBJECT_BYTES', 8)
    with pytest.raises(ArchivePublishError, match='exceeds'):
        prepare_candidates(inventory, cache, staging_root=tmp_path / 'stage')


def test_incompressible_source_stays_fail_closed_before_manifest(tmp_path, monkeypatch):
    import json
    import random
    payload = random.Random(42).randbytes(2048)
    cache = tmp_path / 'cache'
    _write(cache / 'pbp_v7/players.json', payload)
    inventory = {'summary': {'archive_candidate_files': 1}, 'archive_candidates': [{
        'logical_path': 'pbp_v7/players.json', 'class': 'pbp_state',
        'provider': 'live_tennis_api_index', 'size_bytes': len(payload), 'sha256': _sha(payload)}]}
    path = tmp_path / 'inventory.json'
    path.write_text(json.dumps(inventory))
    monkeypatch.setattr(archive_publish, 'MAX_OBJECT_BYTES', 256)
    calls = []
    monkeypatch.setattr(archive_publish, 'publisher_call', lambda body: calls.append(body))
    with pytest.raises(ArchivePublishError, match='compressed archive object exceeds'):
        archive_publish.publish(path, cache)
    assert calls == []
    assert (cache / 'pbp_v7/players.json').read_bytes() == payload


def test_archive_staging_rejects_source_changed_during_compression(tmp_path):
    source = tmp_path / 'players.json'
    source.write_bytes(b'new')
    with pytest.raises(ArchivePublishError, match='source changed during'):
        archive_publish._stage_gzip(source, tmp_path / 'out.json.gz', _sha(b'old'), 3)


def test_compressed_archive_path_collision_is_rejected(tmp_path, monkeypatch):
    payload = b'a' * 2048
    cache = tmp_path / 'cache'
    compressed = gzip.compress(payload)
    entries = []
    for logical, data in [('pbp_v7/players.json', payload), ('pbp_v7/players.json.gz', compressed)]:
        _write(cache / logical, data)
        entries.append({'logical_path': logical, 'class': 'pbp_state',
                        'provider': 'live_tennis_api_index', 'size_bytes': len(data), 'sha256': _sha(data)})
    monkeypatch.setattr(archive_publish, 'MAX_OBJECT_BYTES', 256)
    with pytest.raises(ArchivePublishError, match='duplicate archive path'):
        prepare_candidates({'summary': {'archive_candidate_files': 2}, 'archive_candidates': entries},
                           cache, staging_root=tmp_path / 'stage')
