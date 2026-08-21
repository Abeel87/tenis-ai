from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
F=ROOT/"frontend"

# 1) Napraw konkretny błąd v7.6.1: literalne "\n" zakomentowały bridge profilu.
ps=F/"player-search.js"
s=ps.read_text(encoding="utf-8")
bad='  // v7.6.1: public bridge for clickable player names in Match Center.\\\\n  window.tenisAIPlayerProfileOpen=selectPlayer;\\\\n\\\\n  clearBtn.onclick=closeProfile;'
good="  // v7.6.2: public bridge for clickable player names in Match Center.\n  window.tenisAIPlayerProfileOpen=selectPlayer;\n\n  clearBtn.onclick=closeProfile;"
if bad in s:
    s=s.replace(bad,good,1)
elif "window.tenisAIPlayerProfileOpen=selectPlayer;" not in s:
    marker="  clearBtn.onclick=closeProfile;"
    if marker not in s:
        raise SystemExit("player-search.js: nie znaleziono miejsca na bridge profilu")
    s=s.replace(marker,"  window.tenisAIPlayerProfileOpen=selectPlayer;\n\n"+marker,1)
ps.write_text(s,encoding="utf-8")

# 2) Analytics PRO: pokaż zaraz pod KPI i pilnuj po rerenderach.
pa=F/"player-analytics-v76.js"
a=pa.read_text(encoding="utf-8")
old="""      const pt=panel.querySelector('#player-tendencies-v71');
      if(pt)pt.insertAdjacentElement('afterend',section);
      else{
        const sections=[...panel.querySelectorAll('.player-section')];
        const stats=sections.find(s=>s.textContent.includes('Statystyki zawodnika'));
        if(stats)stats.insertAdjacentElement('afterend',section);else panel.appendChild(section);
      }"""
new="""      const kpis=panel.querySelector('.player-profile-kpis');
      const pt=panel.querySelector('#player-tendencies-v71');
      if(kpis)kpis.insertAdjacentElement('afterend',section);
      else if(pt)pt.insertAdjacentElement('afterend',section);
      else{
        const sections=[...panel.querySelectorAll('.player-section')];
        const stats=sections.find(s=>s.textContent.includes('Statystyki zawodnika'));
        if(stats)stats.insertAdjacentElement('afterend',section);else panel.appendChild(section);
      }"""
if old in a:
    a=a.replace(old,new,1)
if "setInterval(inject,700);" not in a:
    marker="  setTimeout(inject,900);\n})();"
    if marker not in a:
        raise SystemExit("player-analytics-v76.js: nie znaleziono końca inject")
    a=a.replace(marker,"  setTimeout(inject,200);\n  setInterval(inject,700);\n})();",1)
pa.write_text(a,encoding="utf-8")

# 3) Czytelniejsza nazwa ogólnej skuteczności.
app=F/"app.js"
ap=app.read_text(encoding="utf-8")
ap=ap.replace("📊 Skuteczność zielonych","📊 Skuteczność modelu · zielone sygnały")
app.write_text(ap,encoding="utf-8")

# 4) Podłącz nowe niezależne sterowanie UI.
idx=F/"index.html"
x=idx.read_text(encoding="utf-8")
if "restore-v762.css" not in x:
    marker='<link rel="stylesheet" href="player-analytics-v76.css">'
    if marker not in x:
        raise SystemExit("index.html: brak marker CSS")
    x=x.replace(marker,marker+'\n  <link rel="stylesheet" href="restore-v762.css">',1)
if "restore-v762.js" not in x:
    marker='  <script src="readability-v753.js"></script>'
    if marker not in x:
        raise SystemExit("index.html: brak marker JS")
    x=x.replace(marker,marker+'\n  <script src="restore-v762.js"></script>',1)

x=re.sub(r'(<div class="brand-copy">[\s\S]*?<p>)(Tenis AI v[^<]+)(</p>)',
         r'\1Tenis AI v7.6.2 · Statystyki + profile FIX\3',x,count=1)
x=x.replace("LAB v7.6.1","LAB v7.6.2").replace("LAB v7.6","LAB v7.6.2")
if "v7.6.2:" not in x:
    x=x.replace("<div>v7.6:","<div>v7.6.2: przywrócono Zwiń/Rozwiń, Statystyki/Skuteczność i naprawiono wejście do Player Analytics PRO. v7.6:",1)
idx.write_text(x,encoding="utf-8")

# 5) SW cache.
sw=F/"sw.js"
w=sw.read_text(encoding="utf-8")
w=re.sub(r"const C='[^']+';","const C='tenis-ai-v762-ui-restore-player-fix';",w,count=1)
for asset,anchor in [("restore-v762.css","player-analytics-v76.css"),("restore-v762.js","readability-v753.js")]:
    if asset not in w and f"'{anchor}'" in w:
        w=w.replace(f"'{anchor}'",f"'{anchor}','{asset}'",1)
sw.write_text(w,encoding="utf-8")

print("Tenis AI v7.6.2 UI restore + player fix: OK")
