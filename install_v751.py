from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

def edit(path,fn):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    n=fn(s)
    if n!=s:p.write_text(n,encoding='utf-8')

def index(s):
    if 'ui-v751.css' not in s:
        if '<link rel="stylesheet" href="ui-v75.css">' in s:
            s=s.replace('<link rel="stylesheet" href="ui-v75.css">','<link rel="stylesheet" href="ui-v75.css">\n  <link rel="stylesheet" href="ui-v751.css">')
        else:
            s=s.replace('<link rel="stylesheet" href="market-lab-v741.css">','<link rel="stylesheet" href="market-lab-v741.css">\n  <link rel="stylesheet" href="ui-v751.css">')
    if 'ui-v751.js' not in s:
        if '<script src="ui-v75.js"></script>' in s:
            s=s.replace('<script src="ui-v75.js"></script>','<script src="ui-v75.js"></script>\n  <script src="ui-v751.js"></script>')
        else:
            s=s.replace('<script src="market-lab-v741.js"></script>','<script src="market-lab-v741.js"></script>\n  <script src="ui-v751.js"></script>')
    s=s.replace('Tenis AI v7.5 · Match Center','Tenis AI v7.5.1 · Project UI')
    s=s.replace('LAB v7.5','LAB v7.5.1')
    if 'v7.5.1:' not in s:
        s=s.replace('<div>v7.5:', '<div>v7.5.1: przebudowa widoku zgodnie z zaakceptowanym projektem — lista meczów, pełnoekranowa analiza i nowe dolne menu. v7.5:')
    return s

def sw(s):
    s=re.sub(r"const C='[^']+';","const C='tenis-ai-v751-project-ui';",s,count=1)
    # Add both v7.5 and v7.5.1 assets to offline cache.
    for asset,anchor in [
        ('ui-v75.css','early-hold-v7.css'),
        ('ui-v751.css','ui-v75.css'),
        ('ui-v75.js','early-hold-v7.js'),
        ('ui-v751.js','ui-v75.js')
    ]:
        if asset not in s:
            s=s.replace(f"'{anchor}'",f"'{anchor}','{asset}'")
    return s

edit(Path('frontend/index.html'),index)
edit(Path('frontend/sw.js'),sw)
print('Tenis AI v7.5.1 Project UI installer: OK')
