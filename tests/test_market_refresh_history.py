import gzip
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_market_refresh_restores_history_before_consumers_and_packs_before_commit():
    workflow = (ROOT / ".github/workflows/superbet-market-refresh.yml").read_text()
    restore = workflow.index("python scripts/history_publication_chunks.py restore")
    consume = workflow.index("python backend/market_lab_v741.py")
    symphony = workflow.index("python backend/symphony2_engine.py")
    pack = workflow.index("python scripts/history_publication_chunks.py pack")
    publish = workflow.index("git add frontend/data")
    assert restore < consume < symphony < pack < publish


def test_ineed_restores_exact_history_before_settlement_consumers():
    workflow = (ROOT / ".github/workflows/ineed-shadow.yml").read_text()
    restore = workflow.index("python scripts/history_publication_chunks.py restore")
    settle = workflow.index("run: python backend/ineed_settlement_runner.py")
    sync = workflow.index("run: python backend/ineed_scoped_runner.py")
    assert restore < settle < sync


def test_market_refresh_uses_the_full_updates_read_only_pbp_cache():
    hourly = (ROOT / ".github/workflows/superbet-market-refresh.yml").read_text()
    full = (ROOT / ".github/workflows/update-and-pages.yml").read_text()
    save = next(step for step in full.split("\n      - ") if "uses: actions/cache/save@" in step)
    restore = next(step for step in hourly.split("\n      - ") if "uses: actions/cache/restore@" in step)
    prefix = "tennis-history-${{ runner.os }}-"
    assert "path: data/cache\n" in save and "path: data/cache\n" in restore
    assert "key: " + prefix in save
    assert prefix in restore.split("restore-keys: |\n")[1].splitlines()[0]
    assert "fail-on-cache-miss: true" in restore
    assert "actions/cache/save@" not in hourly
    check = hourly.index("python .github/scripts/superbet_refresh_guard.py check-pbp-cache")
    assert hourly.index(restore) < check < hourly.index("python backend/superbet_direct.py refresh-selected")
    assert check < hourly.index("python backend/symphony2_engine.py") < hourly.index("git add frontend/data")


def test_market_refresh_distinguishes_missing_pbp_storage_from_player_eligibility(tmp_path):
    command = [sys.executable, str(ROOT / ".github/scripts/superbet_refresh_guard.py"), "check-pbp-cache"]
    cache = tmp_path / "data/cache/pbp_v7"
    tapes = cache / "matches"
    tapes.mkdir(parents=True)
    index = cache / "players.json"

    def check():
        return subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)

    for content in (None, "{", "[]", '{"players": []}', '{"players": {}}'):
        if content is not None:
            index.write_text(content, encoding="utf-8")
        result = check()
        assert result.returncode != 0 and "players.json" in result.stderr

    # A partial player history can still be read. Fixture-level decisions belong to Symphony.
    index.write_text(json.dumps({"players": {"player": {"matches": [{"id": 1}]}}}), encoding="utf-8")
    result = check()
    assert result.returncode != 0 and "matches" in result.stderr
    with gzip.open(tapes / "1.json.gz", "wt", encoding="utf-8") as tape:
        json.dump({"match": {"id": 1}}, tape)
    assert check().returncode == 0
