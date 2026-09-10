"""Classify source changes without starting data generation for UI-only work."""
import os
import subprocess

before = os.environ.get('BEFORE', '')
head = os.environ.get('HEAD_SHA', 'HEAD')
args = ['git', 'diff', '--name-only', before, head] if before and set(before) != {'0'} else ['git', 'show', '--pretty=', '--name-only', head]
paths = subprocess.check_output(args, text=True).splitlines()

def affects_data(path):
    if path.startswith(('backend/', 'data/', 'frontend/data/')) or path == 'requirements.txt':
        return True
    return path.startswith('scripts/') and not (path.startswith('scripts/verify_') or path in {'scripts/project_health.py', 'scripts/runtime_health.py'})

heavy = any(affects_data(path) for path in paths)
with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
    output.write(f'heavy={str(heavy).lower()}\n')
    output.write(f'deploy={str(not heavy).lower()}\n')
print(f'Data/model changes: {heavy}; changed paths: {len(paths)}')
