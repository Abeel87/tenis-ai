from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

def edit(path,fn):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    n=fn(s)
    if n!=s:p.write_text(n,encoding='utf-8')

def index(s):
    if 'registration-ux-v752.css' not in s:
        s=s.replace('<link rel="stylesheet" href="account.css">','<link rel="stylesheet" href="account.css">\n  <link rel="stylesheet" href="registration-ux-v752.css">')
    if 'registration-ux-v752.js' not in s:
        s=s.replace('<script src="registration-fix-v741.js"></script>','<script src="registration-fix-v741.js"></script>\n  <script src="registration-ux-v752.js"></script>')
    s=s.replace('Tenis AI v7.5.1 · Project UI','Tenis AI v7.5.2 · Registration UX')
    s=s.replace('LAB v7.5.1','LAB v7.5.2')
    if 'v7.5.2:' not in s:
        s=s.replace('<div>v7.5.1:', '<div>v7.5.2: czytelne zasady rejestracji, walidacja pól i polskie komunikaty błędów Supabase. v7.5.1:')
    return s

def sw(s):
    s=re.sub(r"const C='[^']+';","const C='tenis-ai-v752-registration-ux';",s,count=1)
    for asset,anchor in [
        ('registration-ux-v752.css','account.css'),
        ('registration-ux-v752.js','registration-fix-v741.js')
    ]:
        if asset not in s:
            s=s.replace(f"'{anchor}'",f"'{anchor}','{asset}'")
    return s

edit(Path('frontend/index.html'),index)
edit(Path('frontend/sw.js'),sw)
print('Tenis AI v7.5.2 installer: OK')
