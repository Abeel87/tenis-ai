from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def test_current_engine_uses_one_canonical_model_core_path():
    assert (BACKEND / "model_core.py").is_file()
    assert not (BACKEND / "model_core_v945.py").exists()
    facade = (BACKEND / "model.py").read_text(encoding="utf-8")
    assert "from . import model_core as _core" in facade
    assert "import model_core as _core" in facade
    assert "model_core_v945" not in facade


def test_symphony_state_uses_one_canonical_core_path():
    assert (BACKEND / "symphony2_state_core.py").is_file()
    assert not (BACKEND / "symphony2_state_core_v945.py").exists()
    facade = (BACKEND / "symphony2_state.py").read_text(encoding="utf-8")
    assert "from . import symphony2_state_core as _core" in facade
    assert "import symphony2_state_core as _core" in facade
    assert "symphony2_state_core_v945" not in facade
