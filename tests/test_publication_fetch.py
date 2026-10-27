"""Exercise the real publisher fetch commands against a local Git remote."""
from pathlib import Path
import shlex
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def git(cwd, *args):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


@pytest.mark.parametrize('workflow,step_name', [
    ('update-and-pages.yml', 'Commit refreshed JSON'),
    ('superbet-market-refresh.yml', 'Commit refreshed market context'),
    ('player-dna-shadow-refresh.yml', 'Publish Player DNA SHADOW reports'),
])
def test_publication_fetch_excludes_other_branches_and_preserves_main(tmp_path, workflow, step_name):
    remote = tmp_path / 'remote.git'
    git(tmp_path, 'init', '--bare', '--initial-branch=main', str(remote))
    source = tmp_path / 'source'
    git(tmp_path, 'clone', str(remote), str(source))
    git(source, 'config', 'user.name', 'test')
    git(source, 'config', 'user.email', 'test@example.invalid')
    (source / 'base').write_text('base')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'base')
    git(source, 'push', 'origin', 'main')
    worker = tmp_path / 'worker'
    # Actions checks out shallow history but can retain an all-branches fetch
    # refspec. Use file:// so Git really honors depth for this local fixture.
    git(tmp_path, 'clone', '--depth=1', '--no-single-branch', remote.as_uri(), str(worker))
    git(worker, 'config', 'user.name', 'test')
    git(worker, 'config', 'user.email', 'test@example.invalid')
    # An unrelated stale branch/tag must not be downloaded by publication.
    git(source, 'checkout', '-b', 'unrelated-archive')
    (source / 'unrelated').write_text('old unrelated archive')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'unrelated')
    unrelated = git(source, 'rev-parse', 'HEAD')
    git(source, 'tag', 'unrelated-tag')
    git(source, 'push', 'origin', 'unrelated-archive', '--tags')
    git(source, 'checkout', 'main')
    (source / 'parallel-report').write_text('keep concurrent publication')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'concurrent main')
    latest = git(source, 'rev-parse', 'HEAD')
    git(source, 'push', 'origin', 'main')
    (worker / 'generated-report').write_text('keep this publication')
    git(worker, 'add', '.')
    git(worker, 'commit', '-m', 'generated')
    doc = (ROOT / '.github/workflows' / workflow).read_text()
    step = doc.split('- name: ' + step_name, 1)[1].split('\n      - ', 1)[0]
    command = next(line.strip() for line in step.splitlines()
                   if line.strip().startswith('git fetch '))
    subprocess.run(shlex.split(command), cwd=worker, check=True)
    assert git(worker, 'rev-parse', 'origin/main') == latest
    assert 'unrelated-archive' not in git(worker, 'branch', '-r')
    assert not git(worker, 'tag')
    assert subprocess.run(['git', 'cat-file', '-e', unrelated], cwd=worker).returncode != 0
    git(worker, 'rebase', 'origin/main')
    git(worker, 'push', 'origin', 'HEAD:main')
    assert git(remote, 'show', 'main:parallel-report') == 'keep concurrent publication'
    assert git(remote, 'show', 'main:generated-report') == 'keep this publication'
