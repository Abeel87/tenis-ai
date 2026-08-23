/* Tenis AI v6.2 — Player Search + Profile
   Frontend-only layer. Uses current results + frozen Tenis AI history; does not alter model logic. */
(() => {
  const input=document.querySelector('#player-search-input');
  const clearBtn=document.querySelector('#player-search-clear');
  const suggestions=document.querySelector('#player-search-suggestions');
  const panel=document.querySelector('#player-profile-panel');
  if(!input||!clearBtn||!suggestions||!panel)return;

  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
  const same=(a,b)=>norm(a)===norm(b);
  const safeAll=()=>{try{return Array.isArray(all)?all:[]}catch{return []}};
  const safeHistory=()=>{try{return Array.isArray(historyRows)?historyRows:[]}catch{return []}};
  const pc=x=>x==null?'—':`${Math.round(Number(x)*100)}%`;
  const n1=x=>x==null?'—':Number(x).toFixed(1);
  const dt=x=>{const d=new Date(x||'');return Number.isFinite(d.getTime())?d:null};
  const displayDate=x=>{const d=dt(x);return d?d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'2-digit'}):'—'};
  const displayTime=x=>{const d=dt(x);return d?d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—'};
  const playerInitials=name=>String(name||'?').split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();

  function getPlayers(){
    const byKey=new Map();
    const add=p=>{const key=norm(p);if(key&&!byKey.has(key))byKey.set(key,String(p))};
    safeAll().forEach(m=>{add(m.p1);add(m.p2)});
    safeHistory().forEach(m=>{add(m.p1);add(m.p2)});
    return [...byKey.values()];
  }

  function playerCounts(name){
    const current=safeAll().filter(m=>(same(m.p1,name)||same(m.p2,name))&&currentish(m)).length;
    const tracked=safeHistory().filter(m=>same(m.p1,name)||same(m.p2,name)).length;
    return {current,tracked};
  }

  function currentish(m){
    try{return typeof clientCurrent==='function'?clientCurrent(m):true}catch{return true}
  }

  function showSuggestions(query){
    const q=norm(query);
    if(!q){suggestions.hidden=true;suggestions.innerHTML='';return}
    const rows=getPlayers().map(name=>({name,key:norm(name),counts:playerCounts(name)}))
      .filter(x=>x.key.includes(q))
      .sort((a,b)=>Number(b.key.startsWith(q))-Number(a.key.startsWith(q))||b.counts.current-a.counts.current||b.counts.tracked-a.counts.tracked||a.name.localeCompare(b.name,'pl'))
      .slice(0,8);
    suggestions.innerHTML=rows.length?rows.map(x=>`<button type="button" class="player-suggestion" data-player="${esc(x.name)}"><b>${esc(x.name)}</b><small>${x.counts.current?`${x.counts.current} aktualny`:`${x.counts.tracked} w historii`}</small></button>`).join(''):'<div class="player-suggestion-empty">Brak zawodnika w aktualnych danych lub historii Tenis AI.</div>';
    suggestions.hidden=false;
    suggestions.querySelectorAll('[data-player]').forEach(b=>b.onclick=()=>selectPlayer(b.dataset.player));
  }

  function findPlayer(query){
    const q=norm(query);if(!q)return '';
    const players=getPlayers();
    return players.find(x=>norm(x)===q)||players.find(x=>norm(x).startsWith(q))||players.find(x=>norm(x).includes(q))||'';
  }

  function selectPlayer(name){
    input.value=name;clearBtn.hidden=false;suggestions.hidden=true;renderPlayerProfile(name);
    setTimeout(()=>panel.scrollIntoView({behavior:'smooth',block:'start'}),40);
  }

  function latestStats(name,matches){
    const candidates=[...matches,...safeAll().filter(m=>same(m.p1,name)||same(m.p2,name))];
    for(const m of candidates){
      if(same(m.p1,name)&&m.p1_stats)return m.p1_stats;
      if(same(m.p2,name)&&m.p2_stats)return m.p2_stats;
    }
    return null;
  }

  function greenSignals(m){
    try{return bestSignalsData(m,20).filter(x=>Number(x.v)>=72).slice(0,3)}catch{return []}
  }

  function currentCard(m,name){
    const opponent=same(m.p1,name)?m.p2:m.p1;
    const sig=greenSignals(m);
    const liveMeta=[m.tour?String(m.tour).toUpperCase():'',m.surface||'',m.round||m.round_name||m.stage||''].filter(Boolean);
    let detail='';
    try{detail=renderMatchDetail(m)}catch{}
    return `<article class="player-current-card">
      <div class="player-current-head"><div><span>Aktualny mecz</span><b>${esc(name)} <i style="color:#678aa2;font-style:normal">vs</i> ${esc(opponent||'—')}</b></div><div class="player-current-time"><b>${esc(displayTime(m.scheduled_time))}</b><small>${esc(displayDate(m.scheduled_time))}</small></div></div>
      <div class="player-current-meta">${liveMeta.map(x=>`<span>${esc(x)}</span>`).join('')}${m.tournament?`<span>${esc(m.tournament)}</span>`:''}${m.model_confidence!=null?`<span>MODEL ${Math.round(m.model_confidence)}</span>`:''}</div>
      <div class="player-best-signals">${sig.length?sig.map(x=>`<div class="player-best-signal"><span>${esc(x.label)}</span><b>${Math.round(x.v)}/100</b></div>`).join(''):'<div class="player-no-signal">Brak zielonego sygnału ≥72/100 — model nie wymusza typu na siłę.</div>'}</div>
      ${detail?`<details class="player-full-analysis"><summary>Pełna analiza meczu ▾</summary>${detail}</details>`:''}
    </article>`;
  }

  function statGrid(stats){
    if(!stats)return '<div class="player-empty">Brak zagregowanych statystyk zawodnika w aktualnym pakiecie danych.</div>';
    const values=[
      ['Ranking',stats.rank??'—','cyan'],
      ['Mecze próbki',stats.matches??'—',''],
      ['Ta nawierzchnia',stats.surface_matches??'—',''],
      ['Win rate',pc(stats.won),''],
      ['Wygrany 1. set',pc(stats.first_set_won),''],
      ['Wygrany 2. set',pc(stats.second_set_won),''],
      ['Hold',pc(stats.hold_rate),'cyan'],
      ['Return points',pc(stats.return_points_won),''],
      ['Mecze / 7 dni',stats.matches_7d??'—',''],
      ['Dni od meczu',stats.days_since_last??'—',''],
      ['Śr. gemy 1. seta',n1(stats.first_set_games),''],
      ['Próbka surface',stats.surface_matches??'—','']
    ];
    return `<div class="player-stat-grid">${values.map(([l,v,c])=>`<div class="player-stat"><span>${esc(l)}</span><b class="${c}">${esc(v)}</b></div>`).join('')}</div>`;
  }

  function historyFor(name){return safeHistory().filter(e=>same(e.p1,name)||same(e.p2,name)).sort((a,b)=>(dt(b.scheduled_time)?.getTime()||0)-(dt(a.scheduled_time)?.getTime()||0))}

  function signalSummary(rows){
    let hits=0,misses=0,pending=0,unverifiable=0;
    const groups=new Map();
    const surfaces=new Map();
    for(const e of rows){
      for(const s of (e.signals||[])){
        const r=s.result||'pending';
        if(r==='hit')hits++;else if(r==='miss')misses++;else if(r==='pending')pending++;else if(r==='unverifiable')unverifiable++;
        if(r!=='hit'&&r!=='miss')continue;
        const key=s.label||s.market||'Rynek';
        if(!groups.has(key))groups.set(key,{label:key,hits:0,misses:0});
        const g=groups.get(key);if(r==='hit')g.hits++;else g.misses++;
        const sf=String(e.surface||'brak danych').toLowerCase();
        if(!surfaces.has(sf))surfaces.set(sf,{label:sf,hits:0,misses:0});
        const sg=surfaces.get(sf);if(r==='hit')sg.hits++;else sg.misses++;
      }
    }
    const decorate=g=>{const n=g.hits+g.misses;return {...g,n,accuracy:n?100*g.hits/n:0,rank:wilson(g.hits,n)}};
    const markets=[...groups.values()].map(decorate).sort((a,b)=>b.rank-a.rank||b.n-a.n).slice(0,6);
    const surfaceRows=[...surfaces.values()].map(decorate).sort((a,b)=>b.rank-a.rank||b.n-a.n).slice(0,4);
    return {hits,misses,pending,unverifiable,settled:hits+misses,accuracy:hits+misses?100*hits/(hits+misses):null,markets,surfaces:surfaceRows};
  }

  function wilson(h,n){
    if(!n)return 0;const z=1.2816,p=h/n,z2=z*z;
    return (p+z2/(2*n)-z*Math.sqrt((p*(1-p)+z2/(4*n))/n))/(1+z2/n);
  }

  function marketRows(markets){
    if(!markets.length)return '<div class="player-empty">Jeszcze brak rozliczonych zielonych typów dla tego zawodnika.</div>';
    return `<div class="player-market-list">${markets.map(g=>`<div class="player-market-row"><div><b>${esc(g.label)}</b><small>${g.hits} trafione · ${g.misses} nietrafione</small></div><div class="player-market-score"><strong>${g.accuracy.toFixed(0)}%</strong><em>${g.n<3?'mała próbka':`${g.n} rozliczonych`}</em></div></div>`).join('')}</div>`;
  }

  function surfaceRows(rows){
    if(!rows.length)return '';
    return `<div class="player-surface-list">${rows.map(g=>`<div class="player-surface-row"><div><b>${esc(g.label.toUpperCase())}</b><small>${g.n} rozliczonych sygnałów</small></div><div class="player-market-score"><strong>${g.accuracy.toFixed(0)}%</strong><em>${g.hits}/${g.n}</em></div></div>`).join('')}</div>`;
  }

  function historyEntryKey(e){return String(e?.match_key||e?.match_id||e?.id||[e?.p1,e?.p2,e?.scheduled_time].join('|'))}

  function historyRowsHtml(rows,name){
    if(!rows.length)return '<div class="player-empty">Tenis AI nie ma jeszcze zamrożonego raportu dla tego zawodnika.</div>';
    return `<div class="player-history-list">${rows.slice(0,8).map(e=>{
      const opponent=same(e.p1,name)?e.p2:e.p1;
      const sig=e.signals||[];const h=sig.filter(x=>x.result==='hit').length;const m=sig.filter(x=>x.result==='miss').length;
      const settled=h+m;const cls=settled?(m===0?'hit':h===0?'miss':'pending'):'pending';
      let scoreText='Oczekuje';try{scoreText=finalScore(e)}catch{}
      return `<button type="button" class="player-history-row" data-player-history-key="${esc(historyEntryKey(e))}"><div class="player-history-top"><b>${esc(opponent||'—')}</b><span>${esc(displayDate(e.scheduled_time))}</span></div><div class="player-history-meta">${esc(String(e.tour||'').toUpperCase())}${e.tournament?` · ${esc(e.tournament)}`:''}${e.surface?` · ${esc(e.surface)}`:''}</div><div class="player-history-bottom"><div class="player-history-score">${esc(scoreText)}</div><div class="player-history-result ${cls}">${settled?`${h}✅ ${m}❌`:`${sig.length} ⏳`}</div></div><small class="player-history-open-label">Otwórz raport po meczu ›</small></button>`;
    }).join('')}</div>`;
  }

  function renderPlayerProfile(name){
    window.TENIS_AI_PLAYER_PROFILE_ACTIVE=true;
    document.documentElement.classList.add('tenis-ai-player-profile-active');
    const rowsAll=safeAll().filter(m=>same(m.p1,name)||same(m.p2,name));
    const current=rowsAll.filter(currentish).sort((a,b)=>(dt(a.scheduled_time)?.getTime()||0)-(dt(b.scheduled_time)?.getTime()||0));
    const ready=current.filter(m=>m.model_ready&&m.first_set_win);
    const hist=historyFor(name);
    const summary=signalSummary(hist);
    const stats=latestStats(name,ready.length?ready:current);
    const tracked=hist.length;
    const currentForProfile=ready.length?ready:current.slice(0,2);
    const accuracy=summary.accuracy==null?'—':`${summary.accuracy.toFixed(0)}%`;
    panel.hidden=false;
    panel.innerHTML=`
      <div class="player-profile-top"><div class="player-profile-name"><div class="player-avatar-ai">${esc(playerInitials(name))}</div><div><h2>${esc(name)}</h2><p>Profil z aktualnych danych modelu + zamrożonej historii Tenis AI</p></div></div><button type="button" class="player-profile-close" id="player-profile-close" aria-label="Zamknij profil">✕</button></div>
      <div class="player-profile-kpis">
        <div class="player-kpi"><span>Aktualne mecze</span><b>${current.length}</b></div>
        <div class="player-kpi"><span>Historia AI</span><b>${tracked}</b></div>
        <div class="player-kpi"><span>Rozliczone typy</span><b>${summary.settled}</b></div>
        <div class="player-kpi"><span>Skuteczność AI</span><b class="lime">${accuracy}</b></div>
      </div>
      <section class="player-section player-ai-history-quick"><div class="player-section-title"><b>🕘 Historia typów Tenis AI</b><small>dokładnie te mecze, które aplikacja zamroziła przed startem</small></div>${historyRowsHtml(hist,name)}</section>
      <section class="player-section player-current-section"><div class="player-section-title"><b>🔥 Dzisiejszy / najbliższy mecz</b><small>najmocniejsze zielone ≥72</small></div><div class="player-current-list">${currentForProfile.length?currentForProfile.map(m=>currentCard(m,name)).join(''):'<div class="player-empty">Brak aktualnego meczu tego zawodnika w danych. Historia powyżej nadal jest dostępna.</div>'}</div></section>
      <section class="player-section"><div class="player-section-title"><b>📚 Statystyki zawodnika</b><small>agregaty z danych używanych przez model</small></div>${statGrid(stats)}</section>
      <section class="player-section"><div class="player-section-title"><b>🏆 Co najczęściej wchodziło</b><small>tylko rozliczone zielone typy Tenis AI</small></div>${marketRows(summary.markets)}</section>
      ${summary.surfaces.length?`<section class="player-section"><div class="player-section-title"><b>🏟️ Skuteczność wg nawierzchni</b><small>historia naszych sygnałów</small></div>${surfaceRows(summary.surfaces)}</section>`:''}
      <div class="player-profile-note">Na razie profil korzysta z danych, które już mamy: aktualnej analizy oraz historii prognoz zapisanych przez Tenis AI. Nie udajemy pełnej historii game-by-game. Po podłączeniu dokładniejszego API dołożymy pełne ostatnie 10/20 meczów, breaki, kolejność serwisu i bardziej szczegółowe rynki Early Hold.</div>`;
    document.querySelector('#player-profile-close').onclick=()=>closeProfile(true);
    panel.querySelectorAll('[data-player-history-key]').forEach(b=>b.onclick=()=>{
      const e=hist.find(x=>historyEntryKey(x)===b.dataset.playerHistoryKey);
      if(!e)return;
      closeProfile(false);
      document.querySelector('.main-tabs [data-view="history"]')?.click();
      requestAnimationFrame(()=>window.TENIS_AI_CLEAN_CORE?.openPostMatch?.(e));
    });
    // v8.1: montujemy moduły profilu jawnie i porcjami między klatkami.
    requestAnimationFrame(()=>{
      window.TENIS_AI_PLAYER_TRENDS_V81?.mount?.(name);
      window.TENIS_AI_SERVE_PROPS_V81?.mountProfile?.();
      window.TENIS_AI_EARLY_HOLD_PATHS_V81?.mountProfile?.();
      requestAnimationFrame(()=>window.TENIS_AI_PLAYER_ANALYTICS_V801?.mount?.(name));
    });
  }

  function closeProfile(returnToOrigin=true){
    const returnKey=String(window.TENIS_AI_PLAYER_PROFILE_RETURN_KEY||'');
    window.TENIS_AI_PLAYER_PROFILE_RETURN_KEY='';
    window.TENIS_AI_PLAYER_PROFILE_ACTIVE=false;
    document.documentElement.classList.remove('tenis-ai-player-profile-active');
    panel.hidden=true;panel.innerHTML='';input.value='';clearBtn.hidden=true;suggestions.hidden=true;
    requestAnimationFrame(()=>{
      window.TENIS_AI_SERVE_PROPS_V81?.refreshAll?.(document);
      window.TENIS_AI_EARLY_HOLD_PATHS_V81?.refresh?.();
      if(returnToOrigin&&returnKey)window.TENIS_AI_PROJECT_UI?.openMatch?.(returnKey);
    });
  }

  input.addEventListener('input',()=>{clearBtn.hidden=!input.value;showSuggestions(input.value)});
  input.addEventListener('focus',()=>{if(input.value)showSuggestions(input.value)});
  input.addEventListener('keydown',e=>{
    if(e.key==='Enter'){
      e.preventDefault();const name=findPlayer(input.value);if(name)selectPlayer(name);else showSuggestions(input.value);
    }
    if(e.key==='Escape'){suggestions.hidden=true}
  });
  // v7.6.3: public bridge for clickable player names in Match Center.
  window.tenisAIPlayerProfileOpen=selectPlayer;

  clearBtn.onclick=closeProfile;
  document.addEventListener('click',e=>{if(!document.querySelector('#player-search-shell')?.contains(e.target))suggestions.hidden=true});
})();
