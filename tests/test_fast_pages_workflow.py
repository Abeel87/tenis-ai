from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_full_workflow_no_longer_runs_for_plain_frontend_changes():
    workflow = read(".github/workflows/update-and-pages.yml")
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "- 'backend/**'" in workflow
    assert "- 'scripts/**'" in workflow
    assert "- 'frontend/data/**'" in workflow
    push_block = workflow.split("push:", 1)[1].split("permissions:", 1)[0]
    assert "frontend/**" not in push_block.replace("frontend/data/**", "")


def test_long_data_build_has_its_own_concurrency_lane():
    workflow = read(".github/workflows/update-and-pages.yml")
    assert "group: tennis-data-build" in workflow
    assert "group: pages\n" not in workflow
    assert "superbet_market_context_v913.py prepare" in workflow
    assert "superbet_market_context_v913.py finalize" in workflow


def test_fast_workflow_deploys_frontend_only_and_is_not_blocked_by_data_build():
    workflow = read(".github/workflows/deploy-pages-fast.yml")
    assert "name: Fast frontend deploy" in workflow
    assert "- 'frontend/**'" in workflow
    assert "group: pages" in workflow
    assert "tennis-data-build" not in workflow
    assert "cancel-in-progress: false" in workflow
    assert "Fast frontend checks" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "backend/|scripts/|data/|frontend/data/|requirements" in workflow
    assert "FULL workflow owns this deploy" in workflow
