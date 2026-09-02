#!/usr/bin/env python3
from pathlib import Path
import re
import sys

VERSION='v8.4E0'
WARN_MB=15
FAIL_MB=50

def read(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''

def audit(root: Path):
    frontend=root/'frontend'
    failures=[]
    warnings=[]
    metrics={}

    index=read(frontend/'index.html')
    runtime=read(frontend/'runtime-health.js')
    dynamic=read(frontend/'dynamic-weights-v84d1.js')

    app_pos=index.find('app.js')
    runtime_pos=index.find('runtime-health.js')
    dynamic_pos=index.find('dynamic-weights-v84d1.js')
    scenario_pos=index.find('scenario-dynamic-v84d3.js')

    if runtime_pos < 0:
        failures.append('index.html nie ładuje runtime-health.js')
    if app_pos >= 0 and runtime_pos >= 0 and dynamic_pos >= 0 and not (app_pos < runtime_pos < dynamic_pos):
        failures.append('Runtime Health musi być po app.js i przed Dynamic Weights.')
    if scenario_pos >= 0 and not (runtime_pos < scenario_pos):
        failures.append('Runtime Health musi być przed opcjonalnym Scenario runtime.')

    required_runtime=[
        ("const VERSION='v8.4E0'" in runtime,'Brak markera wersji v8.4E0.'),
        ('window.TENIS_AI_DATA' in runtime,'Brak wspólnego API TENIS_AI_DATA.'),
        ('window.fetch=function' in runtime,'Brak deduplikacji ciężkich fetchy.'),
        ("url.searchParams.has('ts')" in runtime,'Brak bypassu dla autorytatywnego odświeżania app.js.'),
        ("/data/results.json" in runtime,'Brak współdzielenia results.json.'),
        ("/data/history.json" in runtime,'Brak współdzielenia history.json.'),
    ]
    for ok,msg in required_runtime:
        if not ok:
            failures.append(msg)

    if 'setInterval(()=>schedule(0),60000)' in dynamic:
        failures.append('Dynamic Weights nadal skanuje całą pulę automatycznie co 60 s.')

    for name in ['results.json','history.json']:
        path=frontend/'data'/name
        if not path.exists():
            continue
        mb=path.stat().st_size/(1024*1024)
        metrics[name]=round(mb,2)
        if mb >= FAIL_MB:
            failures.append(f'{name} ma {mb:.1f} MB (limit awaryjny {FAIL_MB} MB).')
        elif mb >= WARN_MB:
            warnings.append(f'{name} ma {mb:.1f} MB — payload trzeba dalej odchudzać.')

    direct_results=[]
    service_worker_routes=[]
    global_observers=[]
    allowed_results={'app.js','dynamic-weights-v84d1.js','scenario-dynamic-v84d3.js','runtime-health.js'}
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
        if path.name in {'app.js','runtime-health.js','sw.js'}:
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
