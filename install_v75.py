from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

def update(path,fn):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    n=fn(s)
    if n!=s:p.write_text(n,encoding='utf-8')

def index_patch(s):
    if 'ui-v75.css' not in s:
        s=s.replace('<link rel="stylesheet" href="market-lab-v741.css">','<link rel="stylesheet" href="market-lab-v741.css">\n  <link rel="stylesheet" href="ui-v75.css">')
    if 'ui-v75.js' not in s:
        s=s.replace('<script src="market-lab-v741.js"></script>','<script src="market-lab-v741.js"></script>\n  <script src="ui-v75.js"></script>')
    s=s.replace('Tenis AI v7.4.1 · Market Lab','Tenis AI v7.5 · Match Center')
    s=s.replace('LAB v7.4.1','LAB v7.5')
    if 'v7.5:' not in s:
        s=s.replace('<div>v7.4:', '<div>v7.5: nowy czytelny Match Center, mocno wyróżnione mecze, szybki werdykt, zwijane sekcje i kompaktowa Historia. v7.4:')
    return s

def sw_patch(s):
    s=re.sub(r"const C='[^']+';","const C='tenis-ai-v750-match-center';",s,count=1)
    for asset,anchor in [('ui-v75.css','market-lab-v741.css'),('ui-v75.js','market-lab-v741.js')]:
        if asset not in s:
            s=s.replace(f"'{anchor}'",f"'{anchor}','{asset}'")
    return s

update(Path('frontend/index.html'),index_patch)
update(Path('frontend/sw.js'),sw_patch)
print('Tenis AI v7.5 installer: OK')
