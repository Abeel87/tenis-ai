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


@pytest.mark.parametrize('workflow', [
    'ui-smoke.yml', 'update-and-pages.yml',
    'superbet-market-refresh.yml', 'player-dna-shadow-refresh.yml',
])
def test_full_history_checkout_defers_old_blobs_but_keeps_history(tmp_path, workflow):
    remote = tmp_path / 'remote.git'
    git(tmp_path, 'init', '--bare', '--initial-branch=main', str(remote))
    git(remote, 'config', 'uploadpack.allowFilter', 'true')
    source = tmp_path / 'source'
    git(tmp_path, 'clone', str(remote), str(source))
    git(source, 'config', 'user.name', 'test')
    git(source, 'config', 'user.email', 'test@example.invalid')
    (source / 'report.json').write_text('{"generation":"previous"}')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'previous generation')
    previous = git(source, 'rev-parse', 'HEAD')
    old_blob = git(source, 'rev-parse', 'HEAD:report.json')
    (source / 'report.json').write_text('{"generation":"current"}')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'current generation')
    git(source, 'push', 'origin', 'main')
    # Exercise the configured filter. Before the repair this downloads old_blob.
    doc = (ROOT / '.github/workflows' / workflow).read_text()
    checkout = doc.split('uses: actions/checkout@v6', 1)[1].split('\n      -', 1)[0]
    assert 'fetch-depth: 0' in checkout, 'Full commit history must remain available'
    filters = [line.strip().split(':', 1)[1].strip() for line in checkout.splitlines()
               if line.strip().startswith('filter:')]
    worker = tmp_path / 'worker'
    git(tmp_path, 'clone', '--no-checkout', *['--filter='+f for f in filters],
        remote.as_uri(), str(worker))
    git(worker, 'checkout', 'main')
    assert (worker / 'report.json').read_text() == '{"generation":"current"}'
    assert git(worker, 'merge-base', previous, 'HEAD') == previous
    assert git(worker, 'diff', '--name-only', previous, 'HEAD') == 'report.json'
    missing = git(worker, 'rev-list', '--objects', '--missing=print', 'HEAD')
    assert '?' + old_blob in missing, 'Checkout must not download obsolete report bytes'
    # Historical content remains readable on demand (runtime provenance checks).
    assert git(worker, 'show', previous+':report.json') == '{"generation":"previous"}'
