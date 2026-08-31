from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_fast_boot_starts_results_before_history_and_canonicalizes_timestamp():
    s = read("frontend/app-meta.js")
    assert "TENIS_AI_FAST_BOOT_V888" in s
    assert "earlyResults" in s
    assert "data/results.json" in s
    assert "searchParams.delete('ts')" in s
    assert "Ładowanie meczów" in s


def test_match_loading_guard_prevents_false_empty_state_and_primes_results():
    s = read("frontend/loading-fix-v889.js")
    index = read("frontend/index.html")
    assert "TENIS_AI_MATCH_LOADING_V889" in s
    assert "state = 'loading'" in s
    assert "data/results.json" in s
    assert "Ładowanie meczów" in s
    assert "originalRenderMatches" in s
    assert "loading-fix-v889.js?v=889" in index


def test_player_intelligence_has_plain_language_layer_and_keeps_shadow_semantics():
    s = read("frontend/player-intelligence-v888-human.js")
    assert "PLAYER INTELLIGENCE · PO LUDZKU" in s
    assert "Mecz praktycznie równy" in s
    assert "Zaawansowane dane" in s
    assert "SHADOW" in s


def test_retired_generator_is_not_bootstrapped_anymore():
    index = read("frontend/index.html")
    meta = read("frontend/app-meta.js")
    for retired in (
        "generator-quality-v888.js",
        "scenario-studio-v82a.js",
        "scenario-runtime-v202.js",
        "scenario-dynamic-v84d3.js",
        "scenario-settlement-v83c.js",
    ):
        assert retired not in index
        assert retired not in meta


def test_symphony2_is_loaded_from_central_app_bootstrap():
    index = read("frontend/index.html")
    meta = read("frontend/app-meta.js")
    assert "symphony2.js?v=210" in index
    assert "symphony2.css?v=210" in index
    assert "symphony2-live-ui-v201.js?v=201" in meta
    assert "symphonyVersion:'v2.1'" in meta
