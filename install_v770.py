from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
F=ROOT/'frontend'

# Assets are unpacked directly into frontend/.
for name in ['performance-center-v77.js','performance-center-v77.css']:
    if not (F/name).exists(): raise SystemExit(f'Brak {name}')

idx=F/'index.html'
x=idx.read_text(encoding='utf-8')
if 'performance-center-v77.css' not in x:
    marker='<link rel="stylesheet" href="pbp-validation-v73.css">'
    if marker not in x: raise SystemExit('index.html: brak marker CSS')
    x=x.replace(marker,marker+'\n  <link rel="stylesheet" href="performance-center-v77.css">',1)
if 'performance-center-v77.js' not in x:
    marker='  <script src="restore-v762.js"></script>'
    if marker not in x: raise SystemExit('index.html: brak marker JS')
    x=x.replace(marker,marker+'\n  <script src="performance-center-v77.js"></script>',1)
x=re.sub(r'<p>Tenis AI v[^<]+</p>','<p>Tenis AI v7.7 · Model Performance Center</p>',x,count=1)
x=re.sub(r'<span class="model-lab-badge">LAB v[^<]+</span>','<span class="model-lab-badge">LAB v7.7</span>',x,count=1)
if 'v7.7: Model Performance Center' not in x:
    x=x.replace('<div>v7.6.3:','<div>v7.7: Model Performance Center — okresy, trendy, 95% CI, próbki, rynki, toury, nawierzchnie, wersje modelu, PBP i Market Lab. v7.6.3:',1)
idx.write_text(x,encoding='utf-8')

# Old visual shell used to rewrite the visible version after boot.
ui=F/'ui-v751.js'
u=ui.read_text(encoding='utf-8')
u=re.sub(r"document\.querySelector\('\.brand-copy p'\)\.textContent='Tenis AI v[^']+'","document.querySelector('.brand-copy p').textContent='Tenis AI v7.7 · Model Performance Center'",u,count=1)
ui.write_text(u,encoding='utf-8')

sw=F/'sw.js'
w=sw.read_text(encoding='utf-8')
w=re.sub(r"const C='[^']+';","const C='tenis-ai-v770-performance-center';",w,count=1)
for asset,anchor in [('performance-center-v77.css','pbp-validation-v73.css'),('performance-center-v77.js','restore-v762.js')]:
    if f"'{asset}'" not in w:
        if f"'{anchor}'" not in w: raise SystemExit(f'sw.js: brak {anchor}')
        w=w.replace(f"'{anchor}'",f"'{anchor}','{asset}'",1)
sw.write_text(w,encoding='utf-8')

print('Tenis AI v7.7 Model Performance Center: OK')
