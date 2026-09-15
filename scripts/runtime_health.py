#!/usr/bin/env python3
from pathlib import Path
import json
import os
import re
import subprocess
import sys

VERSION='v8.4E0'
WARN_MB=15
FAIL_MB=50

def read(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''

def _git_blob_size(root: Path, ref: str, name: str):
    if not ref or set(str(ref))=={'0'}:
        return None
    p=subprocess.run(
        ['git','cat-file','-s',f'{ref}:frontend/data/{name}'],
        cwd=root,capture_output=True,text=True,check=False,
    )
    if p.returncode!=0:
        return None
    try:
        return int(p.stdout.strip())
    except ValueError:
        return None

def ci_baseline_bytes(root: Path, name: str):
    """Return the exact payload baseline used by the CI comparison.

    Pull-request event metadata can keep an older ``base.sha`` after ``main`` moves,
    while GitHub rebuilds ``refs/pull/<n>/merge`` against the newer branch tip.
    The checked-out synthetic merge commit is authoritative: its first parent is
    the exact base commit used for the merge-ref under test. Fall back to the
    freshly fetched remote base branch, then event metadata. Push events retain
    the previous-commit comparison. Local runs stay strict by returning None.
    """
    event_path=os.getenv('GITHUB_EVENT_PATH')
    if not event_path:
        return None
    try:
        event=json.loads(Path(event_path).read_text(encoding='utf-8'))
        pr=event.get('pull_request') or {}
        if pr:
            parent=subprocess.run(
                ['git','rev-parse','HEAD^1'],cwd=root,capture_output=True,text=True,check=False,
            )
            if parent.returncode==0:
                size=_git_blob_size(root,parent.stdout.strip(),name)
                if size is not None:
                    return size
            base_ref=(pr.get('base') or {}).get('ref')
            if base_ref:
                size=_git_blob_size(root,f'refs/remotes/origin/{base_ref}',name)
                if size is not None:
                    return size
            return _git_blob_size(root,(pr.get('base') or {}).get('sha'),name)
        return _git_blob_size(root,event.get('before'),name)
    except Exception:
        return None

def audit(root: Path):
    frontend=root/'frontend'
    failures=[]
    warnings=[]
    metrics={}

    index=read(frontend/'index.html')
    runtime=read(frontend/'presentation-data.js')
    if 'presentation-data.js' not in index or 'const cache=new Map()' not in runtime:
        failures.append('Missing canonical cached presentation loader')
    if "cache:'no-store'" not in runtime:
        failures.append('Published data must be fetched fresh')

    for name in ['results.json','history.json']:
        path=frontend/'data'/name
        if not path.exists():
            continue
        size=path.stat().st_size
        mb=size/(1024*1024)
        metrics[name]=round(mb,2)
        baseline=ci_baseline_bytes(root,name)
        if baseline is not None:
            metrics[name+'_baseline_mb']=round(baseline/(1024*1024),2)
        if mb >= FAIL_MB:
            if baseline is not None and size<=baseline:
                warnings.append(f'{name} ma {mb:.1f} MB ponad limitem awaryjnym, ale ta zmiana nie zwiększa payloadu (baseline {baseline/(1024*1024):.1f} MB).')
            else:
                failures.append(f'{name} ma {mb:.1f} MB (limit awaryjny {FAIL_MB} MB).')
        elif mb >= WARN_MB:
            warnings.append(f'{name} ma {mb:.1f} MB — payload trzeba dalej odchudzać.')

    direct_results=[]
    service_worker_routes=[]
    global_observers=[]
    allowed_results={'app.js','presentation-data.js'}
    for path in frontend.glob('*.js'):
        txt=read(path)
        if 'data/results.json' in txt and 'fetch(' in txt:
            if path.name=='sw.js' and 'self.addEventListener' in txt and "'fetch'" in txt:
                service_worker_routes.append(path.name)
            else:
                direct_results.append(path.name)
                if path.name not in allowed_results:
                    warnings.append(f'Nowy bezpośredni czytelnik results.json: {path.name}')
        if re.search(r'observer\.observe\(document\.documentElement',txt):
            global_observers.append(path.name)

    metrics['direct_results_readers']=sorted(direct_results)
    metrics['service_worker_data_routes']=sorted(service_worker_routes)
    metrics['global_document_observers']=sorted(global_observers)

    for path in frontend.glob('*.js'):
        if path.name in {'app.js','runtime-fetch.js','data-runtime.js','sw.js'}:
            continue
        txt=read(path)
        if 'data/results.json' in txt and re.search(r'\bts\s*=',txt):
            failures.append(f'{path.name} może omijać shared runtime przez parametr ts=')

    if global_observers:
        warnings.append('Globalne MutationObserver nadal istnieją: '+', '.join(sorted(global_observers)))

    return failures,warnings,metrics

def main():
    root=Path.cwd()
    failures,warnings,metrics=audit(root)
    print(f'=== Tenis AI {VERSION} Runtime Health ===')
    for key,value in metrics.items():
        print(f'{key}: {value}')
    for warning in warnings:
        print('WARN:',warning)
    for failure in failures:
        print('FAIL:',failure)
    print(f'Summary: {len(failures)} FAIL / {len(warnings)} WARN')
    if failures:
        return 1
    print('Runtime health: PASS')
    return 0

if __name__=='__main__':
    sys.exit(main())
