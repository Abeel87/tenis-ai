from pathlib import Path
import re


def exact(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, got {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str, flags: int = 0) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"{label}: expected one regex match, got {count}")
    return out


# ---------------------------------------------------------------------------
# index.html — visible product contract: Start / Mecze / Typy / Zawodnicy / Konto
# ---------------------------------------------------------------------------
p = Path("frontend/index.html")
s = p.read_text(encoding="utf-8")
s = exact(
    s,
    '<html lang="pl" data-tenis-auth-state="pending" data-tenis-ui-ready="0" data-tenis-view="matches" data-tenis-route="matches">',
    '<html lang="pl" data-tenis-auth-state="pending" data-tenis-ui-ready="0" data-tenis-product="blueprint" data-tenis-view="home" data-tenis-route="home">',
    "html product attributes",
)
old_tabs = '''    <nav class="main-tabs" role="tablist" aria-label="Główne sekcje">
      <button class="active" data-view="matches" type="button"><span>🎾</span><b>Mecze</b></button>
      <button data-view="stats" type="button"><span>📊</span><b>Statystyki</b></button>
      <button data-view="history" type="button"><span>◷</span><b>Historia</b></button>
      <button data-view="coupons" type="button"><span>🧾</span><b>Kupony</b></button>
      <button data-view="feedback" type="button"><span>💬</span><b>Pomysły</b></button>
    </nav>'''
new_tabs = '''    <nav class="main-tabs" role="tablist" aria-label="Główne sekcje">
      <button class="active" data-view="home" type="button"><span>⌂</span><b>Start</b></button>
      <button data-view="matches" type="button"><span>🎾</span><b>Mecze</b></button>
      <button data-view="picks" type="button"><span>⚡</span><b>Typy</b></button>
      <button data-view="players" type="button"><span>👤</span><b>Zawodnicy</b></button>
      <button data-view="account" type="button"><span>●</span><b>Konto</b></button>
      <button class="legacy-view-hook" data-view="stats" type="button" aria-hidden="true" tabindex="-1">Statystyki</button>
      <button class="legacy-view-hook" data-view="history" type="button" aria-hidden="true" tabindex="-1">Historia</button>
      <button class="legacy-view-hook" data-view="coupons" type="button" aria-hidden="true" tabindex="-1">Kupony</button>
      <button class="legacy-view-hook" data-view="feedback" type="button" aria-hidden="true" tabindex="-1">Pomysły</button>
    </nav>'''
s = exact(s, old_tabs, new_tabs, "visible navigation")
mode_button = '''        <button id="tenis-ui-mode-toggle" class="topbar-action" type="button" aria-label="Przełącz widok prosty i techniczny" aria-pressed="false">
          <span>👁️</span><span><b>Widok</b><small>Prosty</small></span>
        </button>'''
admin_button = mode_button + '''
        <button id="tenis-admin-center-open" class="topbar-action admin-control-trigger" type="button" aria-label="Otwórz Control Center">
          <span>⚙️</span><span><b>Control</b><small>Admin</small></span>
        </button>'''
s = exact(s, mode_button, admin_button, "admin control trigger")
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# app.js — product-level routes while keeping old stats/history/etc. reachable
# ---------------------------------------------------------------------------
p = Path("frontend/app.js")
s = p.read_text(encoding="utf-8")
s = exact(s, "let view='matches';", "let view='home';", "default product route")
s = regex_once(
    s,
    r"const VIEW_COPY=\{.*?\n\};",
    '''const VIEW_COPY={
  home:['TENIS AI','Start','Najważniejsze rzeczy na dziś — bez przekopywania się przez techniczne dane.'],
  matches:['DZISIAJ','Mecze','Dzisiejsze spotkania. Otwórz mecz, żeby zobaczyć pełną analizę.'],
  picks:['SYGNAŁY','Typy','Aktualne typy PLAYABLE zweryfikowane względem bieżącej oferty Superbet.'],
  players:['ZAWODNICY','Zawodnicy','Wyszukaj zawodnika i przejdź od razu do jego profilu.'],
  account:['TWOJE KONTO','Konto','Profil, rola i ustawienia Tenis AI.'],
  stats:['WYNIKI','Statystyki','Zaawansowane wyniki modeli i diagnostyka.'],
  history:['ARCHIWUM','Historia','Rozliczone mecze i wcześniejsze sygnały.'],
  coupons:['SPOŁECZNOŚĆ','Kupony','Kupony testerów i zapisane typy.'],
  feedback:['ROZWÓJ','Pomysły','Zgłoszenia, poprawki i pomysły.']
};''',
    "view copy",
    flags=re.S,
)

