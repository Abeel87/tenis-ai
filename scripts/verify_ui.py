"""Quick presentation checks; never generate or modify published data."""
from pathlib import Path
import subprocess

def main():
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(['node', 'tests/ui_static_smoke.mjs'], cwd=root).returncode

if __name__ == '__main__':
    raise SystemExit(main())
