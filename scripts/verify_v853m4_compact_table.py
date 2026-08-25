from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
mx=(ROOT/'frontend/model-guide.js').read_text(encoding='utf-8')
idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
errors=[]
def need(s,m):
    if s not in mx: errors.append('brak: '+m)
def forbid(s,m):
    if s in mx: errors.append('nadal jest: '+m)
need('min-width:118px!important','wezszego Rynek desktop')
need('min-width:92px!important','wezszego Typ desktop')
need('min-width:108px!important','wezszego Rynek mobile')
need('min-width:82px!important','wezszego Typ mobile')
need('white-space:normal!important','zawijania Rynek/Typ')
need("(market==='set1_total'||market==='set2_total')&&String(ln)==='11.5'",'filtra 11.5 tylko dla 1S/2S')
if 'model-guide.js?v=853m4' not in idx: errors.append('brak cache bust 853m4')
forbid('fetch(','request sieciowy w Match Matrix')
forbid('setInterval(','polling w Match Matrix')
if errors:
    print('v8.5.3M4 Compact Table Guard: FAIL')
    [print(' -',x) for x in errors]
    raise SystemExit(1)
print('v8.5.3M4 Compact Table Guard: PASS')