product_functions = r'''
function productMatchKey(m){return String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'))}
function productSignalValue(x){const v=x?.operator_model_probability??x?.v??x?.final_score??x?.adaptive_prod_score??x?.score??x?.current;return v==null||!Number.isFinite(Number(v))?null:Number(v)}
function productPlayable(m,limit=5){try{return window.TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,limit)||[]}catch{return []}}
function productTopSignal(m){
  const p=productPlayable(m,1)[0];
  if(p){const v=productSignalValue(p);return v==null?null:{label:p.label||p.pick||p.key||'Typ PLAYABLE',value:v,source:'PLAYABLE'}}
  const raw=bestSignalsData(m,1)[0];
  return raw?{label:raw.label,value:Number(raw.v),source:'MODEL'}:null;
}
function productRows(){return filteredReady().slice().sort((a,b)=>new Date(a.scheduled_time||0)-new Date(b.scheduled_time||0))}
function productRole(){return String(document.documentElement.dataset.tenisRole||window.tenisAIAccount?.profile?.role||'user').toLowerCase()}
function bindProductScreen(){
  document.querySelectorAll('[data-product-go]').forEach(b=>b.onclick=()=>goView(b.dataset.productGo));
  document.querySelectorAll('#app [data-p751-open]').forEach(b=>b.onclick=e=>{
    e.preventDefault();
    let k=b.getAttribute('data-p751-open')||'';try{k=decodeURIComponent(k)}catch{}
    window.TENIS_AI_PROJECT_UI?.openMatch?.(k);
  });
  document.querySelectorAll('[data-product-action="account"]').forEach(b=>b.onclick=()=>document.querySelector('#account-button')?.click());
  document.querySelectorAll('[data-product-action="community"]').forEach(b=>b.onclick=()=>document.querySelector('#community-hub-open')?.click());
  document.querySelectorAll('[data-product-action="symphony"]').forEach(b=>b.onclick=()=>document.querySelector('#symphony-open')?.click());
  document.querySelectorAll('[data-product-action="control"]').forEach(b=>b.onclick=()=>document.querySelector('#tenis-admin-center-open')?.click());
}
function renderProductHome(){
  const app=document.querySelector('#app'),rows=productRows(),now=Date.now();
  const twoHours=rows.filter(m=>{const t=Date.parse(m.scheduled_time||'');return Number.isFinite(t)&&t>=now&&t<=now+2*3600000}).length;
  const playableMatches=rows.filter(m=>productPlayable(m,1).length).length;
  const ranked=rows.map(m=>({m,s:productTopSignal(m)})).filter(x=>x.s).sort((a,b)=>b.s.value-a.s.value);
  const strongest=ranked[0]?.s?.value;
  const role=productRole();
  app.innerHTML=`<div class="product-home">
    <section class="product-home-hero">
      <div><span>TWÓJ TENIS AI</span><h2>Co dziś gramy?</h2><p>Najpierw najważniejsze informacje. Szczegóły są dopiero tam, gdzie ich potrzebujesz.</p></div>
      <div class="product-home-kpis">
        <div><small>Mecze</small><b>${rows.length}</b><span>aktualne</span></div>
        <div><small>Do 2 h</small><b>${twoHours}</b><span>najbliższe</span></div>
        <div><small>PLAYABLE</small><b>${playableMatches}</b><span>Superbet</span></div>
        <div><small>Top</small><b>${strongest==null?'—':Math.round(strongest)}</b><span>${ranked[0]?.s?.source||'N/D'}</span></div>
      </div>
    </section>
    <section class="product-launch-grid">
      <button data-product-go="matches"><span>🎾</span><div><b>Mecze</b><small>Lista spotkań i pełna analiza meczu</small></div><i>→</i></button>
      <button data-product-go="picks"><span>⚡</span><div><b>Typy</b><small>Najmocniejsze aktualne PLAYABLE</small></div><i>→</i></button>
      <button data-product-go="players"><span>👤</span><div><b>Zawodnicy</b><small>Profil, forma, serwis i return</small></div><i>→</i></button>
      <button data-product-action="community"><span>👥</span><div><b>Społeczność</b><small>Testerzy, kupony i aktywność</small></div><i>→</i></button>
      ${role==='admin'?'<button class="admin-launch" data-product-action="control"><span>⚙️</span><div><b>Control Center</b><small>Pełne narzędzia administratora</small></div><i>→</i></button>':''}
      ${role==='moderator'?'<button class="moderator-launch" data-product-action="community"><span>🛡️</span><div><b>Moderacja</b><small>Narzędzia moderatora społeczności</small></div><i>→</i></button>':''}
    </section>
    <section class="product-home-section">
      <header><div><span>NAJMOCNIEJSZE TERAZ</span><b>Top typy</b></div><button data-product-go="picks">Wszystkie typy →</button></header>
      <div class="product-home-picks">${ranked.slice(0,3).map(({m,s})=>`<button data-p751-open="${encodeURIComponent(productMatchKey(m))}"><div><small>${esc((m.tour||'TENIS').toUpperCase())} · ${esc(scheduled(m)||'—')}</small><b>${esc(m.p1)} <i>vs</i> ${esc(m.p2)}</b><span>${esc(s.label)}</span></div><strong>${Math.round(s.value)}</strong><em>${esc(s.source)}</em></button>`).join('')||'<div class="product-empty">Brak gotowych typów dla aktualnych spotkań.</div>'}</div>
    </section>
  </div>`;
  bindProductScreen();
}
function renderProductPicks(){
  const app=document.querySelector('#app');
  const rows=productRows().flatMap(m=>productPlayable(m,12).map(s=>({m,s,v:productSignalValue(s)}))).filter(x=>x.v!=null).sort((a,b)=>b.v-a.v).slice(0,60);
  app.innerHTML=`<div class="product-picks-page">
    <section class="product-picks-hero"><div><span>FINALNA WARSTWA</span><h2>Typy PLAYABLE</h2><p>Tylko selekcje obecne w bieżącej ofercie Superbet i przepuszczone przez finalną warstwę PLAYABLE.</p></div><button data-product-action="symphony">🎼 Otwórz Symfonię 2.0</button></section>
    <div class="product-picks-list">${rows.length?rows.map(({m,s,v})=>`<button class="product-pick-row" data-p751-open="${encodeURIComponent(productMatchKey(m))}"><div><small>${esc((m.tour||'TENIS').toUpperCase())} · ${esc(scheduled(m)||'—')} · ${esc(m.tournament||'Turniej')}</small><b>${esc(m.p1)} <i>vs</i> ${esc(m.p2)}</b><span>${esc(s.label||s.pick||s.key||'Typ')}</span></div><strong>${Math.round(v)}/100</strong><em>SUPERBET ✓</em></button>`).join(''):'<div class="product-empty"><b>Brak PLAYABLE w tej chwili.</b><span>Modele nadal liczą dane, ale tu pokazujemy tylko typy dostępne teraz w Superbet.</span></div>'}</div>
  </div>`;
  bindProductScreen();
}
function renderProductPlayers(){
  const app=document.querySelector('#app');
  app.innerHTML=`<section class="product-players-intro"><span>ZAWODNICY</span><h2>Znajdź zawodnika</h2><p>Wyszukaj nazwisko powyżej. Profil pokaże formę, serwis, return, nawierzchnię, trendy i dostępne dane Player Intelligence.</p></section>`;
  bindProductScreen();
}
function renderProductAccount(){
  const app=document.querySelector('#app');
  const profile=window.tenisAIAccount?.profile||{};const role=productRole();
  app.innerHTML=`<div class="product-account-page"><section class="product-account-card"><div class="product-account-avatar">${esc((profile.username||'U').slice(0,1).toUpperCase())}</div><div><span>TWOJE KONTO</span><h2>${esc(profile.username||'Użytkownik')}</h2><p>Rola: <b>${esc(role.toUpperCase())}</b></p></div></section><section class="product-account-actions"><button data-product-action="account">👤 Profil i ustawienia <i>→</i></button>${role==='admin'?'<button data-product-action="control">⚙️ Control Center <i>→</i></button>':''}<button data-product-action="community">👥 Społeczność <i>→</i></button></section></div>`;
  bindProductScreen();
}
async function goView(next){
  const allowed=new Set(['home','matches','picks','players','account','stats','history','coupons','feedback']);
  if(!allowed.has(next))next='home';
  view=next;
  document.querySelectorAll('.main-tabs button[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===view));
  if(view==='stats'||view==='history')await loadSecondaryData();
  render();
  window.scrollTo({top:0,behavior:'auto'});
}
window.TENIS_AI_APP_NAV=Object.freeze({go:goView,current:()=>view});
'''
render_marker = "\nfunction render(){\n"
if render_marker not in s:
    raise SystemExit("render marker missing")
