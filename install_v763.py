from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
F=ROOT/"frontend"
B=ROOT/"backend"

# 1) PLAYER SEARCH — napraw literalne "\n" z v7.6.1.
ps=F/"player-search.js"
s=ps.read_text(encoding="utf-8")
pattern = re.compile(
    r'  // v7\.6\.1: public bridge for clickable player names in Match Center\.\\n'
    r'  window\.tenisAIPlayerProfileOpen=selectPlayer;\\n\\n'
    r'  clearBtn\.onclick=closeProfile;'
)
good = (
    "  // v7.6.3: public bridge for clickable player names in Match Center.\n"
    "  window.tenisAIPlayerProfileOpen=selectPlayer;\n\n"
    "  clearBtn.onclick=closeProfile;"
)
s, n = pattern.subn(good, s, count=1)
if n == 0:
    if "window.tenisAIPlayerProfileOpen=selectPlayer;" not in s:
        marker="  clearBtn.onclick=closeProfile;"
        if marker not in s:
            raise SystemExit("player-search.js: nie znaleziono clearBtn marker")
        s=s.replace(marker, "  window.tenisAIPlayerProfileOpen=selectPlayer;\n\n"+marker, 1)
ps.write_text(s,encoding="utf-8")

# 2) UI v7.5.1 — nie cofaj wersji po 250 ms.
ui=F/"ui-v751.js"
u=ui.read_text(encoding="utf-8")
u=re.sub(
    r"document\.querySelector\('\.brand-copy p'\)\.textContent='Tenis AI v[^']+'",
    "document.querySelector('.brand-copy p').textContent='Tenis AI v7.6.3 · Audit hardening'",
    u, count=1
)
ui.write_text(u,encoding="utf-8")

# 3) Toolbar: statystyki również gdy nie ma aktualnych grup/meczów.
rt=F/"restore-v762.js"
r=rt.read_text(encoding="utf-8")
old = """  function decorateHome(){
    const app=$('#app');
    const groups=$('.p751-groups',app);
    if(!groups||$('#v762-home-tools',app))return;

    const bar=document.createElement('div');
    bar.id='v762-home-tools';
    bar.className='v762-home-tools';
    bar.innerHTML=`
      <button type="button" data-v762="collapse">− Zwiń wszystko</button>
      <button type="button" data-v762="expand">+ Rozwiń wszystko</button>
      <button type="button" class="stats" data-v762="stats">📊 Statystyki / skuteczność</button>`;
    groups.insertAdjacentElement('beforebegin',bar);

    $('[data-v762="collapse"]',bar).onclick=()=>collapseAll(false);
    $('[data-v762="expand"]',bar).onclick=()=>collapseAll(true);
    $('[data-v762="stats"]',bar).onclick=openStats;
  }"""
new = """  function decorateHome(){
    const app=$('#app');
    if(!app||$('#v762-home-tools',app))return;
    const groups=$('.p751-groups',app);
    const focus=$('.p751-focus',app);
    const empty=$('.p751-empty',app);
    if(!groups&&!focus&&!empty)return;

    const bar=document.createElement('div');
    bar.id='v762-home-tools';
    bar.className='v762-home-tools';
    bar.innerHTML=`
      <button type="button" data-v762="collapse" ${groups?'':'disabled'}>− Zwiń wszystko</button>
      <button type="button" data-v762="expand" ${groups?'':'disabled'}>+ Rozwiń wszystko</button>
      <button type="button" class="stats" data-v762="stats">📊 Statystyki / skuteczność</button>`;

    const anchor=groups||empty;
    if(anchor)anchor.insertAdjacentElement('beforebegin',bar);
    else if(focus)focus.insertAdjacentElement('afterend',bar);
    else app.prepend(bar);

    $('[data-v762="collapse"]',bar).onclick=()=>collapseAll(false);
    $('[data-v762="expand"]',bar).onclick=()=>collapseAll(true);
    $('[data-v762="stats"]',bar).onclick=openStats;
  }"""
if old in r:
    r=r.replace(old,new,1)
elif "const focus=$('.p751-focus',app);" not in r:
    raise SystemExit("restore-v762.js: decorateHome ma nieznany kształt")
rt.write_text(r,encoding="utf-8")

css=F/"restore-v762.css"
c=css.read_text(encoding="utf-8")
if ".v762-home-tools button:disabled" not in c:
    c += "\n.v762-home-tools button:disabled{opacity:.42;cursor:default;}\n"
css.write_text(c,encoding="utf-8")

# 4) PLAYER ANALYTICS PRO — historia-only ma jawne N/D zamiast ciszy.
pa=F/"player-analytics-v76.js"
a=pa.read_text(encoding="utf-8")
old = """    const name=input.value.trim(); if(!name)return;
    const d=dataFor(name); if(!d)return;
    injecting=true;
    try{
      const section=document.createElement('section');"""
