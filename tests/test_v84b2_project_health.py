from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_project_health_accepts_v84b_cache_family_with_legacy_marker():
    health = read("scripts/project_health.py")
    sw = read("frontend/sw.js")
    assert "cache_v84b" in health
    assert "legacy_v801_marker" in health
    assert "tenis-ai-v84b-logic-stability" in sw
    assert "tenis-ai-v801-player-profile" in sw

def test_project_health_script_passes_on_current_repo():
    p = subprocess.run(
        [sys.executable, "scripts/project_health.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert p.returncode == 0, p.stdout + "\n" + p.stderr
