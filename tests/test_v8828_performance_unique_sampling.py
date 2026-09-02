from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_performance_center_uses_unique_report_sampling():
    js = (ROOT / "frontend/performance-center.js").read_text(encoding="utf-8")
    backend = (ROOT / "backend/history_sampling.py").read_text(encoding="utf-8")

    assert "function reportSignals(m)" in js
    assert "for(const s of reportSignals(m))" in js
    assert "for(const s of (m.signals||[]))" not in js
    assert "line===10.5||line===11.5" in js
    assert ".replace('11.5','10.5')" in js
    assert "line not in (10.5, 11.5)" in backend
    assert '.replace("11.5", "10.5")' in backend
    assert "raw?.source_model??null" in js
    assert "raw?.tracker_version??null" in js
    assert 'signal.get("source_model")' in backend
    assert 'signal.get("tracker_version")' in backend
