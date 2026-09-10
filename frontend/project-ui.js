/* Tenis AI — canonical product controller 2026-09-10
   Fresh UI over the existing data/model engine. No model math lives here. */
(()=>{
  'use strict';

  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const num=v=>finite(v)?Number(v):null;
  const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
  const ui={view:'home',focus:'all',lastMatch:null};
  const MODE_KEY='tenis-ai-product-ui-mode';

  const COPY={
    home:['DZISIAJ','Start','Najważniejsze informacje z modeli, Symfonii i aktualnej oferty — podane po ludzku.'],
    matches:['DZISIAJ','Mecze','Aktualne spotkania. Otwórz mecz, żeby zobaczyć pełną analizę i rynki.'],
    picks:['SUPERBET','Typy','Finalne PLAYABLE zweryfikowane z bieżącą ofertą operatora.'],
    players:['PLAYER DNA','Zawodnicy','Wyszukaj zawodnika i przejdź do formy, serwisu, returnu i profilu DNA.'],
    stats:['WYNIKI','Statystyki','Skuteczność, jakość danych, modele i warstwy SHADOW.'],
    history:['ARCHIWUM','Historia','Rozliczone spotkania i wcześniejsze sygnały.'],
    coupons:['SPOŁECZNOŚĆ','Kupony','Kupony testerów i zapisane typy.'],
    feedback:['ROZWÓJ','Pomysły','Zgłoszenia i pomysły do aplikacji.']
  };

  function role(){
    return String(document.documentElement.dataset.tenisRole||window.tenisAIAccount?.profile?.role||window.tenisAICommunityHub?.profile?.role||'user').toLowerCase();
  }
  function isAdmin(){return role()==='admin'}
  function syncMode(){
    let mode='simple';
    if(isAdmin()){
      try{mode=localStorage.getItem(MODE_KEY)==='technical'?'technical':'simple'}catch{}
    }
    document.documentElement.dataset.tenisUiMode=mode;
    document.documentElement.dataset.tenisStatsMode=mode==='technical'?'pro':'simple';
    const b=$('#tenis-ui-mode-toggle');
    if(b){b.setAttribute('aria-pressed',mode==='technical'?'true':'false');const s=$('small',b);if(s)s.textContent=mode==='technical'?'Techniczny':'Prosty'}
    document.documentElement.dataset.tenisRole=role();
    return mode;
  }
  function toggleMode(){
    if(!isAdmin())return;
    const next=document.documentElement.dataset.tenisUiMode==='technical'?'simple':'technical';
    try{localStorage.setItem(MODE_KEY,next)}catch{}
    syncMode();
    renderProduct();
  }

  function allRows(){
    try{return Array.isArray(all)?all.filter(Boolean):[]}catch{return []}
  }
  function currentRows(){
    let rows=[];
    try{rows=typeof filteredReady==='function'?filteredReady():allRows().filter(x=>x?.model_ready)}catch{rows=allRows()}
    try{if(typeof filter!=='undefined'&&filter!=='all'&&typeof tourKey==='function')rows=rows.filter(m=>tourKey(m)===filter)}catch{}
    const now=Date.now();
    if(ui.focus==='soon')rows=rows.filter(m=>{const t=Date.parse(m?.scheduled_time||'');return Number.isFinite(t)&&t>=now&&t<=now+2*3600000});
    if(ui.focus==='strong')rows=rows.filter(m=>(bestSignal(m)?.value||0)>=80);
    if(ui.focus==='playable')rows=rows.filter(m=>playable(m,1).length>0);
    if(ui.focus==='pbp')rows=rows.filter(m=>m?.early_hold_v7?.ready||m?.pbp_ready===true||m?.point_tape_ready===true);
    return rows.sort((a,b)=>Date.parse(a?.scheduled_time||0)-Date.parse(b?.scheduled_time||0));
  }
  function rowKey(m){return String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'))}
  function findMatch(raw){
    let k=String(raw??'');
    try{k=decodeURIComponent(k)}catch{}
    k=k.replace(/^m:/,'').replace(/^id:/,'');
    return allRows().find(m=>rowKey(m)===k||String(m?.id??'')===k||String(m?.match_id??'')===k||`m:${rowKey(m)}`===String(raw))||null;
  }
  function when(m){
    const d=new Date(m?.scheduled_time||'');
    if(!Number.isFinite(d.getTime()))return {time:'—',date:'',full:''};
    return {time:d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}),date:d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'}),full:d.toLocaleString('pl-PL',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})};
  }
  function tour(m){
    const t=String(m?.tour||'').toLowerCase();
    if(t.includes('chall'))return 'CH';if(t.includes('itf'))return 'ITF';if(t.includes('wta'))return 'WTA';if(t.includes('atp'))return 'ATP';return String(m?.tour||'TENIS').toUpperCase();
  }
  function playable(m,limit=50){
    try{return window.TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,limit)||[]}catch{return []}
  }
  function valueOf(s){return num(s?.operator_model_probability??s?.v??s?.final_score??s?.adaptive_prod_score??s?.score??s?.current)}
  function rawSignals(m,limit=60){
    const api=window.TENIS_AI_MODEL_API;let rows=[];
    try{rows=typeof api?.signals==='function'?(api.signals(m,limit)||[]):typeof api?.allSignals==='function'?(api.allSignals(m)||[]):[]}catch{}
    if(rows.length)return rows.map(s=>({...s,__value:valueOf(s)})).filter(s=>s.__value!=null).sort((a,b)=>b.__value-a.__value).slice(0,limit);
    const fallback=[];
    const add=(label,obj)=>{if(!obj||typeof obj!=='object')return;Object.entries(obj).forEach(([pick,v])=>{if(finite(v))fallback.push({label:`${label}: ${pick}`,pick,v:Number(v),__value:Number(v)})})};
    add('Mecz',m?.match_win);add('1. set',m?.first_set_win);add('2. set',m?.second_set_win);add('Sety',m?.total_sets);
    Object.entries(m?.over_under||{}).forEach(([line,x])=>{if(finite(x?.over))fallback.push({label:`1. set OVER ${line}`,v:Number(x.over),__value:Number(x.over)});if(finite(x?.under))fallback.push({label:`1. set UNDER ${line}`,v:Number(x.under),__value:Number(x.under)})});
    Object.entries(m?.match_over_under||{}).forEach(([line,x])=>{if(finite(x?.over))fallback.push({label:`Mecz OVER ${line}`,v:Number(x.over),__value:Number(x.over)});if(finite(x?.under))fallback.push({label:`Mecz UNDER ${line}`,v:Number(x.under),__value:Number(x.under)})});
    return fallback.sort((a,b)=>b.__value-a.__value).slice(0,limit);
  }
  function bestSignal(m){
    const p=playable(m,1)[0];
    if(p&&valueOf(p)!=null)return {label:p.label||p.displayPick||p.pick||p.key||'Typ PLAYABLE',value:valueOf(p),playable:true,row:p};
    const r=rawSignals(m,1)[0];
    return r?{label:r.label||r.displayPick||r.pick||r.key||'Sygnał modelu',value:valueOf(r)??r.__value,playable:false,row:r}:null;
  }
  function score(v){return v==null?'—':`${Math.round(v)}/100`}

  function syncChrome(){
    const copy=COPY[ui.view]||COPY.home;
    document.documentElement.dataset.tenisView=ui.view;
    document.documentElement.dataset.tenisRoute=ui.view;
    const ids=['#page-kicker','#page-title','#page-subtitle'];ids.forEach((id,i)=>{const el=$(id);if(el)el.textContent=copy[i]});
    const top=$('#topbar-section');if(top)top.textContent=copy[1];
    $$('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===ui.view));
    const search=$('#player-search-shell');if(search)search.hidden=!['matches','players'].includes(ui.view);
    const profile=$('#player-profile-panel');if(profile&&ui.view!=='players'&&ui.view!=='matches')profile.hidden=true;
    const controls=$('#match-controls');if(controls)controls.hidden=ui.view!=='matches';
    $$('#focus-filters [data-focus]').forEach(b=>b.classList.toggle('active',b.dataset.focus===ui.focus));
    syncMode();
  }

  function statsFor(rows){
    const now=Date.now();
    const soon=rows.filter(m=>{const t=Date.parse(m?.scheduled_time||'');return Number.isFinite(t)&&t>=now&&t<=now+2*3600000}).length;
    const play=rows.filter(m=>playable(m,1).length).length;
    const strongest=rows.map(bestSignal).filter(Boolean).reduce((a,x)=>Math.max(a,x.value||0),0);
    return {matches:rows.length,soon,play,strongest};
  }

  function topPicks(rows,n=3,onlyPlayable=false){
    return rows.map(m=>({m,s:onlyPlayable?(()=>{const p=playable(m,1)[0];return p?{label:p.label||p.pick||p.key||'PLAYABLE',value:valueOf(p),playable:true,row:p}:null})():bestSignal(m)}))
      .filter(x=>x.s&&x.s.value!=null&&(!onlyPlayable||x.s.playable)).sort((a,b)=>b.s.value-a.s.value).slice(0,n);
  }

  function renderHome(){
    const app=$('#app'),rows=currentRows(),k=statsFor(rows),tops=topPicks(rows,3,false);
    app.innerHTML=`
      <div class="home-grid">
        <section class="hero-card">
          <span class="hero-kicker">TENIS AI · DZISIAJ</span>
          <h2>Mniej szumu. Więcej konkretu przed meczem.</h2>
          <p>Mecze, sygnały modeli, Player DNA, Symfonia 2.0 i finalne PLAYABLE są w jednym miejscu. Warstwa użytkowa pokazuje najpierw to, co ma znaczenie.</p>
          <div class="hero-actions"><button class="go-primary" data-view="matches">Przejdź do meczów</button><button class="go-secondary" data-view="picks">Zobacz PLAYABLE</button>${isAdmin()?'<button class="go-secondary" data-admin-mode>Tryb techniczny</button>':''}</div>
        </section>
        <div class="kpi-stack">
          <article class="kpi"><span>Aktualne mecze</span><b>${k.matches}</b><small>z danymi modelu</small></article>
          <article class="kpi"><span>Najbliższe 2 h</span><b>${k.soon}</b><small>do rozpoczęcia</small></article>
          <article class="kpi accent"><span>PLAYABLE</span><b>${k.play}</b><small>bieżący Superbet</small></article>
          <article class="kpi accent"><span>Najmocniejszy</span><b>${k.strongest?Math.round(k.strongest):'—'}</b><small>score / 100</small></article>
        </div>
      </div>
      <section class="section-block">
        <header class="section-head"><div><small>NAJMOCNIEJSZE TERAZ</small><h2>Top sygnały</h2></div><button class="text-link" data-view="picks">Wszystkie typy →</button></header>
        <div class="top-picks">${tops.length?tops.map(({m,s})=>topPickHtml(m,s)).join(''):'<div class="product-empty">Brak gotowych sygnałów dla aktualnych meczów.</div>'}</div>
      </section>
      <div class="quick-grid">
        <button class="quick-card" data-view="players"><span>◎</span><div><b>Player DNA</b><small>profile zawodników</small></div></button>
        <button class="quick-card" data-symphony><span>♫</span><div><b>Symfonia 2.0</b><small>wspólna analiza</small></div></button>
        <button class="quick-card" data-view="stats"><span>⌁</span><div><b>Wyniki modeli</b><small>skuteczność i trendy</small></div></button>
        <button class="quick-card" data-community><span>♧</span><div><b>Społeczność</b><small>testerzy i kupony</small></div></button>
      </div>`;
  }

  function topPickHtml(m,s){
    const t=when(m);return `<button class="top-pick" data-open-match="${esc(encodeURIComponent(rowKey(m)))}"><div><small>${esc(tour(m))} · ${esc(t.time)} · ${esc(m?.surface||'')}</small><h3>${esc(m?.p1||'—')} <i>vs</i> ${esc(m?.p2||'—')}</h3><p>${esc(s.label)}</p></div><strong>${score(s.value)}</strong><em>${s.playable?'SUPERBET ✓':'MODEL'}</em></button>`;
  }

  function updateTourCounts(){
    const rows=(()=>{try{return typeof filteredReady==='function'?filteredReady():allRows()}catch{return allRows()}})();
    const counts={all:rows.length,atp:0,wta:0,challenger:0,itf:0};
    rows.forEach(m=>{let k='';try{k=typeof tourKey==='function'?tourKey(m):String(m?.tour||'').toLowerCase()}catch{};if(k in counts)counts[k]++});
    $$('#tour-nav [data-filter]').forEach(b=>{const c=$('.count',b);if(c)c.textContent=counts[b.dataset.filter]??0;b.classList.toggle('active',(typeof filter!=='undefined'?filter:'all')===b.dataset.filter)});
    const matched=$('#matched');if(matched)matched.textContent=`Dopasowane: ${rows.length} / ${allRows().length}`;
  }

  function renderMatches(){
    const app=$('#app'),rows=currentRows();updateTourCounts();
    app.innerHTML=`<div class="match-page-head"><p>${rows.length} ${rows.length===1?'spotkanie':'spotkań'} w aktualnym widoku</p><button class="text-link" data-view="picks">Top PLAYABLE →</button></div>
      <div class="match-list">${rows.length?rows.map(matchCardHtml).join(''):'<div class="match-empty"><b>Brak meczów dla tego filtra.</b><br>Rdzeń danych nie został usunięty — zmień filtr albo odśwież dane.</div>'}</div>`;
  }
  function matchCardHtml(m){
    const t=when(m),s=bestSignal(m);return `<button class="match-card-new" data-open-match="${esc(encodeURIComponent(rowKey(m)))}">
      <div class="match-clock"><b>${esc(t.time)}</b><small>${esc(t.date)}</small></div>
      <div class="match-main-new"><small>${esc(tour(m))} · ${esc(m?.tournament||'Turniej')} · ${esc(m?.surface||'')}</small><h3>${esc(m?.p1||'—')} <i>vs</i> ${esc(m?.p2||'—')}</h3></div>
      <div class="match-signal ${s?.playable?'playable':''}"><small>${s?.playable?'PLAYABLE · SUPERBET':'NAJMOCNIEJSZY SYGNAŁ'}</small><b>${esc(s?.label||'Brak gotowego sygnału')}</b><strong>${score(s?.value)}</strong></div>
      <span class="match-arrow">›</span></button>`;
  }

  function renderPicks(){
    const app=$('#app'),matches=(()=>{try{return typeof filteredReady==='function'?filteredReady():allRows()}catch{return allRows()}})();
    const rows=[];
    matches.forEach(m=>playable(m,30).forEach(s=>{const v=valueOf(s);if(v!=null)rows.push({m,s,v})}));
    rows.sort((a,b)=>b.v-a.v);
    const matchCount=new Set(rows.map(x=>rowKey(x.m))).size;
    const strong=rows.filter(x=>x.v>=80).length;
    app.innerHTML=`
      <div class="picks-summary"><div class="mini-kpi"><span>PLAYABLE</span><b>${rows.length}</b></div><div class="mini-kpi"><span>Mecze</span><b>${matchCount}</b></div><div class="mini-kpi"><span>80+</span><b>${strong}</b></div></div>
      <div class="pick-list">${rows.length?rows.slice(0,100).map(({m,s,v})=>`<button class="pick-row" data-open-match="${esc(encodeURIComponent(rowKey(m)))}"><div class="pick-match"><small>${esc(tour(m))} · ${esc(when(m).time)} · ${esc(m?.tournament||'')}</small><b>${esc(m?.p1||'—')} vs ${esc(m?.p2||'—')}</b></div><div class="pick-choice"><small>SUPERBET PLAYABLE</small><b>${esc(s?.label||s?.displayPick||s?.pick||s?.key||'Typ')}</b></div><div class="pick-score"><strong>${score(v)}</strong><small>OFERTA ✓</small></div></button>`).join(''):'<div class="product-empty"><b>Brak PLAYABLE w tej chwili.</b><br>Modele i RAW nadal pracują. Ta sekcja pokazuje wyłącznie finalne typy obecne w aktualnej ofercie Superbet.</div>'}</div>`;
  }

  function renderPlayers(){
    const app=$('#app');app.innerHTML=`<section class="section-block"><header class="section-head"><div><small>PLAYER DNA</small><h2>Profil zawodnika</h2></div></header><div class="product-empty">Użyj wyszukiwarki powyżej. Zostają wszystkie dotychczasowe dane Player Intelligence, trendy, serwis/return, nawierzchnia i warstwy Player DNA.</div></section>`;
  }

  function renderLegacy(name){
    const app=$('#app');
    try{
      if(name==='stats'&&typeof renderStats==='function'){renderStats();return}
      if(name==='history'&&typeof renderHistory==='function'){renderHistory();return}
      if(name==='coupons'&&typeof renderCoupons==='function'){renderCoupons();return}
      if(name==='feedback'&&typeof renderFeedback==='function'){renderFeedback();return}
    }catch(err){console.warn('Tenis AI view adapter',err)}
    app.innerHTML='<div class="product-empty">Ta sekcja ładuje dane. Odśwież za chwilę.</div>';
  }

  function renderProduct(){
    syncChrome();
    const app=$('#app');if(!app)return;
    if(ui.view==='home')renderHome();
    else if(ui.view==='matches')renderMatches();
    else if(ui.view==='picks')renderPicks();
    else if(ui.view==='players')renderPlayers();
    else renderLegacy(ui.view);
    bindDynamic();
    hideTechnicalNoise();
    window.dispatchEvent(new CustomEvent('tenis-ai-product-render',{detail:{view:ui.view,role:role()}}));
  }

  function nav(next){
    if(!COPY[next])next='home';ui.view=next;
    try{view=next}catch{}
    if((next==='stats'||next==='history')&&typeof loadSecondaryData==='function')Promise.resolve(loadSecondaryData()).finally(renderProduct);else renderProduct();
    window.scrollTo({top:0,behavior:'auto'});
  }

  function marketCells(obj){
    if(!obj||typeof obj!=='object')return '<div class="market-cell"><span>Brak danych</span><b>—</b></div>';
    return Object.entries(obj).filter(([,v])=>finite(v)).map(([k,v])=>`<div class="market-cell"><span>${esc(k)}</span><b>${esc(String(k))}<strong>${Math.round(Number(v))}%</strong></b></div>`).join('')||'<div class="market-cell"><span>Brak danych</span><b>—</b></div>';
  }
  function binarySection(title,obj){return `<section class="market-section"><header>${esc(title)}</header><div class="market-grid">${marketCells(obj)}</div></section>`}
  function totalsSection(title,obj){
    if(!obj||typeof obj!=='object')return '';
    const cells=[];Object.entries(obj).forEach(([line,x])=>{if(finite(x?.over))cells.push(`<div class="market-cell"><span>OVER ${esc(line)}</span><b>Over<strong>${Math.round(Number(x.over))}%</strong></b></div>`);if(finite(x?.under))cells.push(`<div class="market-cell"><span>UNDER ${esc(line)}</span><b>Under<strong>${Math.round(Number(x.under))}%</strong></b></div>`)});
    return cells.length?`<section class="market-section"><header>${esc(title)}</header><div class="market-grid">${cells.join('')}</div></section>`:'';
  }
  function stateSections(m){
    const gs=m?.game_states;if(!gs||typeof gs!=='object')return '';
    return Object.entries(gs).map(([n,x])=>`<section class="market-section"><header>Wynik po ${esc(n)} gemach</header><div class="market-grid">${marketCells(x)}</div></section>`).join('');
  }

  function signalLines(m){
    const p=playable(m,20).map(s=>({s,v:valueOf(s),playable:true})).filter(x=>x.v!=null);
    const r=rawSignals(m,20).map(s=>({s,v:valueOf(s)??s.__value,playable:false})).filter(x=>x.v!=null);
    const seen=new Set();return [...p,...r].filter(x=>{const k=String(x.s?.key||x.s?.label||x.s?.pick||'')+'|'+x.v;if(seen.has(k))return false;seen.add(k);return true}).sort((a,b)=>b.v-a.v).slice(0,12);
  }
  function openMatch(raw){
    const m=typeof raw==='object'?raw:findMatch(raw);if(!m)return;
    ui.lastMatch=m;const overlay=$('#match-detail-overlay'),body=$('#match-screen-body'),title=$('#match-screen-title');if(!overlay||!body)return;
    const t=when(m),best=bestSignal(m),signals=signalLines(m);
    if(title)title.textContent=`${m?.p1||'—'} vs ${m?.p2||'—'}`;
    body.innerHTML=`
      <section class="detail-hero"><div><small>${esc(tour(m))} · ${esc(t.full)} · ${esc(m?.surface||'')} · ${esc(m?.tournament||'Turniej')}</small><h2>${esc(m?.p1||'—')} <i>vs</i> ${esc(m?.p2||'—')}</h2><p>${esc(m?.round||m?.round_name||'')} ${m?.quality?`· jakość danych ${esc(m.quality)}`:''}</p></div><div class="detail-strength"><span>TOP SYGNAŁ</span><strong>${score(best?.value)}</strong></div></section>
      <div class="detail-grid">
        <section class="detail-panel"><header class="detail-panel-head"><h3>Najmocniejsze sygnały</h3><span>PLAYABLE ma pierwszeństwo przed RAW</span></header><div class="signal-list">${signals.length?signals.map(x=>`<div class="signal-line ${x.playable?'playable':''}"><span>${x.playable?'SUPERBET ✓ · ':''}${esc(x.s?.label||x.s?.displayPick||x.s?.pick||x.s?.key||'Sygnał')}</span><strong>${score(x.v)}</strong></div>`).join(''):'<div class="product-empty">Brak sygnałów</div>'}</div></section>
        <section class="detail-panel"><header class="detail-panel-head"><h3>Zawodnicy</h3><span>Player DNA / Intelligence</span></header><div class="player-duel"><button data-player="${esc(m?.p1||'')}">${esc(m?.p1||'—')}</button><span>VS</span><button data-player="${esc(m?.p2||'')}">${esc(m?.p2||'—')}</button></div><div class="detail-actions"><button class="primary" data-symphony>♫ Symfonia 2.0</button>${isAdmin()?'<button data-admin-mode>⌘ Tryb techniczny</button>':''}</div></section>
        <section class="detail-panel wide"><header class="detail-panel-head"><h3>Rynki modelu</h3><span>pełne dane analityczne pozostają niezależne od oferty</span></header><div class="market-sections">${binarySection('Zwycięzca meczu',m?.match_win)}${binarySection('Zwycięzca 1. seta',m?.first_set_win)}${binarySection('Zwycięzca 2. seta',m?.second_set_win)}${binarySection('Liczba setów',m?.total_sets)}${totalsSection('Gemy · 1. set',m?.over_under)}${totalsSection('Gemy · cały mecz',m?.match_over_under)}${stateSections(m)}${binarySection('Dokładny wynik 1. seta',m?.exact_first_set)}${binarySection('Dokładny wynik meczu',m?.exact_match_score)}</div></section>
      </div>`;
    overlay.hidden=false;document.body.style.overflow='hidden';bindDynamic(body);
  }
  function closeMatch(){const o=$('#match-detail-overlay');if(o)o.hidden=true;document.body.style.overflow=''}

  function openPlayer(name){
    closeMatch();nav('players');const input=$('#player-search-input');if(!input)return;input.value=name;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));setTimeout(()=>input.focus(),50);
  }
  function proxyAccount(){const b=$('#account-button');if(b)b.click()}
  function proxyCommunity(){const b=$('#community-hub-open');if(b)b.click()}
  function proxySymphony(){const b=$('#symphony-open');if(b)b.click()}

  function hideTechnicalNoise(){
    if(document.documentElement.dataset.tenisUiMode==='technical')return;
    ['.v79-health','.v79-live-panel','.adaptive-health','.integrity-status-card','.technical-card','.phase11-technical'].forEach(sel=>$$(sel).forEach(el=>{if(!el.closest('#account-overlay,#community-hub-overlay'))el.style.display='none'}));
  }

  function bindDynamic(root=document){
    $$('[data-open-match]',root).forEach(el=>{if(el.dataset.boundProduct)return;el.dataset.boundProduct='1';el.addEventListener('click',()=>openMatch(el.dataset.openMatch))});
    $$('[data-symphony]',root).forEach(el=>{if(el.dataset.boundProduct)return;el.dataset.boundProduct='1';el.addEventListener('click',proxySymphony)});
    $$('[data-community]',root).forEach(el=>{if(el.dataset.boundProduct)return;el.dataset.boundProduct='1';el.addEventListener('click',proxyCommunity)});
    $$('[data-admin-mode]',root).forEach(el=>{if(el.dataset.boundProduct)return;el.dataset.boundProduct='1';el.addEventListener('click',()=>{if(isAdmin()&&document.documentElement.dataset.tenisUiMode!=='technical'){try{localStorage.setItem(MODE_KEY,'technical')}catch{}syncMode();renderProduct()}})});
    $$('[data-player]',root).forEach(el=>{if(el.dataset.boundProduct)return;el.dataset.boundProduct='1';el.addEventListener('click',()=>openPlayer(el.dataset.player))});
  }

  document.addEventListener('click',ev=>{
    const navEl=ev.target.closest?.('[data-view]');
    if(navEl){ev.preventDefault();ev.stopPropagation();nav(navEl.dataset.view);return}
    if(ev.target.closest?.('[data-account-proxy]')){ev.preventDefault();proxyAccount();return}
    if(ev.target.closest?.('[data-close-match]')){ev.preventDefault();closeMatch();return}
    if(ev.target.closest?.('[data-match-symphony]')){ev.preventDefault();proxySymphony();return}
  },true);

  $$('#focus-filters [data-focus]').forEach(b=>b.addEventListener('click',()=>{ui.focus=b.dataset.focus||'all';renderProduct()}));
  $$('#tour-nav [data-filter]').forEach(b=>b.addEventListener('click',ev=>{
    ev.stopImmediatePropagation();try{filter=b.dataset.filter||'all'}catch{};renderProduct();
  },true));
  $('#tenis-ui-mode-toggle')?.addEventListener('click',ev=>{ev.stopImmediatePropagation();toggleMode()},true);
  $('#match-detail-overlay')?.addEventListener('click',ev=>{if(ev.target.id==='match-detail-overlay')closeMatch()});
  document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&!$('#match-detail-overlay')?.hidden)closeMatch()});

  // Account/profile code assigns the role asynchronously. Keep shell permissions in sync.
  const observer=new MutationObserver(()=>{const r=role();if(document.documentElement.dataset.productRoleApplied!==r){document.documentElement.dataset.productRoleApplied=r;syncMode();hideTechnicalNoise()}});
  observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-tenis-role','data-tenis-auth-state']});

  // Replace only the old presentation entry point. Data loaders continue calling `render()` as before.
  try{render=renderProduct}catch{}
  try{updateViewChrome=syncChrome}catch{}

  window.TENIS_AI_PROJECT_UI=Object.freeze({
    version:'product-ui-2026-09-10',
    findMatch,
    openMatch,
    closeMatch,
    render:renderProduct,
    navigate:nav,
    currentView:()=>ui.view,
    currentMatch:()=>ui.lastMatch,
    role
  });
  window.TENIS_AI_APP_NAV=Object.freeze({go:nav,current:()=>ui.view});

  syncMode();
  // Allow the existing app bootstrap to start first, then take visual ownership.
  queueMicrotask(renderProduct);
})();
