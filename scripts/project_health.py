#!/usr/bin/env python3
from pathlib import Path
import base64
import json
import re
import sys

ROOT=Path.cwd()
frontend=ROOT/'frontend'
workflows=ROOT/'.github'/'workflows'
warnings=[]
failures=[]

def read(path):
    try:return path.read_text(encoding='utf-8',errors='replace')
    except Exception:return ''

if not frontend.exists():failures.append('Brak katalogu frontend/')
js_files=list(frontend.glob('*.js')) if frontend.exists() else []
css_files=list(frontend.glob('*.css')) if frontend.exists() else []
if len(js_files)>20:warnings.append(f'Frontend ma {len(js_files)} osobnych plików JS — aktywne mosty legacy warto dalej scalać w v8.x.')
if len(css_files)>20:warnings.append(f'Frontend ma {len(css_files)} osobnych plików CSS — aktywne style legacy warto dalej scalać w v8.x.')

def b64url_decode(s):
    s += '=' * (-len(s)%4)
    return base64.urlsafe_b64decode(s.encode()).decode('utf-8',errors='ignore')

def jwt_is_service_role(token):
    parts=token.split('.')
    if len(parts)!=3:return False
    try:return json.loads(b64url_decode(parts[1])).get('role')=='service_role'
    except Exception:return False

assignment_rx=re.compile(r'(?:SUPABASE_SERVICE_ROLE_KEY|SERVICE_ROLE_KEY)\s*[:=]\s*[\"\']([^\"\']{20,})[\"\']',re.I)
secret_key_rx=re.compile(r'\bsb_secret_[A-Za-z0-9_-]{20,}\b')
jwt_rx=re.compile(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b')

if frontend.exists():
    for p in frontend.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in {'.js','.html','.json','.css'}:continue
        txt=read(p)
        if secret_key_rx.search(txt):failures.append(f'Rzeczywisty Supabase secret key w frontendzie: {p}')
        if assignment_rx.search(txt):failures.append(f'Service-role key przypisany w frontendzie: {p}')
        for token in jwt_rx.findall(txt):
            if jwt_is_service_role(token):
                failures.append(f'JWT z role=service_role w frontendzie: {p}')
                break

index=read(frontend/'index.html')
meta=read(frontend/'app-meta.js')
ui=read(frontend/'ui-v751.js')
clean=read(frontend/'clean-core-v80.js')
sw=read(frontend/'sw.js')

required=[
    ('clean-core-v80.css?v=801' in index,'Brak Clean Core CSS v8.0.1 w index.html.'),
    ('clean-core-v80.js?v=801' in index,'Brak Clean Core JS v8.0.1 w index.html.'),
    ("appVersion: 'v8.0.1'" in meta,'app-meta.js nie wskazuje v8.0.1.'),
    ('Post-Match Center' in clean or 'RAPORT PO MECZU' in clean,'Brak Post-Match Center w Clean Core.'),
    ('learning_signals_v79b' in clean,'Clean Core nie pokazuje specialist learning.'),
    ('adaptive_review_v79' in clean,'Clean Core nie pokazuje analizy Adaptive po meczu.'),
]
for ok,msg in required:
    if not ok:failures.append(msg)

if 'history-days-v732.js' in index or 'history-days-v732.css' in index:
    failures.append('Stary renderer History v7.3.2 nadal jest ładowany.')
if (frontend/'history-days-v732.js').exists() or (frontend/'history-days-v732.css').exists():
    failures.append('Stare pliki History v7.3.2 nadal istnieją po migracji v8.0.')
if "Tenis AI v7.8D · Calibration Guard" in ui:
    failures.append('ui-v751 nadal nadpisuje nagłówek starą wersją v7.8D.')
if 'readability-v753.js' in index:
    failures.append('Obsolete readability-v753.js nadal jest ładowany.')
if 'cache.addAll(ASSETS)' in sw:
    failures.append('Service worker nadal używa kruchego cache.addAll(ASSETS).')
cache_v801 = re.search(r"const\s+CACHE\s*=\s*['\"]tenis-ai-v801-[0-9a-z._-]+['\"]", sw, re.I)
cache_v84b = re.search(r"const\s+CACHE\s*=\s*['\"]tenis-ai-v84b-[0-9a-z._-]+['\"]", sw, re.I)
legacy_v801_marker = 'tenis-ai-v801-player-profile' in sw
if not (cache_v801 or (cache_v84b and legacy_v801_marker)):
    failures.append('Service worker nie ma zgodnego cache v801/v84b z markerem kompatybilności.')
if '@supabase/supabase-js@2.112.3' not in index:
    warnings.append('Supabase JS nie jest przypięty do 2.112.3.')

legacy_root=[]
legacy_root += list(ROOT.glob('install_v*.py'))
legacy_root += list(ROOT.glob('V*_README.txt'))
legacy_root += list(ROOT.glob('tenis-ai-v*.zip'))
for name in ['PREDEPLOY_TESTS.txt','TESTS.txt','TESTS_PREUPDATE.txt','v7.4-admin-moderator.txt']:
    p=ROOT/name
    if p.exists():legacy_root.append(p)
if legacy_root:
    failures.append('Legacy śmieci w root: '+', '.join(sorted(p.name for p in legacy_root)))

analytics=read(frontend/'player-analytics-v76.js')
adaptive=read(frontend/'adaptive-learning-v79.js')
clean_core=read(frontend/'clean-core-v80.js')

restore=read(frontend/'restore-v762.js')
if 'setInterval(refresh,1200)' in restore:
    failures.append('Stary polling UI co 1.2 s nadal istnieje.')

if 'setInterval(inject,700)' in analytics:
    failures.append('Player Analytics nadal ma stary polling co 700 ms.')

if re.search(r'observer\.observe\(document\.documentElement', adaptive):
    failures.append('Adaptive nadal obserwuje cały dokument.')

if re.search(r'observer\.observe\(document\.documentElement', clean_core):
    failures.append('Clean Core nadal obserwuje cały dokument.')

if workflows.exists():
    for wf in [*workflows.glob('*.yml'),*workflows.glob('*.yaml')]:
        txt=read(wf);low=txt.lower()
        if 'git push' not in low:continue
        if 'git fetch origin' not in low or 'git rebase origin/main' not in low:
            warnings.append(f'{wf}: workflow pushuje bez fetch/rebase safeguard.')
        if 'concurrency:' not in low:
            warnings.append(f'{wf}: workflow pushujący nie ma concurrency guard.')

print('=== Tenis AI v8.0.1 Player Profile Project Health ===')
print(f'JS files:  {len(js_files)}')
print(f'CSS files: {len(css_files)}')
for w in warnings:print('WARN:',w)
for f in failures:print('FAIL:',f)
print(f'\nSummary: {len(failures)} FAIL / {len(warnings)} WARN')
if failures:sys.exit(1)
print('Project health: PASS')