s = s.replace(render_marker, "\n" + product_functions + "\nfunction render(){\n", 1)
s = regex_once(
    s,
    r"function render\(\)\{\n.*?\n\}",
    '''function render(){
  updateViewChrome();
  const matchControls=document.querySelector('#match-controls');
  const matched=document.querySelector('#matched');
  if(matchControls)matchControls.style.display=view==='matches'?'block':'none';
  if(matched)matched.style.display=view==='matches'?'inline-block':'none';
  if(view==='home')renderProductHome();
  else if(view==='matches')renderMatches();
  else if(view==='picks')renderProductPicks();
  else if(view==='players')renderProductPlayers();
  else if(view==='account')renderProductAccount();
  else if(view==='stats')renderStats();
  else if(view==='history')renderHistory();
  else if(view==='feedback')renderFeedback();
  else renderCoupons();
}''',
    "product router",
    flags=re.S,
)
s = exact(
    s,
    "document.querySelectorAll('.main-tabs button[data-view]').forEach(b=>b.onclick=async()=>{document.querySelectorAll('.main-tabs button[data-view]').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;if(view==='stats'||view==='history')await loadSecondaryData();render()});",
    "document.querySelectorAll('.main-tabs button[data-view]').forEach(b=>b.onclick=()=>goView(b.dataset.view));",
    "tab routing",
)
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# project-ui.js — clean match list and four real detail sections
# ---------------------------------------------------------------------------
p = Path("frontend/project-ui.js")
s = p.read_text(encoding="utf-8")
s = exact(s, "      ${topStrip(rows)}\n", "", "remove raw top strip")
s = exact(
    s,
    "    const out=[\n      lazySection78e23('stats','📊','Statystyki zawodników','porównanie obok siebie'),\n      lazySection78e23('analytics','🧠','Player Analytics PRO','profil 0–100 · nie prawdopodobieństwo','PRO')\n    ];",
    "    const out=[];",
    "move stats out of lazy diagnostics",
)

detail_block = r'''
  function h2hHtml(m){
    const rows=[m?.h2h,m?.head_to_head,m?.head2head].find(Array.isArray)||[];
    if(!rows.length)return `<div class="match-h2h-empty"><b>Brak bezpośrednich danych H2H.</b><span>Nie tworzymy sztucznej historii. Gdy feed ma wcześniejsze bezpośrednie mecze, pojawią się tutaj.</span></div>`;
    return `<div class="match-h2h-list">${rows.slice(0,10).map(r=>{const a=r?.p1??r?.player1??r?.home??m.p1,b=r?.p2??r?.player2??r?.away??m.p2,score=r?.score??r?.result??r?.score_text??'—',date=r?.date??r?.scheduled_time??'';return `<article><small>${esc(date)}</small><b>${esc(a)} <i>vs</i> ${esc(b)}</b><strong>${esc(score)}</strong></article>`}).join('')}</div>`;
  }

  function detailHtml(m){
    const ss=top(m,3),best=ss[0],second=ss[1];
    const trust=Math.round(Math.min(100,(num(m.model_confidence)||0)+(m.early_hold_v7?.ready?4:0)));
    return `<div class="p751-detail-screen match-page">
      <header class="match-page-top">
        <button data-p751-close class="match-back" aria-label="Wróć">←</button>
        <div><span>${esc(tour(m))} · ${esc(m.tournament||'Turniej')}</span><b>Analiza meczu</b></div>
        <time>${esc(dt(m))} · ${esc(tm(m))}</time>
      </header>
      <section class="match-hero">
        <div class="match-hero-meta"><span>${esc(surf(m))}</span><span>${m.early_hold_v7?.ready?'PBP gotowe':'PBP N/D'}</span><span class="phase11-technical">Jakość ${trust}/100</span></div>
        <div class="match-hero-players"><b class="v762-player-link" role="link" tabindex="0">${esc(m.p1)}</b><span>vs</span><b class="v762-player-link" role="link" tabindex="0">${esc(m.p2)}</b></div>
      </section>
      <nav class="match-detail-tabs" aria-label="Sekcje analizy meczu">
        <button class="active" data-match-tab="summary" type="button">Podsumowanie</button>
        <button data-match-tab="path" type="button">Przebieg</button>
        <button data-match-tab="stats" type="button">Statystyki</button>
        <button data-match-tab="h2h" type="button">H2H</button>
      </nav>
      <section class="match-tab-panel active" data-match-panel="summary">
        <section class="match-decision">
          <article class="match-decision-main"><span>NAJLEPSZY TYP</span><b>${esc(best?.label||'Brak mocnego sygnału')}</b><strong>${best?signalText(best.value):'—'}</strong><small>${second?`Alternatywa: ${esc(second.label)} · ${signalText(second.value)}`:'Model nie wskazał mocnej alternatywy.'}</small></article>
          <article><span>OCENA</span><b>${(best?.value||0)>=85?'Bardzo mocny':(best?.value||0)>=72?'Mocny':'Umiarkowany'}</b><strong>${best?signalText(best.value):'—'}</strong></article>
          <article><span>DANE</span><b>${trust>=85?'Wysokie zaufanie':trust>=65?'Średnie zaufanie':'Ostrożnie'}</b><strong>${trust||'—'}%</strong></article>
        </section>
        <div class="match-summary-layout">
          <section class="match-page-primary"><div class="section-heading"><span>RYNKI</span><b>Co warto sprawdzić</b></div>${coreMarkets(m)}${jointBuilder78b(m)}</section>
          <aside class="match-page-side"><div class="section-heading"><span>KONTEKST</span><b>Kalibracja i jakość</b></div>${calibration78d(m)}<p class="p751-disclaimer">Sygnały są estymacjami analitycznymi, nie gwarancją wyniku.</p></aside>
        </div>
        <div class="phase11-technical match-technical-extras">${lazySections78e23(m)}</div>
      </section>
      <section class="match-tab-panel" data-match-panel="path"><div class="section-heading"><span>PLAYER DNA</span><b>Przewidywany przebieg meczu</b></div><div data-player-dna-tab-slot><div class="product-empty">Ładowanie przebiegu Player DNA…</div></div></section>
      <section class="match-tab-panel" data-match-panel="stats"><div class="section-heading"><span>ZAWODNICY</span><b>Statystyki i profile</b></div>${stats(m)}${analyticsPro76(m)}<div data-player-stats-tab-slot></div></section>
      <section class="match-tab-panel" data-match-panel="h2h"><div class="section-heading"><span>H2H</span><b>Bezpośrednie spotkania</b></div>${h2hHtml(m)}</section>
    </div>`;
  }

  function bindMatchDetailTabs(root){
    const buttons=[...root.querySelectorAll('[data-match-tab]')],panels=[...root.querySelectorAll('[data-match-panel]')];
    const activate=id=>{buttons.forEach(b=>b.classList.toggle('active',b.dataset.matchTab===id));panels.forEach(p=>p.classList.toggle('active',p.dataset.matchPanel===id));};
    buttons.forEach(b=>b.addEventListener('click',()=>activate(b.dataset.matchTab)));
    activate('summary');
  }
'''
s = regex_once(
    s,
    r"\n  function detailHtml\(m\)\{.*?\n  \}\n\n  let returnScroll=0;",
    "\n" + detail_block + "\n  let returnScroll=0;\n  let returnView='matches';",
    "detail screen",
    flags=re.S,
)
s = exact(
    s,
    "    returnScroll=window.scrollY||0;\n    route='match';",
    "    returnScroll=window.scrollY||0;\n    returnView=window.TENIS_AI_APP_NAV?.current?.()||'matches';\n    route='match';",
    "remember source view",
)
s = exact(s, "    bindLazySections78e23(app,m);", "    bindMatchDetailTabs(app);\n    bindLazySections78e23(app,m);", "bind detail tabs")
old_close = '''    route='matches';
    document.documentElement.dataset.tenisRoute='matches';
    document.dispatchEvent(new CustomEvent('tenis-ai:match-close'));
    renderMatches();
    setTimeout(()=>window.scrollTo({top:returnScroll,behavior:'auto'}),0);'''
