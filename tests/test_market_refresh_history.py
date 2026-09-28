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
