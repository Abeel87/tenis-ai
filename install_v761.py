
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent

ps=ROOT/"frontend/player-search.js"
s=ps.read_text(encoding="utf-8")
if "window.tenisAIPlayerProfileOpen=selectPlayer;" not in s:
    marker="  clearBtn.onclick=closeProfile;"
    if marker not in s:
        raise SystemExit("player-search.js: listener marker not found")
    s=s.replace(
        marker,
        "  // v7.6.1: public bridge for clickable player names in Match Center.\\n"
        "  window.tenisAIPlayerProfileOpen=selectPlayer;\\n\\n"
        + marker,
        1
    )
ps.write_text(s,encoding="utf-8")

ui=ROOT/"frontend/ui-v751.js"
u=ui.read_text(encoding="utf-8")

old = "        <div class=\"p751-names\">\\n          <b>${esc(m.p1)}</b>\\n          <span>VS</span>\\n          <b>${esc(m.p2)}</b>\\n        </div>"
new = "        <div class=\"p751-names\">\\n          <b class=\"p761-player-link\" role=\"link\" tabindex=\"0\" data-p761-player=\"${esc(m.p1)}\" title=\"Otwórz profil ${esc(m.p1)}\">${esc(m.p1)}</b>\\n          <span>VS</span>\\n          <b class=\"p761-player-link\" role=\"link\" tabindex=\"0\" data-p761-player=\"${esc(m.p2)}\" title=\"Otwórz profil ${esc(m.p2)}\">${esc(m.p2)}</b>\\n        </div>"
if "data-p761-player=\"${esc(m.p1)}\"" not in u:
    if old not in u:
        raise SystemExit("ui-v751.js: card player names marker not found")
    u=u.replace(old,new,1)

old = "      <section class=\"p751-matchup\">\\n        <b>${esc(m.p1)}</b><span>VS</span><b>${esc(m.p2)}</b>"
new = "      <section class=\"p751-matchup\">\\n        <b class=\"p761-player-link\" role=\"link\" tabindex=\"0\" data-p761-player=\"${esc(m.p1)}\" title=\"Otwórz profil ${esc(m.p1)}\">${esc(m.p1)}</b><span>VS</span><b class=\"p761-player-link\" role=\"link\" tabindex=\"0\" data-p761-player=\"${esc(m.p2)}\" title=\"Otwórz profil ${esc(m.p2)}\">${esc(m.p2)}</b>"
if u.count("data-p761-player=\"${esc(m.p1)}\"") < 2:
    if old not in u:
        raise SystemExit("ui-v751.js: detail player names marker not found")
    u=u.replace(old,new,1)

helper = """
  function openPlayerProfile761(name){
    name=String(name||'').trim();
    if(!name)return;
    try{closeMatch()}catch{}
    if(typeof window.tenisAIPlayerProfileOpen==='function'){
      window.tenisAIPlayerProfileOpen(name);
      return;
    }
    const inp=document.querySelector('#player-search-input');
    if(inp){
      inp.value=name;
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
    }
  }

  function bindPlayerLinks761(root=document){
    root.querySelectorAll?.('[data-p761-player]').forEach(el=>{
      if(el.dataset.p761Bound==='1')return;
      el.dataset.p761Bound='1';
      const open=e=>{
        e.preventDefault();
        e.stopPropagation();
        openPlayerProfile761(el.dataset.p761Player);
      };
      el.addEventListener('click',open);
      el.addEventListener('keydown',e=>{
        if(e.key==='Enter'||e.key===' '){open(e)}
      });
    });
  }

"""
if "function openPlayerProfile761(name)" not in u:
    marker="  function bindHome(){"
    if marker not in u:
        raise SystemExit("ui-v751.js: bindHome marker not found")
    u=u.replace(marker,helper+marker,1)

needle="  function bindHome(){\\n    document.querySelectorAll('[data-p751-focus]').forEach"
replace="  function bindHome(){\\n    bindPlayerLinks761(document);\\n    document.querySelectorAll('[data-p751-focus]').forEach"
if "function bindHome(){\n    bindPlayerLinks761(document);" not in u:
    if needle not in u:
        raise SystemExit("ui-v751.js: bindHome body marker not found")
    u=u.replace(needle,replace,1)

needle="    const o=ensureOverlay();o.innerHTML=detailHtml(m);o.hidden=false;document.body.classList.add('p751-modal-open');\\n    o.scrollTop=0;"
replace="    const o=ensureOverlay();o.innerHTML=detailHtml(m);o.hidden=false;document.body.classList.add('p751-modal-open');\\n    bindPlayerLinks761(o);\\n    o.scrollTop=0;"
if "bindPlayerLinks761(o);" not in u:
    if needle not in u:
        raise SystemExit("ui-v751.js: openMatch marker not found")
    u=u.replace(needle,replace,1)

u=u.replace(
    "document.querySelector('.brand-copy p').textContent='Tenis AI v7.5.1 · Match Center'",
    "document.querySelector('.brand-copy p').textContent='Tenis AI v7.6.1 · Klikalne profile'"
)
ui.write_text(u,encoding="utf-8")

css=ROOT/"frontend/player-analytics-v76.css"
c=css.read_text(encoding="utf-8")
block = """
/* v7.6.1 — clickable player names */
.p761-player-link{
  cursor:pointer!important;
  text-decoration:underline!important;
  text-decoration-color:rgba(185,255,0,.28)!important;
  text-underline-offset:3px!important;
  transition:color .15s ease,text-decoration-color .15s ease!important;
}
.p761-player-link:hover,
.p761-player-link:focus{
  color:#b9ff00!important;
  text-decoration-color:#b9ff00!important;
  outline:none!important;
}
.p751-matchup .p761-player-link::after{
  content:' ↗';
  font-size:.55em;
  color:#7897a5;
  vertical-align:middle;
}
"""
if "v7.6.1 — clickable player names" not in c:
    c+="\\n"+block
css.write_text(c,encoding="utf-8")

idx=ROOT/"frontend/index.html"
x=idx.read_text(encoding="utf-8")
x=x.replace("Tenis AI v7.6 · Player Analytics PRO","Tenis AI v7.6.1 · Klikalne profile")
x=x.replace("LAB v7.6","LAB v7.6.1")
if "v7.6.1:" not in x:
    x=x.replace(
        "<div>v7.6:",
        "<div>v7.6.1: kliknięcie nazwiska na karcie lub w szczegółach meczu otwiera profil Player Analytics PRO. v7.6:"
    )
idx.write_text(x,encoding="utf-8")

sw=ROOT/"frontend/sw.js"
w=sw.read_text(encoding="utf-8")
w=re.sub(r"const C='[^']+';","const C='tenis-ai-v761-clickable-players';",w,count=1)
sw.write_text(w,encoding="utf-8")

print("Tenis AI v7.6.1 clickable player profiles: OK")