new_close = '''    route=returnView==='matches'?'matches':returnView;
    document.documentElement.dataset.tenisRoute=route;
    document.dispatchEvent(new CustomEvent('tenis-ai:match-close'));
    if(returnView==='matches')renderMatches();
    else window.TENIS_AI_APP_NAV?.go?.(returnView);
    setTimeout(()=>window.scrollTo({top:returnScroll,behavior:'auto'}),0);'''
s = exact(s, old_close, new_close, "detail back route")
s = exact(
    s,
    "    const mapped=which==='history'?'history':which==='matches'?'matches':null;",
    "    const mapped=which==='signals'?'picks':['home','matches','picks','players','account','history'].includes(which)?which:null;",
    "project nav mapping",
)
admin_code = r'''
  function ensureAdminCenter(){
    const trigger=document.querySelector('#tenis-admin-center-open');
    if(!trigger)return;
    if(!isUiAdmin()){trigger.hidden=true;document.querySelector('#tenis-admin-center')?.remove();return;}
    trigger.hidden=false;
    let overlay=document.querySelector('#tenis-admin-center');
    if(!overlay){
      overlay=document.createElement('div');overlay.id='tenis-admin-center';overlay.className='tenis-admin-center';overlay.hidden=true;
      overlay.innerHTML=`<section class="tenis-admin-center-panel" role="dialog" aria-modal="true"><header><div><span>ADMIN</span><h2>Control Center</h2><p>Normalny interfejs zostaje prosty. Tutaj masz pełny dostęp techniczny.</p></div><button data-admin-close type="button">✕</button></header><div class="tenis-admin-grid">
        <button data-admin-go="matches">🎾<b>Mecze</b><small>Match Browser</small></button><button data-admin-go="picks">⚡<b>Typy</b><small>PLAYABLE</small></button><button data-admin-go="players">👤<b>Zawodnicy</b><small>Profile</small></button><button data-admin-action="symphony">🎼<b>Symfonia 2.0</b><small>Decyzje</small></button>
        <button data-admin-go="stats">📊<b>Statystyki</b><small>Modele i SHADOW</small></button><button data-admin-go="history">◷<b>Historia</b><small>Settlement</small></button><button data-admin-go="coupons">🧾<b>Kupony</b><small>Społeczność</small></button><button data-admin-action="community">👥<b>Użytkownicy</b><small>Moderacja</small></button>
        <button data-admin-action="neuro">🧠<b>NEURO</b><small>SHADOW</small></button><button data-admin-action="shadow">👻<b>SHADOW</b><small>Signal Center</small></button><button data-admin-action="mode">👁️<b>Tryb widoku</b><small>Prosty / techniczny</small></button><button data-admin-go="feedback">💬<b>Pomysły</b><small>Zgłoszenia</small></button>
      </div></section>`;
      document.body.append(overlay);
      overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('[data-admin-close]'))overlay.hidden=true;const go=e.target.closest('[data-admin-go]')?.dataset.adminGo;if(go){overlay.hidden=true;window.TENIS_AI_APP_NAV?.go?.(go);return}const a=e.target.closest('[data-admin-action]')?.dataset.adminAction;if(!a)return;if(a==='symphony')document.querySelector('#symphony-open')?.click();if(a==='community')document.querySelector('#community-hub-open')?.click();if(a==='neuro')document.querySelector('#neuro-open')?.click();if(a==='shadow')document.querySelector('#shadow-signals-open')?.click();if(a==='mode')setUiMode(document.documentElement.dataset.tenisUiMode==='technical'?'simple':'technical');if(a!=='mode')overlay.hidden=true;});
    }
    if(trigger.dataset.blueprintBound!=='1'){trigger.dataset.blueprintBound='1';trigger.addEventListener('click',()=>{ensureAdminCenter();const o=document.querySelector('#tenis-admin-center');if(o)o.hidden=false;});}
  }
'''
marker = "\n  function simplifyShell(){\n"
if marker not in s:
    raise SystemExit("simplifyShell marker missing")
