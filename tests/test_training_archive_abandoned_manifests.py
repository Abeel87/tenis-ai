from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = next((ROOT / "supabase/migrations").glob("*_training_archive_abandoned_manifests.sql"))
GC_EDGE = (ROOT / "supabase/functions/training-archive-gc/index.ts").read_text(encoding="utf-8")
PUBLISH_EDGE = (ROOT / "supabase/functions/training-archive-publish/index.ts").read_text(encoding="utf-8")
PUBLISH_CLIENT = (ROOT / "scripts/publish_training_archive.py").read_text(encoding="utf-8")


def test_abandoned_manifest_lifecycle_is_bounded_and_private():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "'abandoned'" in sql
    assert "abandoned_at timestamptz" in sql
    assert "p_stale_hours integer default 24" in sql
    assert "p_stale_hours < 1 or p_stale_hours > 168" in sql
    assert "status = 'staged'" in sql
    assert "created_at <= v_now - make_interval(hours => p_stale_hours)" in sql
    assert "set status = 'abandoned'" in sql
    assert "delete from public.training_archive_entries" in sql
    assert "delete from public.training_archive_objects" not in sql
    assert "delete from storage.objects" not in sql
    assert "revoke all on function public.training_archive_abandon_stale_manifests(integer)" in sql
    assert "grant execute on function public.training_archive_abandon_stale_manifests(integer)" in sql
    assert "training_archive_abandon_manifest(" in sql
    assert "and m.archive_run_id = p_archive_run_id" in sql
    assert "and m.archive_run_attempt = p_archive_run_attempt" in sql
    assert "and m.source_sha = p_source_sha" in sql
    assert "for update" in sql
    assert "a complete manifest cannot be abandoned" in sql
    assert "grant execute on function public.training_archive_abandon_manifest(uuid, bigint, integer, text)" in sql


def test_gc_reaps_stale_staged_before_observation_without_shortening_grace():
    assert 'const STAGED_STALE_HOURS = 24;' in GC_EDGE
    assert '"training_archive_abandon_stale_manifests"' in GC_EDGE
    assert GC_EDGE.index('"training_archive_abandon_stale_manifests"') < GC_EDGE.index(
        '"training_archive_retention_observe"'
    )
    assert "const GRACE_HOURS = 168;" in GC_EDGE
    assert "const KEEP_LATEST = 2;" in GC_EDGE


def test_failed_publisher_abandons_only_its_owned_manifest():
    assert "async function abandon(" in PUBLISH_EDGE
    assert "await ownedManifest(supabase, auth, manifestId)" in PUBLISH_EDGE
    assert 'manifest.status === "complete"' in PUBLISH_EDGE
    assert 'supabase.rpc("training_archive_abandon_manifest"' in PUBLISH_EDGE
    assert "p_archive_run_id: auth.runId" in PUBLISH_EDGE
    assert "p_archive_run_attempt: auth.runAttempt" in PUBLISH_EDGE
    assert "p_source_sha: auth.sha" in PUBLISH_EDGE
    assert 'body.action === "abandon"' in PUBLISH_EDGE
    assert 'publisher_call({"action": "abandon", "manifest_id": manifest_id})' in PUBLISH_CLIENT
