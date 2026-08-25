from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
mx=(ROOT/'frontend/model-guide.js').read_text(encoding='utf-8')
idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
errors=[]
need=[
('const selectedList=[...selectedCols]','selected columns list'),
('const filled=selectedList.reduce','coverage count per row'),
('const complete=selectedList.length>0 && filled===selectedList.length','complete row filter'),
('const hide=showEmpty ? false : !complete','checkbox semantics'),
('Pokaż rynki bez danych / niepełne','clear checkbox label'),
('model-guide.js?v=853m6','cache bust'),
]
for s,m in need:
    target=idx if 'model-guide.js?v=' in s else mx
    if s not in target: errors.append('brak: '+m)
for s,m in [
    ('const any=[...selectedCols].some','old any-data filter'),
    ('const hide=!showEmpty&&!any','old hide rule'),
    ('fetch(','network in matrix'),
    ('setInterval(','polling in matrix'),
]:
    if s in mx: errors.append('nadal jest: '+m)
if errors:
    print('v8.5.3M6 Empty Rows Toggle Guard: FAIL')
    [print(' -',x) for x in errors]
    raise SystemExit(1)
print('v8.5.3M6 Empty Rows Toggle Guard: PASS')
