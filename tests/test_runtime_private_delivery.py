import hashlib
import importlib.util
import json
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
HELPER_PATH = ROOT / "scripts" / "publish_runtime_private.py"
HELPER = HELPER_PATH.read_text(encoding="utf-8")


def _load_helper():
    spec = importlib.util.spec_from_file_location("runtime_private_helper_test", HELPER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


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
    assert '"data/private/history/manifest.json"' in HELPER
    assert '"data/private/history/chunks/*.json"' in HELPER
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" in HELPER
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" in HELPER


def test_layer_scoping_and_history_chunking_are_bounded(tmp_path, monkeypatch):
    helper = _load_helper()
    frontend = tmp_path / "frontend"
    data = frontend / "data"

    history = [
        {"match_id": i, "p1": f"A{i}", "p2": f"B{i}", "payload": "x" * 220}
        for i in range(30)
    ]
    _write_json(data / "history.json", history)
    _write_json(data / "misc_admin.json", {"admin": True})
    _write_json(data / "delivery" / "index.json", {"matches": []})
    _write_json(data / "neuron_current.json", {"current": True})
    _write_json(data / "neuron_metrics.json", {"metrics": True})
    _write_json(data / "neuron_model.json", {"model": True})
    _write_json(data / "player_dna_current_simulation.json", {"dna": True})
    _write_json(data / "results.json", [{"id": 1}])
    _write_json(data / "meta.json", {"updated_at": "2026-09-16T00:00:00Z"})
    _write_json(data / "superbet_direct_current.json", {"operator": "superbet.pl"})

    helper.FRONTEND = frontend
    helper.DATA = data
    helper.HISTORY_CHUNK_TARGET = 1024
    helper.MAX_OBJECT_SIZE = 8192
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))

    rows_by_layer = {}
    maps_by_layer = {}
    for layer in ("core", "market", "dna", "neuron"):
        rows_by_layer[layer], maps_by_layer[layer] = helper.snapshot_files(layer)

    paths = {
        layer: {row["path"] for row in rows}
        for layer, rows in rows_by_layer.items()
    }

    assert paths["neuron"] == {
        "data/neuron_current.json",
        "data/neuron_metrics.json",
        "data/neuron_model.json",
    }
    assert paths["dna"] == {"data/player_dna_current_simulation.json"}
    assert paths["market"] == {
        "data/results.json",
        "data/meta.json",
        "data/superbet_direct_current.json",
    }
    assert "data/history.json" not in paths["core"]
    assert "data/private/history/manifest.json" in paths["core"]
    assert any(p.startswith("data/private/history/chunks/") for p in paths["core"])
    assert "data/misc_admin.json" in paths["core"]
    assert "data/delivery/index.json" in paths["core"]

    all_paths = [path for layer_paths in paths.values() for path in layer_paths]
    assert len(all_paths) == len(set(all_paths))
    assert all(
        row["size_bytes"] <= helper.MAX_OBJECT_SIZE
        for rows in rows_by_layer.values()
        for row in rows
    )

    manifest_row = next(
        row
        for row in rows_by_layer["core"]
        if row["path"] == "data/private/history/manifest.json"
    )
    manifest_path = maps_by_layer["core"][manifest_row["sha256"]]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_path"] == "data/history.json"
    assert manifest["source_sha256"] == hashlib.sha256(
        (data / "history.json").read_bytes()
    ).hexdigest()
    assert manifest["entry_count"] == len(history)
    assert len(manifest["chunks"]) >= 2
    assert all(chunk["size_bytes"] <= helper.MAX_OBJECT_SIZE for chunk in manifest["chunks"])

    for row in rows_by_layer["core"]:
        if row["path"] == "data/private/history/manifest.json" or row["path"].startswith(
            "data/private/history/chunks/"
        ):
            assert row["tier"] == "b"


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
