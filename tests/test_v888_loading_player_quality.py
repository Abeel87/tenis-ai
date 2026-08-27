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


def test_player_intelligence_has_plain_language_layer_and_keeps_shadow_semantics():
    s = read("frontend/player-intelligence-v888-human.js")
    assert "PLAYER INTELLIGENCE · PO LUDZKU" in s
    assert "Mecz praktycznie równy" in s
    assert "Zaawansowane dane" in s
    assert "SHADOW" in s
    assert "nie zmienia końcowego sygnału ani generatora" in s


def test_generator_quality_lock_drops_weak_pairs_instead_of_padding_count():
    s = read("frontend/generator-quality-v888.js")
    assert "Quality Lock" in s
    assert "minItem:78" in s
    assert "minAvg:80" in s
    assert "Nie dokładam słabszych" in s
    assert "match_total" in s
    assert "accuracy_lab_v86.json" in s


def test_hotfix_addons_are_loaded_from_central_metadata_bootstrap():
    s = read("frontend/app-meta.js")
    assert "player-intelligence-v888-human.js?v=888" in s
    assert "generator-quality-v888.js?v=888" in s