new = """    const name=input.value.trim(); if(!name)return;
    const d=dataFor(name);
    injecting=true;
    try{
      const section=document.createElement('section');"""
if old in a:
    a=a.replace(old,new,1)

old2 = """      const ui=state();
      const surfSample=Number(d.trends?.surface?.[ui.window]?.sample_matches||0);
      if(ui.scope==='surface'&&surfSample<3)ui.scope='all';
      render(section.querySelector('#pa76-content'),name,d,ui);
    }finally{injecting=false}"""
new2 = """      if(!d){
        section.querySelector('#pa76-content').innerHTML=
          '<div class="pa76-head"><div><b>🧠 Player Analytics PRO</b><span>profil 5/10/20</span></div><em>N/D</em></div>'+
          '<div class="player-empty">Ten zawodnik jest obecnie dostępny tylko w historii Tenis AI. Rozszerzony profil PRO powstaje z bieżącego pakietu tendencies/PBP i pojawi się, gdy zawodnik znajdzie się w aktualnych spotkaniach.</div>';
        return;
      }
      const ui=state();
      const surfSample=Number(d.trends?.surface?.[ui.window]?.sample_matches||0);
      if(ui.scope==='surface'&&surfSample<3)ui.scope='all';
      render(section.querySelector('#pa76-content'),name,d,ui);
    }finally{injecting=false}"""
if old2 in a:
    a=a.replace(old2,new2,1)
elif "Ten zawodnik jest obecnie dostępny tylko w historii Tenis AI" not in a:
    raise SystemExit("player-analytics-v76.js: nie znaleziono końca inject")
pa.write_text(a,encoding="utf-8")

# 5) Community count — hub nie nadpisuje Członków liczbą wszystkich kont.
hub=F/"community-hub.js"
h=hub.read_text(encoding="utf-8")
h=h.replace(
    "      if(ue) ue.textContent = d.registered ?? '—';",
    "      if(ue && !hasAccess()) ue.textContent = d.registered ?? '—';",
    1
)
hub.write_text(h,encoding="utf-8")

# 6) LIVE API label — BASIC, nie FREE.
upd=B/"update.py"
q=upd.read_text(encoding="utf-8")
q=q.replace("return rows,'live-tennis-api-free'","return rows,'live-tennis-api-basic'",1)
upd.write_text(q,encoding="utf-8")

# 7) PBP validation — doprecyzowanie green walk-forward.
pbp=F/"pbp-validation-v73.js"
p=pbp.read_text(encoding="utf-8")
old_note='<div class="v73-note">Brier: im niżej, tym lepiej (0 = idealnie). Production tracker zaczyna zbierać czystą, zamrożoną historię od v7.3.</div>'
new_note='<div class="v73-note">Brier: im niżej, tym lepiej (0 = idealnie). Production tracker zbiera zamrożone typy przed meczem. W replay walk-forward „zielone ≥72” oznacza pewny kierunek zdarzenia (max(p,1−p) ≥72), więc nie jest to dokładnie ta sama próbka co zielone typy produkcyjne.</div>'
if old_note in p:
    p=p.replace(old_note,new_note,1)
pbp.write_text(p,encoding="utf-8")

# 8) Service Worker — brakujące assety.
sw=F/"sw.js"
w=sw.read_text(encoding="utf-8")
w=re.sub(r"const C='[^']+';","const C='tenis-ai-v763-audit-hardening';",w,count=1)
for asset in [
    "registration-fix-v741.js",
    "registration-ux-v752.js",
    "market-lab-v741.js",
    "market-lab-v741.css",
]:
    if f"'{asset}'" not in w:
        marker="'manifest.webmanifest'"
        if marker not in w:
            raise SystemExit("sw.js: brak manifest marker")
        w=w.replace(marker,f"'{asset}',{marker}",1)
sw.write_text(w,encoding="utf-8")

# 9) Index / widoczna wersja.
idx=F/"index.html"
x=idx.read_text(encoding="utf-8")
x=re.sub(r'<p>Tenis AI v[^<]+</p>','<p>Tenis AI v7.6.3 · Audit hardening</p>',x,count=1)
x=re.sub(r'<span class="model-lab-badge">LAB v[^<]+</span>',
         '<span class="model-lab-badge">LAB v7.6.3</span>',x,count=1)
if "v7.6.3:" not in x:
    x=x.replace(
        "<div>v7.6.2:",
        "<div>v7.6.3: audyt i utwardzenie — naprawa core player-search, wersji UI, pustego widoku statystyk, community count, BASIC label i cache PWA. v7.6.2:",
        1
    )
idx.write_text(x,encoding="utf-8")

print("Tenis AI v7.6.3 audit hardening: OK")
