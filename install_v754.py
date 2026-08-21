from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

def edit(path,fn):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    n=fn(s)
    if n!=s:p.write_text(n,encoding='utf-8')

def index(s):
    if 'admin-delete-v754.css' not in s:
        s=s.replace(
          '<link rel="stylesheet" href="community-admin-v74.css">',
          '<link rel="stylesheet" href="community-admin-v74.css">\n  <link rel="stylesheet" href="admin-delete-v754.css">'
        )
    if 'admin-delete-v754.js' not in s:
        s=s.replace(
          '<script src="community-admin-v74.js"></script>',
          '<script src="community-admin-v74.js"></script>\n  <script src="admin-delete-v754.js"></script>'
        )
    s=s.replace('Tenis AI v7.5.3 · Czytelność + gemy meczu','Tenis AI v7.5.4 · Admin delete')
    s=s.replace('LAB v7.5.3','LAB v7.5.4')
    if 'v7.5.4:' not in s:
        s=s.replace(
          '<div>v7.5.3:',
          '<div>v7.5.4: admin może trwale usunąć zwykłe konto po podwójnym potwierdzeniu. v7.5.3:'
        )
    return s

def sw(s):
    s=re.sub(r"const C='[^']+';","const C='tenis-ai-v754-admin-delete';",s,count=1)
    for asset,anchor in [
      ('admin-delete-v754.css','community-admin-v74.css'),
      ('admin-delete-v754.js','community-admin-v74.js')
    ]:
        if asset not in s:
            s=s.replace(f"'{anchor}'",f"'{anchor}','{asset}'")
    return s

edit(Path('frontend/index.html'),index)
edit(Path('frontend/sw.js'),sw)
print('Tenis AI v7.5.4 installer: OK')
