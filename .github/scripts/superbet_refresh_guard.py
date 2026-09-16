"""Read-only Actions orchestration guard; never imports tennis runtime code."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ACTIVE = {'queued', 'in_progress', 'waiting', 'requested', 'pending'}
STALE_MINUTES = 55
FULL_GRACE_MINUTES = 5
REFRESH = 'superbet-market-refresh.yml'
FULL = 'update-and-pages.yml'
WORK_STEP = 'Refresh real Superbet catalogue + map audited families'
PUBLISH_STEP = 'Commit refreshed market context'


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None


def main_runs(rows):
    return [r for r in rows if r.get('head_branch') == 'main'
            and r.get('event') != 'pull_request']


def watchdog_block(refreshes, fulls, now):
    if any(r.get('status') in ACTIVE for r in main_runs(refreshes)):
        return 'refresh_already_active'
    if any(r.get('status') in ACTIVE for r in main_runs(fulls)):
        return 'full_already_active'
    for r in main_runs(fulls):
        finished = timestamp(r.get('updated_at'))
        if (r.get('conclusion') == 'success' and finished
                and 0 <= (now - finished).total_seconds() < FULL_GRACE_MINUTES * 60):
            return 'successful_full_propagation_grace'
    return None


def completed_refresh(run, jobs, now, after=None):
    """A successful NO-OP is not evidence of newly refreshed data."""
    finished = timestamp(run.get('updated_at'))
    if (not main_runs([run]) or run.get('status') != 'completed'
            or run.get('conclusion') != 'success' or not finished
            or not 0 <= (now - finished).total_seconds() < STALE_MINUTES * 60):
        return False
    for job in jobs:
        steps = {s['name']: s for s in job.get('steps', [])}
        work, publish = steps.get(WORK_STEP, {}), steps.get(PUBLISH_STEP, {})
        started = timestamp(work.get('started_at'))
        if (job.get('conclusion') == 'success' and work.get('conclusion') == 'success'
                and publish.get('conclusion') == 'success' and started
                and (after is None or started >= after)):
            return True
    return False


def api(path):
    # gh supplies authentication; errors stop the guard before dispatch/API work.
    return json.loads(subprocess.check_output(
        ['gh', 'api', f'/repos/{os.environ["GITHUB_REPOSITORY"]}/{path}'], text=True))


def runs(workflow):
    # Query active and successful separately so failed/NO-OP bursts cannot hide
    # active runs behind the first page. Paginate successful runs to the horizon.
    rows = []
    for state in (*sorted(ACTIVE), 'success'):
        for page in range(1, 11):
            batch = api(f'actions/workflows/{workflow}/runs?branch=main&status={state}&per_page=100&page={page}')['workflow_runs']
            rows.extend(batch)
            if len(batch) < 100:
                break
            if state == 'success' and all(
                timestamp(r.get('updated_at')) and
                (datetime.now(timezone.utc) - timestamp(r['updated_at'])).total_seconds() >= STALE_MINUTES * 60
                for r in batch
            ):
                break
        else:
            raise RuntimeError('Actions history exceeds guard pagination limit')
    return rows


def main():
    mode = sys.argv[1]
    now = datetime.now(timezone.utc)
    event_name = os.environ['GITHUB_EVENT_NAME']
    reason, after = None, None
    if mode == 'refresh' and event_name == 'pull_request':
        # Preserve the existing PR validation path; never use PRs as freshness evidence.
        pass
    else:
        refreshes = runs(REFRESH)
        if mode == 'watchdog':
            reason = watchdog_block(refreshes, runs(FULL), now)
        elif event_name == 'workflow_run':
            source = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())['workflow_run']
            if source.get('head_branch') != 'main' or source.get('conclusion') != 'success':
                reason = 'ineligible_full_source'
            else:
                after = timestamp(source['updated_at'])
        if not reason:
            for run in main_runs(refreshes):
                if str(run['id']) == os.environ.get('GITHUB_RUN_ID'):
                    continue
                finished = timestamp(run.get('updated_at'))
                if not finished or not 0 <= (now - finished).total_seconds() < STALE_MINUTES * 60:
                    continue
                jobs = api(f'actions/runs/{run["id"]}/jobs?filter=latest&per_page=100')['jobs']
                if completed_refresh(run, jobs, now, after):
                    reason = f'fresh_completed_refresh_{run["id"]}'
                    break
    proceed = reason is None
    reason = reason or 'stale_refresh_required'
    key = 'dispatch' if mode == 'watchdog' else 'refresh'
    result = f'{key}={str(proceed).lower()}\nreason={reason}\n'
    print(result)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(result)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
        output.write(f'### Superbet orchestration guard\n\n{result}\n')


if __name__ == '__main__':
    main()
