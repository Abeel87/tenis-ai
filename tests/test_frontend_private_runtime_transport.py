from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSPORT = (ROOT / "frontend" / "runtime-data-transport.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
PRESENTATION = (ROOT / "frontend" / "presentation-data.js").read_text(encoding="utf-8")
SW = (ROOT / "frontend" / "sw.js").read_text(encoding="utf-8")


def test_private_runtime_transport_is_loaded_after_auth_and_before_app():
    assert "runtime-data-transport.js" in INDEX
    assert INDEX.index('src="account.js"') < INDEX.index('src="runtime-data-transport.js"')
    assert INDEX.index('src="runtime-data-transport.js"') < INDEX.index('src="app.js"')
    assert "'runtime-data-transport.js'" in SW


def test_default_mode_remains_public_until_real_auth_e2e_cutover():
    assert "window.TENIS_RUNTIME_DATA_MODE||'public'" in TRANSPORT
    assert "new Set(['public','dual','private'])" in TRANSPORT
    assert "mode==='public'" in TRANSPORT
    assert "return publicReader()" in TRANSPORT
    assert "TENIS_RUNTIME_ALLOW_PUBLIC_FALLBACK===false" in TRANSPORT


def test_private_transport_uses_real_supabase_session_and_reader():
    assert "window.TenisAccount" in TRANSPORT
    assert "account.client.auth.getSession()" in TRANSPORT
    assert "access_token" in TRANSPORT
    assert "/functions/v1/runtime-data-read" in TRANSPORT
    assert "'Authorization':`Bearer ${token}`" in TRANSPORT
    assert "'apikey':cfg.publishableKey" in TRANSPORT
    assert "metadata?.url" in TRANSPORT
    assert "fetch(metadata.url,{cache:'no-store'})" in TRANSPORT
    assert "user_metadata" not in TRANSPORT


def test_history_is_reconstructed_from_bounded_private_chunks():
    assert "const HISTORY_PATH='data/history.json'" in TRANSPORT
    assert "const HISTORY_MANIFEST='data/private/history/manifest.json'" in TRANSPORT
    assert "json-array-chunks-v1" in TRANSPORT
    assert "data/private/history/chunks/" in TRANSPORT
    assert "manifest.entry_count" in TRANSPORT
    assert "history_count_mismatch" in TRANSPORT


def test_dual_mode_is_shadow_only_and_telemetry_does_not_capture_tokens():
    dual = TRANSPORT.split("if(mode==='dual')", 1)[1].split("try{", 1)[0]
    assert "const result=await publicReader()" in dual
    assert "shadow(path,force)" in dual
    assert "return result" in dual
    record_fn = TRANSPORT.split("function record", 1)[1].split("function runtimeEligible", 1)[0]
    assert "token" not in record_fn.lower()
    assert "url" not in record_fn.lower()


def test_transport_wraps_only_the_central_presentation_json_reader():
    assert "window.TenisPresentation" in TRANSPORT
    assert "presentation.json=(path,force=false)=>read(" in TRANSPORT
    assert "__runtimeTransportWrapped" in TRANSPORT
    assert "async function json(path,force=false)" in PRESENTATION
    assert "frontend/app.js" not in TRANSPORT


def test_private_read_layer_cannot_change_model_or_betting_logic():
    forbidden = (
        "probability",
        "threshold",
        "player dna",
        "surface elo",
        "symphony2_engine",
        "superbet_playable",
        "ineed_system_place_bet",
        "settlement",
    )
    lowered = TRANSPORT.lower()
    for item in forbidden:
        assert item not in lowered
