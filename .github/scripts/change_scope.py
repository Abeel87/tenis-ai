"""Classify source changes without starting data generation for UI-only work."""
import os
import subprocess

before = os.environ.get('BEFORE', '')
head = os.environ.get('HEAD_SHA', 'HEAD')
base_ref = os.environ.get('GITHUB_BASE_REF', '')
if base_ref:
    # Pull-request base.sha can lag behind a moving main while Actions checks out
    # the synthetic merge commit. Diff against the fetched current base branch so
    # unrelated bot data refreshes on main do not turn a UI-only PR into a heavy run.
    current_base = f'origin/{base_ref}'
    try:
        subprocess.check_call(['git', 'rev-parse', '--verify', current_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        before = current_base
    except subprocess.CalledProcessError:
        pass
args = ['git', 'diff', '--name-only', before, head] if before and set(before) != {'0'} else ['git', 'show', '--pretty=', '--name-only', head]
paths = subprocess.check_output(args, text=True).splitlines()

def affects_data(path):
    # iNeed$ is a post-PLAYABLE SHADOW/risk layer with its own dedicated
    # workflow and tests. Changes there must not be classified as core
    # data/model generation, otherwise unrelated publication-size gates can
    # turn a healthy iNeed$ fix red.
    if path.startswith('backend/ineed_') and path.endswith('.py'):
        return False
    if path.startswith('tests/test_ineed_') and path.endswith('.py'):
        return False

    # The main data workflow is itself part of the data-generation contract.
    # A quota/backfill change there must run the full build immediately.
    if path == '.github/workflows/update-and-pages.yml':
        return True
    # Runtime Health changes must execute the full health pipeline; otherwise
    # the check being edited could be skipped by the scope classifier itself.
    if path == 'scripts/runtime_health.py':
        return True
    if path.startswith(('backend/', 'data/', 'frontend/data/')) or path in {'requirements.txt','requirements.lock'}:
        return True
    if path.startswith('tests/') and path.endswith('.py'):
        return True
    return path.startswith('scripts/') and not (path.startswith('scripts/verify_') or path == 'scripts/project_health.py')

heavy = any(affects_data(path) for path in paths)
with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
    output.write(f'heavy={str(heavy).lower()}\n')
    output.write(f'deploy={str(not heavy).lower()}\n')
print(f'Data/model changes: {heavy}; changed paths: {len(paths)}')