s = s.replace(marker, "\n" + admin_code + "\n  function simplifyShell(){\n", 1)
s = exact(s, "    window.TENIS_AI_APPLY_META?.();", "    window.TENIS_AI_APPLY_META?.();\n    ensureAdminCenter();", "init admin center")
s = exact(
    s,
    "  window.addEventListener('tenis-ai-auth-change',()=>setTimeout(bindUiMode,0));",
    "  window.addEventListener('tenis-ai-auth-change',()=>setTimeout(()=>{bindUiMode();ensureAdminCenter();},0));",
    "admin auth sync",
)
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# Player DNA + Player Intelligence — place the data in the relevant tabs
# ---------------------------------------------------------------------------
p = Path("frontend/player-dna-shadow.js")
s = p.read_text(encoding="utf-8")
old = '''    const playerContext=currentScreen.querySelector('[data-pi851-detail],#pi85-detail');
    const verdict=currentScreen.querySelector('.p751-verdict');
    const matchup=currentScreen.querySelector('.p751-matchup');
    if(playerContext?.parentNode){
      playerContext.insertAdjacentElement('afterend',panel);
    }else if(verdict?.parentNode){
      verdict.parentNode.insertBefore(panel,verdict);
    }else if(matchup?.parentNode){
      matchup.insertAdjacentElement('afterend',panel);
    }'''
new = '''    const tabSlot=currentScreen.querySelector('[data-player-dna-tab-slot]');
    const playerContext=currentScreen.querySelector('[data-pi851-detail],#pi85-detail');
    const verdict=currentScreen.querySelector('.p751-verdict');
    const matchup=currentScreen.querySelector('.p751-matchup');
    if(tabSlot){
      tabSlot.replaceChildren(panel);
    }else if(playerContext?.parentNode){
      playerContext.insertAdjacentElement('afterend',panel);
    }else if(verdict?.parentNode){
      verdict.parentNode.insertBefore(panel,verdict);
    }else if(matchup?.parentNode){
      matchup.insertAdjacentElement('afterend',panel);
    }'''
s = exact(s, old, new, "Player DNA tab slot")
p.write_text(s, encoding="utf-8")

p = Path("frontend/player-intelligence-ui.js")
s = p.read_text(encoding="utf-8")
old = "  function injectDetail(m){const h=document.querySelector('.p751-detail-screen');if(!m||!h||h.querySelector('[data-pi851-detail]'))return;const x=details(m),head=h.querySelector('.dc87')||h.querySelector('.p751-matchup')||h.querySelector('.p751-detail-header');if(x)(head?head.insertAdjacentHTML('afterend',x):h.insertAdjacentHTML('afterbegin',x))}"
new = "  function injectDetail(m){const h=document.querySelector('.p751-detail-screen');if(!m||!h||h.querySelector('[data-pi851-detail]'))return;const x=details(m),slot=h.querySelector('[data-player-stats-tab-slot]'),head=h.querySelector('.dc87')||h.querySelector('.p751-matchup')||h.querySelector('.p751-detail-header');if(x){if(slot)slot.insertAdjacentHTML('beforeend',x);else(head?head.insertAdjacentHTML('afterend',x):h.insertAdjacentHTML('afterbegin',x))}}"
s = exact(s, old, new, "Player Intelligence tab slot")
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# PLAYABLE UI — keep the strict logic, retire duplicated presentation on Matches
# ---------------------------------------------------------------------------
p = Path("frontend/playable-ui.js")
s = p.read_text(encoding="utf-8")
s = regex_once(
    s,
    r"function patchTopStrip\(\)\{.*?\n\}",
    '''function patchTopStrip(){
  document.querySelector('#app [data-playable-top-v917="1"]')?.remove();
}''',
    "duplicate PLAYABLE top strip",
    flags=re.S,
)
s = exact(
    s,
    '''function patchHome(){
  document.querySelectorAll('#app .p751-match-card[data-p751-open]').forEach(patchCard);
  patchTopStrip();''',
    '''function patchHome(){
  const simple=document.documentElement.dataset.tenisUiMode!=='technical';
  if(simple){
    document.querySelectorAll('#app [data-v917-playable-card],#app [data-v917-match-total-preview]').forEach(el=>el.remove());
  }else{
    document.querySelectorAll('#app .p751-match-card[data-p751-open]').forEach(patchCard);
  }
  patchTopStrip();''',
    "simple PLAYABLE card cleanup",
)
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# style.css — final scoped visual owner for the agreed product
# ---------------------------------------------------------------------------
p = Path("frontend/style.css")
s = p.read_text(encoding="utf-8")
marker = "/* TENIS AI AGREED PRODUCT BLUEPRINT */"
if marker in s:
    s = s.split(marker, 1)[0].rstrip() + "\n"
