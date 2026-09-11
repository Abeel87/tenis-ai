"""Classify source changes without starting data generation for UI-only work."""
import os
import subprocess

before = os.environ.get('BEFORE', '')
head = os.environ.get('HEAD_SHA', 'HEAD')
args = ['git', 'diff', '--name-only', before, head] if before and set(before) != {'0'} else ['git', 'show', '--pretty=', '--name-only', head]
paths = subprocess.check_output(args, text=True).splitlines()

def affects_data(path):
    # The main data workflow is itself part of the data-generation contract.
    # A quota/backfill change there must run the full build immediately.
    if path == '.github/workflows/update-and-pages.yml':
        return True
    if path.startswith(('backend/', 'data/', 'frontend/data/')) or path == 'requirements.txt':
        return True
    if path.startswith('tests/') and path.endswith('.py'):
        return True
    return path.startswith('scripts/') and not (path.startswith('scripts/verify_') or path in {'scripts/project_health.py', 'scripts/runtime_health.py'})

heavy = any(affects_data(path) for path in paths)
with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
    output.write(f'heavy={str(heavy).lower()}\n')
    output.write(f'deploy={str(not heavy).lower()}\n')
print(f'Data/model changes: {heavy}; changed paths: {len(paths)}')
