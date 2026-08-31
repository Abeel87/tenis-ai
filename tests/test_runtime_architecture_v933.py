from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_stale_raw_playable_v921_is_removed():
    assert not (FRONTEND / "raw-playable-separation-v921.js").exists()
    assert not (FRONTEND / "data" / "symphony_match_cards_v90.json").exists()


def test_current_runtime_uses_symphony2_and_exact_superbet_layer_only():
    files = [
        FRONTEND / "index.html",
        FRONTEND / "app-meta.js",
        FRONTEND / "match-list-visibility-v916.js",
        FRONTEND / "superbet-model-coverage-v922.js",
        FRONTEND / "market-segregation-v93g.js",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    index = files[0].read_text(encoding="utf-8")
    meta = files[1].read_text(encoding="utf-8")
    loader = files[2].read_text(encoding="utf-8")

    assert "raw-playable-separation-v921" not in text
    assert "symphony_match_cards_v90" not in text
    assert "loadRawPlayableV921" not in loader
    assert "symphony2.js?v=210" in index
    assert "symphony2-live-ui-v201.js?v=201" in meta
    assert "playable-ui-coherence-v917.js?v=925" in meta
    assert "playable-line-freshness-v925.js?v=925" in meta
    assert "loadSuperbetModelCoverageV922" in loader
    assert "loadMarketSegregationV93G" in loader
