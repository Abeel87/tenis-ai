from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

def edit(path,fn):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    n=fn(s)
    if n!=s:p.write_text(n,encoding='utf-8')

def index(s):
    if 'readability-v753.css' not in s:
        s=s.replace('<link rel="stylesheet" href="ui-v751.css">','<link rel="stylesheet" href="ui-v751.css">\n  <link rel="stylesheet" href="readability-v753.css">')
    if 'readability-v753.js' not in s:
        s=s.replace('<script src="ui-v751.js"></script>','<script src="ui-v751.js"></script>\n  <script src="readability-v753.js"></script>')
    s=s.replace('Tenis AI v7.5.2 · Registration UX','Tenis AI v7.5.3 · Czytelność + gemy meczu')
    s=s.replace('LAB v7.5.2','LAB v7.5.3')
    if 'v7.5.3:' not in s:
        s=s.replace('<div>v7.5.2:', '<div>v7.5.3: większa czcionka w całej aplikacji oraz osobna sekcja liczby gemów całego meczu przy każdym spotkaniu. v7.5.2:')
    return s

def sw(s):
    s=re.sub(r"const C='[^']+';","const C='tenis-ai-v753-readability-match-games';",s,count=1)
    for asset,anchor in [
        ('readability-v753.css','ui-v751.css'),
        ('readability-v753.js','ui-v751.js')
    ]:
        if asset not in s:
            s=s.replace(f"'{anchor}'",f"'{anchor}','{asset}'")
    return s

edit(Path('frontend/index.html'),index)
edit(Path('frontend/sw.js'),sw)
print('Tenis AI v7.5.3 installer: OK')
