from pathlib import Path
import re


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


def test_retry_selects_only_its_own_pages_artifact():
    workflow = read('.github/workflows/deploy-pages-fast.yml')

    def action_input(action, key):
        # Inspect this workflow's block-style steps, not arbitrary YAML. Scope the
        # input to its action so an unrelated name cannot satisfy the regression.
        steps = re.split(r'(?m)^      - ', workflow)[1:]
        matching = [step for step in steps
                    if re.search(rf'(?m)^        uses: {re.escape(action)}$', step)]
        assert len(matching) == 1, f'Expected one {action} step'
        value = re.search(rf'(?m)^        with:\n(?:          [^\n]*\n)*?'
                          rf'          {re.escape(key)}: ([^\n]+)', matching[0])
        assert value, f'Missing {key} input for {action}'
        return value.group(1).strip().strip('\"\'')

    upload_name = action_input('actions/upload-pages-artifact@v4', 'name')
    deploy_name = action_input('actions/deploy-pages@v4', 'artifact_name')

    def resolve(value, attempt):
        return value.replace('${{ github.run_id }}', '12345').replace('${{ github.run_attempt }}', str(attempt))

    artifacts = []
    for attempt in (1, 2):
        artifact = resolve(upload_name, attempt)
        artifacts.append(artifact)
        assert artifacts.count(resolve(deploy_name, attempt)) == 1
    assert len(set(artifacts)) == 2  # the original retry failed on duplicate github-pages names
    push_block = workflow.split('  push:', 1)[1].split('\npermissions:', 1)[0]
    assert "      - '.github/workflows/deploy-pages-fast.yml'" in push_block
