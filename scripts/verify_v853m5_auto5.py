from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
mx=(ROOT/'frontend/model-guide.js').read_text(encoding='utf-8')
idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
errors=[]
need=[
('return b.coverage-a.coverage || pa-pb','AUTO 5 strict coverage'),
('AUTO 5 · NAJWIĘCEJ DANYCH','label AUTO 5'),
('MM853M3_MAX=5','limit 5'),
('coverage','coverage counter'),
]
for s,m in need:
    if s not in mx: errors.append('brak: '+m)
for s,m in [('coverage+(pa<3','stare bonusowanie pokrycia'),('fetch(','request sieciowy'),('setInterval(','polling')]:
    if s in mx: errors.append('nadal jest: '+m)
if 'model-guide.js?v=853m5' not in idx: errors.append('brak cache bust 853m5')
if errors:
    print('v8.5.3M5 AUTO 5 Guard: FAIL')
    [print(' -',x) for x in errors]
    raise SystemExit(1)
print('v8.5.3M5 AUTO 5 Guard: PASS')
