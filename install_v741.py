from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

def update(path,fn):
    p=ROOT/path
    s=p.read_text(encoding="utf-8")
    n=fn(s)
    if n!=s:p.write_text(n,encoding="utf-8")

def idx(s):
    if 'market-lab-v741.css' not in s:
        s=s.replace('<link rel="stylesheet" href="community-admin-v74.css">','<link rel="stylesheet" href="community-admin-v74.css">\n  <link rel="stylesheet" href="market-lab-v741.css">')
    if 'registration-fix-v741.js' not in s:
        s=s.replace('<script src="account.js"></script>','<script src="account.js"></script>\n  <script src="registration-fix-v741.js"></script>')
    if 'market-lab-v741.js' not in s:
        s=s.replace('<script src="history-days-v732.js"></script>','<script src="history-days-v732.js"></script>\n  <script src="market-lab-v741.js"></script>')
    s=s.replace('Tenis AI v7.4 · Admin & Moderator','Tenis AI v7.4.1 · Market Lab')
    s=s.replace('LAB v7.4</span>','LAB v7.4.1</span>')
    return s

def sw(s):
    s=re.sub(r"const C='[^']+';","const C='tenis-ai-v741-registration-market-lab';",s,count=1)
    for asset,anchor in [('market-lab-v741.css','community-admin-v74.css'),('registration-fix-v741.js','account.js'),('market-lab-v741.js','history-days-v732.js')]:
        if asset not in s:s=s.replace(f"'{anchor}'",f"'{anchor}','{asset}'")
    return s

def wf(s):
    if 'Build Market Lab v7.4.1' not in s:
        marker='      - name: Build player tendency profiles'
        block='      - name: Build Market Lab v7.4.1\n        run: python backend/market_lab_v741.py\n'
        s=s.replace(marker,block+marker)
    if 'Track Market Lab learning data' not in s:
        marker='      - name: Save tennis history + PBP cache'
        block='      - name: Track Market Lab learning data\n        run: python backend/market_lab_tracker_v741.py\n'
        s=s.replace(marker,block+marker)
    return s

update(Path('frontend/index.html'),idx)
update(Path('frontend/sw.js'),sw)
update(Path('.github/workflows/update-and-pages.yml'),wf)
print('v7.4.1 installer: OK')
