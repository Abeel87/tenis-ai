from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    return (ROOT/p).read_text(encoding="utf-8")

def test_ui_audit_is_additive_and_keeps_protected_pins():
    h=read("frontend/index.html")
    assert 'href="style.css"' in h
    assert "autolearn-v84.css" not in h
    assert 'src="symphony2.js"' in h
    assert "scenario-studio-v82a.js" not in h
    assert "dynamic-weights-v84d1.css" not in h
    assert any(x in h for x in (
        "dynamic-weights-v84d1.js?v=84d1",
        "dynamic-weights-v84d1.js?v=84d2",
        "dynamic-weights-v84d1.js?v=84e0",
    ))

def test_ui_audit_exposes_dynamic_and_global_modes():
    s=read("frontend/dynamic-weights-v84d1.js")
    assert "dynamic_weighting" in s
    assert "local_weights" in s
    assert "DYNAMIC" in s
    assert "GLOBAL" in s
    assert "maxShift" in s

def test_ui_audit_is_mobile_responsive():
    c=read("frontend/style.css")
    assert "@media(max-width:760px)" in c
    assert ".match-grid" in c
