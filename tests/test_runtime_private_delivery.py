from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase" / "migrations" / "20260916032018_runtime_private_delivery_staging.sql"
).read_text(encoding="utf-8")
PUBLISHER = (
    ROOT / "supabase" / "functions" / "runtime-data-publish" / "index.ts"
).read_text(encoding="utf-8")
READER = (
    ROOT / "supabase" / "functions" / "runtime-data-read" / "index.ts"
).read_text(encoding="utf-8")
WORKFLOW = (
    ROOT / ".github" / "workflows" / "runtime-private-delivery.yml"
).read_text(encoding="utf-8")
HELPER = (ROOT / "scripts" / "publish_runtime_private.py").read_text(encoding="utf-8")


def test_private_bucket_and_metadata_are_closed_to_browser_roles():
    assert "'tenis-ai-runtime-private'" in MIGRATION
    assert "false," in MIGRATION
    assert "enable row level security" in MIGRATION
    assert "from public, anon, authenticated" in MIGRATION
    assert "to service_role" in MIGRATION
    assert "runtime_data_generation_ready" in MIGRATION
    assert "runtime_data_activate_generation" in MIGRATION


def test_runtime_objects_are_content_addressed_and_cas_activated():
    assert "storage_path = ('objects/' || sha256 || '.json')" in MIGRATION
    assert "p_expected_generation" in MIGRATION
    assert "for update" in MIGRATION
    assert "Activation rejected by CAS guard" in PUBLISHER
    assert "createSignedUploadUrl" in PUBLISHER
    assert "upsert: false" in PUBLISHER


def test_publisher_is_bound_to_this_repo_main_and_one_workflow():
    assert 'const REPOSITORY = "Abeel87/tenis-ai"' in PUBLISHER
    assert 'const REPOSITORY_ID = "1339352577"' in PUBLISHER
    assert 'const REPOSITORY_OWNER_ID = "198365428"' in PUBLISHER
    assert 'const REF = "refs/heads/main"' in PUBLISHER
    assert 'const WORKFLOW = ".github/workflows/runtime-private-delivery.yml"' in PUBLISHER
    assert 'new Set(["workflow_run", "workflow_dispatch"])' in PUBLISHER
    assert "repository_id" in PUBLISHER
    assert "repository_owner_id" in PUBLISHER
    assert "workflow_ref" in PUBLISHER


def test_reader_revalidates_user_and_never_downgrades_admin_tier():
    assert ".auth.getUser(token)" in READER
    assert '.select("role,banned_at")' in READER
    assert "profile.banned_at" in READER
    assert 'target.access_tier === "c" && profile.role !== "admin"' in READER
    assert "Never fall back to an older, less restrictive copy" in READER
    assert "createSignedUrl" in READER


def test_staging_workflow_has_no_repo_write_or_git_push():
    assert "contents: read" in WORKFLOW
    assert "id-token: write" in WORKFLOW
    assert "workflow_run:" in WORKFLOW
    assert "head_branch == 'main'" in WORKFLOW
    assert "git push" not in WORKFLOW
    assert "contents: write" not in WORKFLOW
    assert "publish_runtime_private.py" in WORKFLOW


def test_unknown_runtime_json_defaults_to_admin_technical_tier():
    assert 'return "c"' in HELPER
    assert '"data/delivery/index.json"' in HELPER
    assert '"data/delivery/matches/*.json"' in HELPER
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" in HELPER
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" in HELPER


def test_private_delivery_does_not_touch_model_or_betting_logic():
    forbidden = (
        "backend/neuron.py",
        "backend/symphony2_engine.py",
        "backend/player_dna_",
        "backend/superbet_playable.py",
        "backend/ineed",
    )
    joined = "\n".join((MIGRATION, PUBLISHER, READER, WORKFLOW, HELPER))
    for item in forbidden:
        assert item not in joined
