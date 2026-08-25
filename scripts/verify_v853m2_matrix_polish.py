from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
mx=(ROOT/'frontend/model-guide.js').read_text(encoding='utf-8')
eh=(ROOT/'frontend/early-hold-paths-v771.js').read_text(encoding='utf-8')
idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
errors=[]
def need(t,s,m):
    if s not in t: errors.append('brak: '+m)
def forbid(t,s,m):
    if s in t: errors.append('nadal jest: '+m)
need(mx,'overflow-x:auto;overflow-y:visible;max-height:none','brak pionowego scrolla')
need(mx,'min-width:1360px','desktop width')
need(mx,'min-width:1240px','mobile width')
need(mx,'nth-child(12)','Ensemble highlight')
need(mx,'nth-child(13)','SH highlight')
need(mx,"#eh771-match-compare",'cleanup old compare')
need(eh,'Match Matrix owns the match-level comparison','disable old compare')
need(idx,'model-guide.js?v=853m2','matrix cache bust')
need(idx,'early-hold-paths-v771.js?v=853m2','early cache bust')
forbid(mx,'max-height:60vh','old nested vertical scroll')
forbid(mx,'fetch(','network in matrix')
forbid(mx,'setInterval(','polling in matrix')
if errors:
    print('v8.5.3M2 Matrix Polish Guard: FAIL')
    [print(' -',e) for e in errors]
    raise SystemExit(1)
print('v8.5.3M2 Matrix Polish Guard: PASS')
