from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    return (ROOT/p).read_text(encoding="utf-8")

def test_ui_audit_is_additive_and_keeps_protected_pins():
    h=read("frontend/index.html")
    assert "autolearn.css?v=84a1&hf=84a3" in h
    assert "symphony2.js?v=210" in h
    assert "scenario-studio-v82a.js" not in h
    assert "dynamic-weights.css?v=84d1" in h
    assert any(x in h for x in (
        "dynamic-weights.js?v=84d1",
        "dynamic-weights.js?v=84d2",
        "dynamic-weights.js?v=84e0",
    ))

def test_ui_audit_exposes_dynamic_and_global_modes():
    s=read("frontend/dynamic-weights.js")
    assert "dynamic_weighting" in s
    assert "local_weights" in s
    assert "DYNAMIC" in s
    assert "GLOBAL" in s
    assert "maxShift" in s

def test_ui_audit_is_mobile_responsive():
    c=read("frontend/dynamic-weights.css")
    assert "@media(max-width:520px)" in c
    assert "grid-template-columns:minmax(0,1fr)" in c
