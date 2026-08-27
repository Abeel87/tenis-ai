from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pair_preserve_fast_path_is_two_signal_only():
    s = (ROOT / "frontend/scenario-studio-v82a.js").read_text(encoding="utf-8")
    start = s.index("function repairGeneratorCandidate")
    end = s.index("function draftMatches", start)
    block = s[start:end]

    # A pair score is a complete score only for exactly two selected events.
    # For 3/4 events the candidate must continue through the full per-signal
    # floor and whole-set average validation below.
    assert "spm===2 &&" in block
    assert "if(sc<policy.floor)return false;" in block
    assert "if(avg<policy.minAverage)return" in block
    assert "pair_preserved:true" in block