css = r'''

/* TENIS AI AGREED PRODUCT BLUEPRINT */
html[data-tenis-product="blueprint"]{--bp-bg:#020711;--bp-panel:#071320;--bp-panel2:#0a1827;--bp-line:#163247;--bp-muted:#7f95ab;--bp-text:#f4f9ff;--bp-cyan:#29e6d2;--bp-lime:#a6f45a;--bp-green:#45e58d;background:var(--bp-bg)}
html[data-tenis-product="blueprint"] body{background:radial-gradient(circle at 50% -8%,rgba(41,230,210,.08),transparent 30%),var(--bp-bg);color:var(--bp-text)}
html[data-tenis-product="blueprint"] .product-shell{width:min(1180px,100%);margin:auto;padding:0 18px 86px}
html[data-tenis-product="blueprint"] .topbar{position:sticky;top:0;z-index:90;min-height:66px;padding:10px 0;border-bottom:1px solid rgba(41,230,210,.10);background:rgba(2,7,17,.88);backdrop-filter:blur(18px)}
html[data-tenis-product="blueprint"] .product-brand{gap:10px}html[data-tenis-product="blueprint"] .product-brand-symbol{width:38px;height:38px}html[data-tenis-product="blueprint"] .product-brand-wordmark{max-width:108px}html[data-tenis-product="blueprint"] .product-brand small{color:#627990;font-size:9px}
html[data-tenis-product="blueprint"][data-tenis-ui-mode="simple"] #symphony-open,html[data-tenis-product="blueprint"][data-tenis-ui-mode="simple"] #neuro-open,html[data-tenis-product="blueprint"][data-tenis-ui-mode="simple"] #shadow-signals-open,html[data-tenis-product="blueprint"][data-tenis-ui-mode="simple"] #community-hub-open{display:none!important}
html[data-tenis-product="blueprint"] #tenis-admin-center-open{display:none}html[data-tenis-product="blueprint"][data-tenis-role="admin"] #tenis-admin-center-open{display:inline-flex}html[data-tenis-product="blueprint"] .legacy-view-hook{display:none!important}
html[data-tenis-product="blueprint"] .page-head{padding:22px 2px 12px;min-height:auto}html[data-tenis-product="blueprint"] .page-head>div:first-child{max-width:720px}html[data-tenis-product="blueprint"] .page-head span{color:var(--bp-lime);letter-spacing:.16em;font-size:9px}html[data-tenis-product="blueprint"] .page-head h1{margin:5px 0 5px;font-size:clamp(30px,5vw,48px);letter-spacing:-.05em}html[data-tenis-product="blueprint"] .page-head p{margin:0;color:var(--bp-muted);font-size:12px;line-height:1.5}
html[data-tenis-product="blueprint"] .technical-status{display:none!important}html[data-tenis-product="blueprint"][data-tenis-role="admin"][data-tenis-ui-mode="technical"] .technical-status{display:flex!important}
html[data-tenis-product="blueprint"] #player-search-shell,html[data-tenis-product="blueprint"] #player-profile-panel{display:none!important}html[data-tenis-product="blueprint"][data-tenis-view="players"] #player-search-shell{display:block!important}html[data-tenis-product="blueprint"][data-tenis-view="players"] #player-profile-panel:not([hidden]){display:block!important}
html[data-tenis-product="blueprint"] #community-live-stats{display:none!important}html[data-tenis-product="blueprint"][data-tenis-view="home"] #community-live-stats{display:grid!important;margin:0 0 14px!important;padding:10px 12px!important;border-radius:16px!important;background:#06131f!important;border-color:rgba(41,230,210,.12)!important}
html[data-tenis-product="blueprint"] .main-tabs{position:sticky;top:74px;z-index:70;display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin:0 0 16px;padding:6px;border:1px solid rgba(127,149,171,.14);border-radius:18px;background:rgba(5,14,25,.92);backdrop-filter:blur(16px)}
html[data-tenis-product="blueprint"] .main-tabs button:not(.legacy-view-hook){display:flex;align-items:center;justify-content:center;gap:7px;min-height:44px;border:0;border-radius:13px;background:transparent;color:#7d93aa;font-weight:850}html[data-tenis-product="blueprint"] .main-tabs button.active:not(.legacy-view-hook){color:#001b17;background:linear-gradient(135deg,var(--bp-cyan),var(--bp-lime));box-shadow:0 0 24px rgba(41,230,210,.10)}
html[data-tenis-product="blueprint"] #app{display:block;min-height:240px}html[data-tenis-product="blueprint"] .app-content{padding-bottom:12px}
.product-home{display:grid;gap:14px}.product-home-hero{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(300px,.85fr);gap:18px;padding:24px;border:1px solid rgba(41,230,210,.17);border-radius:24px;background:linear-gradient(135deg,rgba(41,230,210,.055),transparent 44%),linear-gradient(180deg,#091827,#06111e);box-shadow:0 18px 60px rgba(0,0,0,.18)}.product-home-hero>div:first-child>span,.product-home-section header span,.product-picks-hero span,.product-players-intro>span,.product-account-card>div>span{color:var(--bp-lime);font-size:9px;font-weight:950;letter-spacing:.16em}.product-home-hero h2,.product-picks-hero h2,.product-players-intro h2,.product-account-card h2{margin:6px 0 8px;font-size:clamp(26px,5vw,42px);letter-spacing:-.05em}.product-home-hero p,.product-picks-hero p,.product-players-intro p{margin:0;color:var(--bp-muted);font-size:13px;line-height:1.55}.product-home-kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.product-home-kpis>div{display:grid;align-content:center;min-height:82px;padding:11px 13px;border:1px solid rgba(127,149,171,.12);border-radius:15px;background:#071421}.product-home-kpis small{color:#6e8499;font-size:9px}.product-home-kpis b{color:var(--bp-text);font-size:24px;letter-spacing:-.04em}.product-home-kpis span{color:#637a90;font-size:9px}
.product-launch-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.product-launch-grid button{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:11px;min-height:88px;padding:15px;border:1px solid rgba(127,149,171,.13);border-radius:18px;background:#071320;text-align:left}.product-launch-grid button>span{font-size:24px}.product-launch-grid button div{display:grid;gap:3px}.product-launch-grid button b{color:#eff8ff;font-size:14px}.product-launch-grid button small{color:#70869b;font-size:9px;line-height:1.35}.product-launch-grid button i{color:var(--bp-cyan);font-style:normal}.product-launch-grid .admin-launch{border-color:rgba(166,244,90,.20);background:linear-gradient(135deg,rgba(166,244,90,.045),#071320)}
.product-home-section{padding:16px;border:1px solid rgba(127,149,171,.12);border-radius:20px;background:#06121f}.product-home-section>header{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:10px}.product-home-section header>div{display:grid;gap:2px}.product-home-section header b{font-size:18px}.product-home-section header button{border:0;background:none;color:var(--bp-cyan);font-size:10px}.product-home-picks{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.product-home-picks>button,.product-pick-row{position:relative;display:grid;grid-template-columns:1fr auto;gap:8px;padding:13px;border:1px solid rgba(127,149,171,.12);border-radius:16px;background:#071421;text-align:left}.product-home-picks button>div,.product-pick-row>div{display:grid;gap:4px;min-width:0}.product-home-picks small,.product-pick-row small{color:#657c92;font-size:8px}.product-home-picks b,.product-pick-row b{color:#eef8ff;font-size:12px;white-space:normal}.product-home-picks b i,.product-pick-row b i{color:#536b82;font-size:8px;font-style:normal}.product-home-picks span,.product-pick-row span{color:#8ca2b7;font-size:9px}.product-home-picks strong,.product-pick-row strong{align-self:center;color:var(--bp-lime);font-size:20px}.product-home-picks em,.product-pick-row em{grid-column:2;color:#668c7a;font-size:7px;font-style:normal;text-align:right}
.product-picks-page{display:grid;gap:12px}.product-picks-hero{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;padding:20px;border:1px solid rgba(41,230,210,.15);border-radius:22px;background:linear-gradient(135deg,rgba(41,230,210,.05),transparent 45%),#071421}.product-picks-hero>div{max-width:680px}.product-picks-hero button{min-height:42px;padding:0 13px;border:1px solid rgba(41,230,210,.18);border-radius:13px;background:#071c25;color:#bdfbf1;font-weight:850}.product-picks-list{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.product-pick-row{min-height:96px}.product-empty{display:grid;gap:5px;padding:18px;border:1px dashed rgba(127,149,171,.17);border-radius:16px;color:#72889e;background:#06111d}.product-empty b{color:#d7e7f4}.product-empty span{font-size:10px;line-height:1.45}
.product-players-intro{padding:22px;border:1px solid rgba(41,230,210,.14);border-radius:22px;background:linear-gradient(135deg,rgba(41,230,210,.05),transparent 44%),#071421}.product-account-page{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,.65fr);gap:12px}.product-account-card{display:flex;align-items:center;gap:16px;padding:22px;border:1px solid rgba(41,230,210,.14);border-radius:22px;background:#071421}.product-account-avatar{display:grid!important;place-items:center;width:68px;height:68px;border-radius:20px;background:linear-gradient(135deg,var(--bp-cyan),var(--bp-lime));color:#001a17;font-size:30px;font-weight:950}.product-account-card p{margin:0;color:var(--bp-muted)}.product-account-actions{display:grid;gap:8px}.product-account-actions button{display:flex;justify-content:space-between;align-items:center;min-height:58px;padding:0 14px;border:1px solid rgba(127,149,171,.13);border-radius:16px;background:#071320;color:#e9f5ff;font-weight:850}.product-account-actions i{color:var(--bp-cyan);font-style:normal}
html[data-tenis-product="blueprint"][data-tenis-view="matches"] .signal-spotlight,html[data-tenis-product="blueprint"][data-tenis-view="matches"] [data-playable-top-v917="1"]{display:none!important}html[data-tenis-product="blueprint"][data-tenis-ui-mode="simple"] [data-v917-playable-card],html[data-tenis-product="blueprint"][data-tenis-ui-mode="simple"] [data-v917-match-total-preview]{display:none!important}.match-browser{display:grid;gap:12px}.match-browser-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;padding:4px 1px}.match-browser-head>div:first-child{display:grid}.match-browser-head>div:first-child span{color:var(--bp-lime);font-size:8px;font-weight:950;letter-spacing:.14em}.match-browser-head>div:first-child b{font-size:18px}.match-filter-row{display:flex;gap:5px;overflow-x:auto;scrollbar-width:none}.match-filter-row::-webkit-scrollbar{display:none}.match-filter-row button{white-space:nowrap;min-height:34px;padding:0 11px;border:1px solid rgba(127,149,171,.13);border-radius:999px;background:#071421;color:#8097ac;font-size:9px;font-weight:850}.match-filter-row button.active{border-color:rgba(41,230,210,.25);background:rgba(41,230,210,.08);color:#bdfbf1}.match-group{border:1px solid rgba(127,149,171,.11)!important;border-radius:18px!important;background:#06111d!important;overflow:hidden}.match-group>header{padding:11px 13px!important;border-bottom:1px solid rgba(127,149,171,.09)!important}.match-grid{gap:7px!important;padding:7px!important}.p751-match-card.match-tile{border:1px solid rgba(127,149,171,.11)!important;border-radius:15px!important;background:#071421!important;box-shadow:none!important}.match-tile-main{gap:10px!important}.match-tile-score strong{color:var(--bp-lime)!important}
.match-page{max-width:1080px;margin:0 auto}.match-page-top{position:sticky;top:0;z-index:84;background:rgba(2,7,17,.94)!important;backdrop-filter:blur(16px);border-bottom-color:rgba(41,230,210,.10)!important}.match-hero{margin-top:8px!important;border-color:rgba(41,230,210,.15)!important;background:linear-gradient(135deg,rgba(41,230,210,.05),transparent 46%),#071421!important}.match-detail-tabs{position:sticky;top:64px;z-index:82;display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin:8px 0 12px;padding:5px;border:1px solid rgba(127,149,171,.13);border-radius:15px;background:rgba(5,14,25,.94);backdrop-filter:blur(14px)}.match-detail-tabs button{min-height:40px;border:0;border-radius:11px;background:transparent;color:#7890a6;font-size:10px;font-weight:900}.match-detail-tabs button.active{background:linear-gradient(135deg,var(--bp-cyan),var(--bp-lime));color:#001a17}.match-tab-panel{display:none}.match-tab-panel.active{display:block}.match-summary-layout{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(250px,.5fr);gap:11px}.match-tab-panel>.section-heading{margin:10px 1px}.match-tab-panel .p751-acc{border-color:rgba(127,149,171,.12)!important;background:#071421!important}.match-tab-panel[data-match-panel="path"] [data-player-dna-tab-slot],.match-tab-panel[data-match-panel="stats"] [data-player-stats-tab-slot]{display:grid;gap:10px}.match-h2h-list{display:grid;gap:7px}.match-h2h-list article{display:grid;grid-template-columns:100px 1fr auto;align-items:center;gap:10px;padding:12px;border:1px solid rgba(127,149,171,.12);border-radius:14px;background:#071421}.match-h2h-list small{color:#657d92}.match-h2h-list b{font-size:12px}.match-h2h-list b i{color:#587086;font-size:8px;font-style:normal}.match-h2h-list strong{color:var(--bp-lime)}.match-h2h-empty{display:grid;gap:6px;padding:18px;border:1px dashed rgba(127,149,171,.16);border-radius:16px;background:#06111d}.match-h2h-empty span{color:#71879c;font-size:10px;line-height:1.5}
.tenis-admin-center{position:fixed;inset:0;z-index:10050;display:grid;place-items:center;padding:18px;background:rgba(1,5,12,.82);backdrop-filter:blur(16px)}.tenis-admin-center[hidden]{display:none!important}.tenis-admin-center-panel{width:min(760px,100%);max-height:88vh;overflow:auto;padding:18px;border:1px solid rgba(166,244,90,.20);border-radius:24px;background:linear-gradient(180deg,#091827,#05101b);box-shadow:0 28px 90px rgba(0,0,0,.58)}.tenis-admin-center-panel>header{display:flex;justify-content:space-between;gap:14px;padding-bottom:14px;border-bottom:1px solid rgba(127,149,171,.11)}.tenis-admin-center-panel>header span{color:var(--bp-lime);font-size:8px;font-weight:950;letter-spacing:.16em}.tenis-admin-center-panel h2{margin:3px 0;font-size:28px}.tenis-admin-center-panel p{margin:0;color:#7890a5;font-size:10px}.tenis-admin-center-panel>header button{width:38px;height:38px;padding:0;border:1px solid rgba(127,149,171,.13);border-radius:12px;background:#071421}.tenis-admin-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding-top:15px}.tenis-admin-grid button{display:grid;align-content:center;justify-items:start;gap:4px;min-height:102px;padding:13px;border:1px solid rgba(127,149,171,.12);border-radius:15px;background:#071421;text-align:left;font-size:20px}.tenis-admin-grid b{font-size:11px;color:#eef8ff}.tenis-admin-grid small{font-size:8px;color:#70879c}
@media(max-width:760px){html[data-tenis-product="blueprint"] .product-shell{padding:0 10px 90px}html[data-tenis-product="blueprint"] .topbar{min-height:54px;padding:7px 0}html[data-tenis-product="blueprint"] .product-brand-symbol{width:31px;height:31px}html[data-tenis-product="blueprint"] .product-brand small{display:none}html[data-tenis-product="blueprint"] .topbar-actions{gap:5px}html[data-tenis-product="blueprint"] .topbar-action,html[data-tenis-product="blueprint"] .account-button,html[data-tenis-product="blueprint"] .topbar-icon{width:36px;min-width:36px;min-height:36px;padding:0;justify-content:center}html[data-tenis-product="blueprint"] .topbar-action>b,html[data-tenis-product="blueprint"] .topbar-action>span>*,html[data-tenis-product="blueprint"] .account-button-copy{display:none!important}html[data-tenis-product="blueprint"] .page-head{padding:14px 2px 9px}html[data-tenis-product="blueprint"] .page-head h1{font-size:30px}html[data-tenis-product="blueprint"] .page-head p{font-size:10px}html[data-tenis-product="blueprint"] .page-sync{display:none}html[data-tenis-product="blueprint"] .main-tabs{position:fixed;left:8px;right:8px;bottom:8px;top:auto;z-index:120;margin:0;padding:5px;border-radius:18px;box-shadow:0 18px 44px rgba(0,0,0,.55)}html[data-tenis-product="blueprint"] .main-tabs button:not(.legacy-view-hook){display:grid;place-items:center;align-content:center;gap:2px;min-width:0;min-height:54px;padding:4px 2px}html[data-tenis-product="blueprint"] .main-tabs button span{font-size:16px}html[data-tenis-product="blueprint"] .main-tabs button b{font-size:8px}.product-home-hero{grid-template-columns:1fr;padding:17px}.product-home-kpis{grid-template-columns:repeat(4,1fr);gap:5px}.product-home-kpis>div{min-height:64px;padding:8px}.product-home-kpis b{font-size:19px}.product-home-kpis span{font-size:7px}.product-launch-grid{grid-template-columns:repeat(2,1fr)}.product-launch-grid button{min-height:76px;padding:11px}.product-launch-grid button>span{font-size:20px}.product-home-picks{display:flex;overflow-x:auto;gap:7px;scroll-snap-type:x proximity;scrollbar-width:none}.product-home-picks>button{flex:0 0 min(82vw,310px);scroll-snap-align:start}.product-picks-hero{display:grid;padding:16px}.product-picks-list{grid-template-columns:1fr}.product-account-page{grid-template-columns:1fr}.match-summary-layout{grid-template-columns:1fr}.match-detail-tabs{top:54px;overflow-x:auto}.match-detail-tabs button{font-size:9px}.tenis-admin-grid{grid-template-columns:repeat(2,1fr)}.tenis-admin-grid button{min-height:84px}.match-h2h-list article{grid-template-columns:1fr auto}.match-h2h-list small{grid-column:1/-1}}
@media(max-width:430px){.product-home-kpis{grid-template-columns:repeat(2,1fr)}.product-home-hero h2{font-size:32px}.product-launch-grid button small{font-size:8px}.product-pick-row strong{font-size:18px}.match-detail-tabs{grid-template-columns:repeat(4,minmax(82px,1fr))}.tenis-admin-center-panel{padding:13px}.tenis-admin-grid{gap:6px}}
'''
p.write_text(s.rstrip() + css + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# regression contract
# ---------------------------------------------------------------------------
p = Path("tests/test_clean_product_ui.py")
s = p.read_text(encoding="utf-8")
addition = r'''

def test_agreed_product_blueprint_is_the_visible_navigation_contract():
    assert 'data-tenis-product="blueprint"' in INDEX
    assert 'data-tenis-view="home"' in INDEX
    for view, label in (("home","Start"),("matches","Mecze"),("picks","Typy"),("players","Zawodnicy"),("account","Konto")):
        assert f'data-view="{view}"' in INDEX
        assert f'<b>{label}</b>' in INDEX
    assert 'class="legacy-view-hook" data-view="stats"' in INDEX
    assert 'id="tenis-admin-center-open"' in INDEX


def test_agreed_product_blueprint_has_real_product_routes():
    assert "let view='home';" in APP
    assert 'function renderProductHome()' in APP
    assert 'function renderProductPicks()' in APP
    assert 'function renderProductPlayers()' in APP
    assert 'function renderProductAccount()' in APP
    assert 'window.TENIS_AI_APP_NAV=Object.freeze' in APP


def test_match_detail_uses_agreed_four_section_information_architecture():
    for tab in ('summary','path','stats','h2h'):
        assert f'data-match-tab="{tab}"' in PROJECT_UI
        assert f'data-match-panel="{tab}"' in PROJECT_UI
    for label in ('Podsumowanie','Przebieg','Statystyki','H2H'):
        assert label in PROJECT_UI
    assert '${topStrip(rows)}' not in PROJECT_UI
    assert 'data-player-dna-tab-slot' in PROJECT_UI
    assert 'data-player-stats-tab-slot' in PROJECT_UI


def test_blueprint_keeps_one_visual_owner_and_role_aware_admin_center():
    assert 'TENIS AI AGREED PRODUCT BLUEPRINT' in STYLE
    assert '.legacy-view-hook{display:none!important}' in STYLE
    assert '[data-tenis-role="admin"] #tenis-admin-center-open' in STYLE
    assert '.match-detail-tabs' in STYLE
    assert '.product-home-hero' in STYLE
'''
if "def test_agreed_product_blueprint_is_the_visible_navigation_contract()" not in s:
    p.write_text(s.rstrip() + addition + "\n", encoding="utf-8")
