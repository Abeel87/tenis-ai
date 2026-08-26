from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
checks=[]

def ok(name, cond, detail=''):
    checks.append((name,bool(cond),detail))

backend=(ROOT/'backend/player_intelligence_v85.py').read_text(encoding='utf-8')
front=(ROOT/'frontend/player-intelligence-v85.js').read_text(encoding='utf-8')
index=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
workflow=(ROOT/'.github/workflows/update-and-pages.yml').read_text(encoding='utf-8')
scenario=(ROOT/'frontend/scenario-studio-v82a.js').read_text(encoding='utf-8')

ok('backend version', 'VERSION = "v8.5"' in backend)
ok('cache-first zero API', '"api_calls": 0' in backend and 'requests.' not in backend)
ok('same-surface policy', 'same_surface_only' in backend)
ok('L5/L10/L20', 'WINDOWS = (5, 10, 20)' in backend)
ok('12m + 24m fallback', 'PRIMARY_DAYS = 365' in backend and 'FALLBACK_DAYS = 730' in backend)
ok('set 4/5 support', 'set4_won' in backend and 'set5_won' in backend)
ok('shadow bounded', '"HIGH": (.25, .04)' in backend and 'production_influence' in backend)
ok('generator remains shadow-only', '"generator_assist": "disabled_shadow_only"' in backend)
ok('frontend no fetch', 'fetch(' not in front)
ok('frontend no observer', 'new MutationObserver(' not in front)
ok('frontend no interval', 'setInterval' not in front)
ok('index css once', index.count('player-intelligence-v85.css?v=85a1')==1)
ok('index js once', index.count('player-intelligence-v85.js?v=85a1')==1)
ok('workflow pre', 'Player Intelligence v8.5 PRE' in workflow)
ok('workflow post', 'Player Intelligence v8.5 POST' in workflow)
ok('workflow guard', 'Player Intelligence Guard v8.5' in workflow)
ok('strict shadow marker', 'PLAYER_INTELLIGENCE_V85_SHADOW_ONLY' in scenario)
ok('no generator score influence', 'score+=Math.max(-cap,Math.min(cap,ps*.20))' not in scenario)
ok('protected app pin', 'app.js?v=84b1' in index)
ok('protected autolearn pin', 'autolearn-v84.js?v=84a1&hf=84b1' in index)
ok('protected scenario pin', 'scenario-studio-v82a.js?v=82a6&hf=84a1' in index)

failed=[x for x in checks if not x[1]]
for name,status,detail in checks:
    print(('PASS' if status else 'FAIL')+': '+name+(f' — {detail}' if detail else ''))
if failed:
    raise SystemExit(f'v8.5 guard failed: {len(failed)}')
print(f'v8.5 guard PASS: {len(checks)} checks')
