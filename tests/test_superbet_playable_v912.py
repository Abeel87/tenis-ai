from __future__ import annotations

from pathlib import Path

from backend.signal_settlement import SIGNAL_LAYERS, settle_signal
from backend.superbet_playable_v912 import (
    inject_match,
    is_operator_playable_signal,
    project_match_for_display,
    signal_signature,
)


ROOT = Path(__file__).resolve().parents[1]


def _selection(market, pick, line=None, checkpoint=None, score=75.0):
    row = {
        "market": market,
        "pick": pick,
        "operator_available": True,
        "operator_line_verified": True,
    }
    if line is not None:
        row["line"] = line
    if checkpoint is not None:
        row["checkpoint"] = checkpoint
    model = {
        **row,
        "key": f"superbet|{market}|{checkpoint or ''}||{line if line is not None else ''}|{pick}",
        "label": f"{market} {pick} {line if line is not None else ''}".strip(),
        "score": score,
        "symphony_raw_probability": score,
        "operator_line_source": "oddspapi_superbet_pl",
    }
    return row, model


def _match():
    a20, m20 = _selection("match_total", "over", 20.5, score=73.0)
    u20, mu20 = _selection("match_total", "under", 20.5, score=27.0)
    sw1, msw1 = _selection("set1_winner", "Player A", score=69.0)
    sw2, msw2 = _selection("set1_winner", "Player B", score=31.0)
    st, mst = _selection("set1_total", "over", 8.5, score=82.0)
    return {
        "id": 1,
        "p1": "Player A",
        "p2": "Player B",
        "model_ready": True,
        "match_over_under": {
            "18.5": {"over": 91.0, "under": 9.0},
            "20.5": {"over": 73.0, "under": 27.0},
        },
        "over_under": {
            "7.5": {"over": 94.0, "under": 6.0},
            "8.5": {"over": 82.0, "under": 18.0},
        },
        "first_set_win": {"Player A": 69.0, "Player B": 31.0},
        "autolearn_v84": {
            "signals": [
                {"key": "match_total|18.5|over", "market": "match_total", "pick": "over", "line": 18.5, "current": 91.0, "ensemble": 88.0},
                {"key": "match_total|20.5|over", "market": "match_total", "pick": "over", "line": 20.5, "current": 73.0, "ensemble": 71.0},
            ],
            "by_key": {},
        },
        "serve_props_v72": {
            "ready": True,
            "p1": {"aces": {"mean": 4.2, "lines": {"1.5": {"over": 90, "under": 10}}}, "double_faults": {"mean": 2.2, "lines": {"0.5": {"over": 88, "under": 12}}}},
            "p2": {"aces": {"mean": 3.2, "lines": {"1.5": {"over": 80, "under": 20}}}, "double_faults": {"mean": 3.0, "lines": {"0.5": {"over": 85, "under": 15}}}},
        },
        "superbet_market_v91": {
            "status": "VERIFIED",
            "operator_verified": True,
            "canonical_selections": [a20, u20, sw1, sw2, st],
            "model_signals": [m20, mu20, msw1, msw2, mst],
        },
    }


def test_signature_ignores_irrelevant_line_for_game_state():
    a = {"market": "game_state", "pick": "2:2", "checkpoint": 4, "line": None}
    b = {"market": "game_state", "pick": "2-2", "checkpoint": 4, "line": 4}
    assert signal_signature(a) == signal_signature(b)


def test_inject_adds_real_operator_line_and_marks_raw_line_analysis_only():
    match, info = inject_match(_match())
    assert info["active"] is True
    signals = match["autolearn_v84"]["signals"]
    raw18 = next(x for x in signals if x.get("line") == 18.5)
    real20 = next(x for x in signals if x.get("line") == 20.5 and x.get("market") == "match_total")
    assert raw18["operator_playable"] is False
    assert real20["operator_playable"] is True
    assert is_operator_playable_signal(match, real20) is True
    # Real set-total selection was absent from AutoLearn raw candidates and is injected.
    assert any(x.get("market") == "set1_total" and x.get("line") == 8.5 for x in signals)


def test_normal_match_view_uses_only_real_superbet_lines():
    injected, _ = inject_match(_match())
    view, info = project_match_for_display(injected)
    assert info["active"] is True
    assert set(view["match_over_under"]) == {"20.5"}
    assert "18.5" not in view["match_over_under"]
    assert set(view["over_under"]) == {"8.5"}
    assert "7.5" not in view["over_under"]
    assert {x.get("line") for x in view["autolearn_v84"]["signals"] if x.get("market") == "match_total"} == {20.5}


def test_model_generated_individual_aces_and_df_are_hidden_from_playable_view():
    injected, _ = inject_match(_match())
    view, _ = project_match_for_display(injected)
    p1 = view["serve_props_v72"]["p1"]
    assert p1["aces"]["lines"] == {}
    assert "1.5" in p1["aces"]["analysis_lines"]
    assert p1["double_faults"]["lines"] == {}


def test_playable_history_layers_are_settled_and_total_sets_ou_is_supported():
    for name in (
        "playable_signals_v912", "playable_shadow_lab_v912",
        "playable_autolearn_signals_v912", "playable_shadow_models_v912",
    ):
        assert name in SIGNAL_LAYERS
    signal = {"market": "total_sets", "pick": "over", "line": 2.5}
    final = {"status": "completed", "number_of_sets": 3, "sets": [[6, 4], [4, 6], [6, 3]]}
    assert settle_signal(signal, final) == "hit"


def test_playable_stats_ui_is_explicit_when_operator_feed_is_unverified():
    js = (ROOT / "frontend/superbet-playable-v912.js").read_text(encoding="utf-8")
    assert "FEED N/D" in js
    assert "Brak zweryfikowanej oferty Superbet" in js
    assert "feedActive=verified>0" in js
    assert "nie są w tej chwili potwierdzone jako grywalne" in js
