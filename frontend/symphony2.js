(() => {
  'use strict';

  const VERSION='2.1';
  const DATA_URL='./data/symphony2_current.json';
  const STATS_URL='./data/symphony2_stats.json';
  const NAV_SELECTOR='#p751-bottom-nav [data-p751-nav="symphony2"]';
  let cache=null,statsCache=null,navTimer=null;

  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>v==null||v===''?null:(Number.isFinite(Number(v))?Number(v):null);
  const pct=v=>num(v)==null?'N/D':`${Number(v).toFixed(1)}%`;
  const nfmt=v=>Number(v||0).toLocaleString('pl-PL');
  const norm=v=>String(v??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ');

  const MARKET_LABELS={
    match_winner:'Wygra mecz',match_win:'Wygra mecz',
    set1_winner:'Wygra 1. set',set1_win:'Wygra 1. set',
    set2_winner:'Wygra 2. set',set2_win:'Wygra 2. set',
    set3_winner:'Wygra 3. set',set3_win:'Wygra 3. set',
    match_total:'Suma gemów · mecz',set1_total:'Suma gemów · 1. set',
    total_sets:'Liczba setów',exact_match_score:'Dokładny wynik meczu',
    set1_exact_score:'Dokładny wynik 1. seta',set1_tiebreak:'Tie-break w 1. secie',
    game_state:'Stan po gemach'
  };

  async function fetchJson(url){
    const r=await fetch(`${url}?v=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error(`${url} HTTP ${r.status}`);
    return r.json();
  }
  async function load(force=false){if(cache&&!force)return cache;cache=await fetchJson(DATA_URL);return cache}
  async function loadStats(force=false){if(statsCache&&!force)return statsCache;statsCache=await fetchJson(STATS_URL);return statsCache}

  function ensureHub(){
    let hub=document.querySelector('#symphony2-hub');
    if(hub)return hub;
    hub=document.createElement('section');
    hub.id='symphony2-hub';
    hub.className='s2-hub';
    hub.hidden=true;
    hub.innerHTML=`<div class="s2-hub-frame"><header class="s2-hub-top"><div><b>🎼 Symfonia 2.0</b><small>Realne linie Superbet · exact PLAYABLE</small></div><button type="button" data-s2-close aria-label="Zamknij">✕</button></header><div class="s2-hub-body"></div></div>`;
    document.body.appendChild(hub);
    hub.querySelector('[data-s2-close]')?.addEventListener('click',close);
    return hub;
  }
  function hubBody(){return ensureHub().querySelector('.s2-hub-body')}
  function close(){
    const hub=document.querySelector('#symphony2-hub');
    if(!hub)return;
    hub.hidden=true;
    document.documentElement.classList.remove('s2-hub-open');
    markNav('symphony2',false);
  }
  function markNav(which='symphony2',active=true){
    document.querySelectorAll('#p751-bottom-nav [data-p751-nav]').forEach(btn=>{
      if(active)btn.classList.toggle('active',btn.dataset.p751Nav===which);
      else if(btn.dataset.p751Nav===which)btn.classList.remove('active');
    });
  }

  function status(data){
    return `<div class="s2-status"><div class="s2-stat"><small>Model linii</small><strong>${esc(data?.model_status||'N/D')}</strong></div><div class="s2-stat"><small>Mecze z ofertą</small><strong>${Number(data?.matches_count||0)}</strong></div><div class="s2-stat"><small>Wygenerowano</small><strong>${esc((data?.generated_at||'').replace('T',' ').slice(0,16)||'N/D')}</strong></div></div>`;
  }
  function marketLabel(x){
    const base=MARKET_LABELS[String(x?.market||'').toLowerCase()]||String(x?.label||x?.market||'Rynek');
    const cp=num(x?.checkpoint);
    return cp!=null&&String(x?.market||'').toLowerCase()==='game_state'?`${base} ${cp} gemach`:base;
  }
  function selectionLabel(x){
    const line=num(x?.line),pick=String(x?.pick||'').trim(),core=pick||x?.label||x?.selection_id||'Selekcja';
    return line==null?core:`${core} ${Number(line).toFixed(1).replace('.0','')}`;
  }
  function leg(x){
    const state=num(x?.state_probability)==null?'':` · STATE ${pct(x.state_probability)}`;
    const support=Number(x?.learning_support_rows||0);
    return `<div class="s2-leg"><div><strong>${esc(selectionLabel(x))}</strong><small>${esc(marketLabel(x))} · dokładna linia Superbet${x?.operator_line_source?` · ${esc(x.operator_line_source)}`:''}${state} · historia n=${support}</small></div><div class="s2-prob">${pct(x?.operator_model_probability)}</div></div>`;
  }
  function compositionCard(m,c){
    return `<article class="s2-card"><div class="s2-head"><div><small>${esc(m?.tour||'')} ${m?.surface?`· ${esc(m.surface)}`:''}</small><h3>${esc(m?.p1)} <span>vs</span> ${esc(m?.p2)}</h3><div class="s2-muted">${Number(c?.legs||0)} zdarzenia · wszystkie z bieżącej oferty Superbet</div></div><div class="s2-score"><small>quality</small><strong>${Number(c?.score||0).toFixed(1)}</strong></div></div><div>${(c?.selection||[]).map(leg).join('')}</div><div class="s2-joint"><span>Wspólne P kompozycji</span><strong>${pct(c?.joint_probability)}</strong><small>${esc(c?.joint_status||'')} · policzone na tej samej dystrybucji stanów meczu</small></div></article>`;
  }
  function renderCompositions(data,count,legs){
    const rows=(data?.matches||[]).map(m=>{
      const n=legs==='auto'?m?.recommended_leg_count:Number(legs);
      return {m,c:n?m?.compositions?.[String(n)]:null};
    }).filter(x=>x.c).sort((a,b)=>Number(b.c?.score||0)-Number(a.c?.score||0)).slice(0,count);
    if(!rows.length)return '<div class="s2-empty">Brak kompozycji spełniających próg Symfonii 2.0. Pokazujemy wyłącznie wystarczająco jakościowe selekcje z dokładnej bieżącej oferty Superbet, które można policzyć we wspólnym state-space.</div>';
    return rows.map(x=>compositionCard(x.m,x.c)).join('');
  }
  function hubShell(data){
    return `<section class="s2-shell" data-symphony2-version="${VERSION}"><div class="s2-hero"><div class="s2-kicker">TENIS AI · SYMFONIA 2.0</div><h2>Symfonia 2.0</h2><p>Jedno miejsce dla PLAYABLE. Biorę dokładną aktualną ofertę Superbet, oceniam każdą selekcję modelem uczonym na historycznych realnych liniach i składam tylko spójne kombinacje z prawdziwym joint probability.</p></div>${status(data)}<div class="s2-controls"><label>Mecze<select id="s2-count"><option>1</option><option>2</option><option>3</option><option selected>4</option><option>5</option><option>6</option></select></label><label>Zdarzenia / mecz<select id="s2-legs"><option value="auto" selected>AUTO 2–6</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option></select></label><button class="s2-generate" id="s2-compose" type="button">🎼 Ułóż Symfonię 2.0</button></div><div id="s2-results" class="s2-grid">${renderCompositions(data,4,'auto')}</div></section>`;
  }
  async function open(){
    const hub=ensureHub(),b=hubBody();
    hub.hidden=false;document.documentElement.classList.add('s2-hub-open');markNav();
    b.innerHTML='<div class="s2-empty">Ładuję aktualny snapshot Superbet i model Symfonii 2.0…</div>';
    try{
      const data=await load(true);b.innerHTML=hubShell(data);
      b.querySelector('#s2-compose')?.addEventListener('click',()=>{
        const c=Number(b.querySelector('#s2-count')?.value||4),l=b.querySelector('#s2-legs')?.value||'auto';
        b.querySelector('#s2-results').innerHTML=renderCompositions(data,c,l);
      });
      return true;
    }catch(e){
      console.warn('[Symphony2 hub]',e);
      b.innerHTML='<div class="s2-empty">Symfonia 2.0 nie ma opublikowanego feedu. Nie używam żadnego starego generatora ani starej Symfonii jako fallback.</div>';
      return false;
    }
  }

  function bindNav(){
    const nav=document.querySelector(NAV_SELECTOR);
    if(!nav)return false;
    if(nav.dataset.symphony2Nav!=='1'){
      nav.innerHTML='<span>🎼</span><b>Symfonia 2.0</b>';
      nav.setAttribute('aria-label','Symfonia 2.0');
      nav.dataset.symphony2Nav='1';
    }
    nav.onclick=e=>{e?.preventDefault?.();e?.stopPropagation?.();open()};
    return true;
  }
  function scheduleNav(){
    clearTimeout(navTimer);
    if(bindNav())return;
    [50,200,700,1500,3000].forEach(ms=>setTimeout(bindNav,ms));
  }

  function calibrationHtml(training){
    const global=training?.global_calibration||{},markets=training?.market_calibration||{};
    const accepted=Object.entries(markets).filter(([,v])=>v?.accepted).length,raw=num(global.raw_brier),cal=num(global.calibrated_brier);
    const globalMode=global.production_applied===true?'UŻYWANA':global.accepted?'DIAGNOSTYKA':'RAW';
    return `<div class="s2stats-cal"><span>Time split <b>${training?.time_split?'TAK':'NIE'}</b></span><span>Kalibracja globalna <b>${globalMode}</b></span><span>Brier globalny <b>${raw==null?'N/D':raw.toFixed(4)}${cal==null?'':` → ${cal.toFixed(4)}`}</b></span><span>Aktywne kalibracje rynków <b>${accepted}</b></span></div>`;
  }
  function byLegHtml(perf){return `<div class="s2stats-legs">${[2,3,4,5,6].map(n=>{const r=perf?.by_leg_count?.[String(n)]||{};return `<div><span>${n} zd.</span><b>${pct(r.accuracy)}</b><small>${nfmt(r.hits)}/${nfmt(r.settled)} trafionych kompozycji</small></div>`}).join('')}</div>`}
  function statsCard(stats){
    const train=stats?.training||{},offer=stats?.current_offer||{},perf=stats?.performance||{};
    return `<section id="symphony2-performance" class="s2stats-card" data-version="${VERSION}"><header class="s2stats-head"><div><span>🎼 SYMFONIA 2.0 · STATYSTYKI</span><h3>Realne linie Superbet</h3><p>Nowa historia od zera. Wyniki starej Symfonii i starego generatora nie są importowane ani mieszane z tym panelem.</p></div><div class="s2stats-state"><small>model</small><b>${esc(stats?.model_status||'N/D')}</b></div></header><div class="s2stats-kpis"><div><span>Trening exact-line</span><b>${nfmt(train.training_rows)}</b><small>walidacja ${nfmt(train.validation_rows)}</small></div><div><span>Oferta teraz</span><b>${nfmt(offer.exact_operator_selections)}</b><small>${nfmt(offer.verified_fixtures)} fixture · state ${nfmt(offer.state_supported_selections)}</small></div><div><span>Kompozycje rozliczone</span><b>${nfmt(perf.compositions_settled)}</b><small>${pct(perf.composition_accuracy)} skuteczności</small></div><div><span>Nogi rozliczone</span><b>${nfmt(perf.legs_settled)}</b><small>${pct(perf.leg_accuracy)} skuteczności</small></div></div>${calibrationHtml(train)}<div class="s2stats-section"><div class="s2stats-title"><b>Skuteczność wg liczby zdarzeń</b><small>wyłącznie Symfonia 2.0</small></div>${byLegHtml(perf)}</div><div class="s2stats-note">Akcyjne teraz: <b>${nfmt(offer.selections_above_actionable_threshold)}</b> selekcji przy progu ${pct(offer.threshold)}. Oczekujące kompozycje 2.0: <b>${nfmt(perf.predictions_pending)}</b>. Joint: <b>${esc(stats?.joint_probability_policy||'EXACT_SHARED_STATE_ONLY')}</b>. Stare statystyki użyte: <b>NIE</b>.</div></section>`;
  }
  async function renderStats(force=false){
    const host=document.querySelector('#pc77');if(!host)return false;
    try{
      const stats=await loadStats(force);host.querySelector('#symphony2-performance')?.remove();
      const wrap=document.createElement('div');wrap.innerHTML=statsCard(stats);const card=wrap.firstElementChild;
      const anchor=host.querySelector('.pc12-main-trend')||host.querySelector('.pc12-summary');
      anchor?anchor.insertAdjacentElement('afterend',card):host.prepend(card);return true;
    }catch(e){console.warn('[Symphony2 stats]',e);return false}
  }
  function scheduleStats(force=false){[0,150,600,1300].forEach((d,i)=>setTimeout(()=>renderStats(force&&i===0),d))}

  function currentMatch(){
    const overlay=document.querySelector('#p751-match-overlay:not([hidden])'),screen=overlay?.querySelector('.p751-detail-screen')||document.querySelector('.p751-detail-screen');
    const key=overlay?.dataset?.matchKey||screen?.dataset?.matchKey||'';let match=null;
    try{match=key?window.TENIS_AI_PROJECT_UI?.findMatch?.(key):null}catch{}
    return {overlay,screen,match,key};
  }
  function sameMatch(row,match,key){
    if(!row)return false;
    const ids=[row.id,row.match_id,row.match_key].filter(v=>v!=null&&String(v)!=='').map(String),mids=[match?.id,match?.match_id,key].filter(v=>v!=null&&String(v)!=='').map(String);
    if(ids.some(x=>mids.includes(x)))return true;
    const a1=norm(row.p1),a2=norm(row.p2),b1=norm(match?.p1),b2=norm(match?.p2);
    return !!a1&&!!a2&&((a1===b1&&a2===b2)||(a1===b2&&a2===b1));
  }
  function compositionFor(row){
    if(!row)return null;const n=row.recommended_leg_count;if(n&&row.compositions?.[String(n)])return row.compositions[String(n)];
    for(const k of ['2','3','4','5','6'])if(row.compositions?.[k])return row.compositions[k];return null;
  }
  function matchSymphonyHtml(row,data){
    const comp=compositionFor(row),offer=Number(row?.offer_selections||0),scored=(row?.scored_selections||[]).filter(x=>num(x?.operator_model_probability)!=null);
    const best=scored.sort((a,b)=>num(b.operator_model_probability)-num(a.operator_model_probability)).slice(0,3);
    if(comp)return `<section id="symphony2-match-detail" class="s2-match-detail s2-match-ready" data-symphony2-match="1"><header><div><small>🎼 SYMFONIA 2.0 · PLAYABLE</small><h3>Najlepsza spójna kompozycja</h3><p>Wyłącznie dokładne, aktualne selekcje Superbet. RAW nie jest źródłem linii PLAYABLE.</p></div><strong>${pct(comp.joint_probability)}</strong></header><div class="s2-match-legs">${(comp.selection||[]).map(leg).join('')}</div><footer>Exact shared-state joint · ${comp.legs} zdarzenia · model ${esc(data?.model_status||'N/D')}</footer></section>`;
    return `<section id="symphony2-match-detail" class="s2-match-detail s2-match-wait" data-symphony2-match="1"><header><div><small>🎼 SYMFONIA 2.0 · PLAYABLE</small><h3>Brak kompozycji spełniającej próg</h3><p>Oferta Superbet jest oceniona, ale Symfonia 2.0 nie pokazuje słabszego układu jako gotowego typu.</p></div><strong>—</strong></header><div class="s2-match-summary"><span><small>Realne selekcje Superbet</small><b>${offer}</b></span><span><small>Najwyższe P(hit)</small><b>${best.length?pct(best[0].operator_model_probability):'N/D'}</b></span><span><small>Model</small><b>${esc(data?.model_status||'N/D')}</b></span></div>${best.length?`<details class="s2-match-candidates"><summary>Najmocniejsze ocenione linie · nie są PLAYABLE poniżej progu</summary>${best.map(leg).join('')}</details>`:''}</section>`;
  }
  function cleanupLegacySymphony(scope){
    if(!scope)return;scope.querySelectorAll('[data-symphony-match-mini],.symmatch-mini').forEach(x=>x.remove());
    const bad=/^(?:🎼\s*)?(?:SYMFONIA MODELOWA|PEŁNA SYMFONIA(?:\s*·\s*SUPERBET PLAYABLE)?|SYMFONIA\s*·\s*SUPERBET)$/i;
    [...scope.querySelectorAll('h2,h3,h4,b,strong,span,small')].forEach(node=>{
      if(node.closest('#symphony2-match-detail,.s2-shell,#symphony2-performance,#symphony2-hub'))return;
      if(!bad.test(String(node.textContent||'').trim()))return;
      const box=node.closest('article,section,details');if(box&&!box.matches('.p751-detail-screen,#p751-match-overlay'))box.remove();
    });
  }
  function compactSuperbet(scope){
    const root=scope?.querySelector?.('.dc87');if(!root)return;
    const kicker=root.querySelector('.dc87-kicker');if(kicker)kicker.textContent='SUPERBET · REALNA OFERTA';
    const title=root.querySelector('#dc87-title');if(title)title.textContent='Dokładne rynki i linie Superbet';
    const rows=[...root.querySelectorAll('.dc87-row,[data-dc87-row],tbody tr')];if(rows.length<=8||root.querySelector('[data-s2-offer-toggle]'))return;
    root.dataset.s2OfferCollapsed='1';rows.forEach((r,i)=>{if(i>=8)r.dataset.s2OfferExtra='1'});
    const btn=document.createElement('button');btn.type='button';btn.className='s2-offer-toggle';btn.dataset.s2OfferToggle='1';btn.textContent=`Pokaż pełną ofertę (${rows.length})`;
    btn.addEventListener('click',()=>{const collapsed=root.dataset.s2OfferCollapsed==='1';root.dataset.s2OfferCollapsed=collapsed?'0':'1';btn.textContent=collapsed?'Zwiń pełną ofertę':`Pokaż pełną ofertę (${rows.length})`});root.append(btn);
  }
  async function renderMatchDetail(force=false){
    const {overlay,screen,match,key}=currentMatch(),scope=screen||overlay;if(!scope)return false;cleanupLegacySymphony(scope);compactSuperbet(scope);
    try{
      const data=await load(force),row=(data?.matches||[]).find(x=>sameMatch(x,match,key));scope.querySelector('#symphony2-match-detail')?.remove();if(!row)return false;
      const wrap=document.createElement('div');wrap.innerHTML=matchSymphonyHtml(row,data);const block=wrap.firstElementChild,raw=scope.querySelector('[data-raw-playable-separation],.v921-raw,.raw-playable-raw,.model-raw'),decision=scope.querySelector('.dc87');
      if(decision)decision.insertAdjacentElement('beforebegin',block);else if(raw)raw.insertAdjacentElement('afterend',block);else scope.append(block);compactSuperbet(scope);return true;
    }catch(e){console.warn('[Symphony2 match]',e);return false}
  }
  function scheduleMatch(force=false){[0,80,250,700].forEach((d,i)=>setTimeout(()=>renderMatchDetail(force&&i===0),d))}

  document.addEventListener('click',e=>{
    if(e.target?.closest?.('[data-view="stats"],[data-p751-nav="stats"]'))scheduleStats(true);
    if(e.target?.closest?.('[data-p751-open],[data-p751-focus],[data-view="matches"],[data-p751-nav="matches"]'))scheduleMatch(true);
  },true);
  document.addEventListener('tenis-ai:stats-ready',()=>scheduleStats());
  document.addEventListener('tenis-ai:stats-dashboard-ready',()=>scheduleStats());
  document.addEventListener('tenis-ai:ui-ready',scheduleNav);
  window.addEventListener('pageshow',scheduleNav);

  let mutationTimer=null;
  const observer=new MutationObserver(()=>{
    scheduleNav();clearTimeout(mutationTimer);mutationTimer=setTimeout(()=>{
      const {screen,overlay}=currentMatch(),scope=screen||overlay;
      if(scope){cleanupLegacySymphony(scope);compactSuperbet(scope);if(!scope.querySelector('#symphony2-match-detail'))renderMatchDetail(false)}
    },80);
  });
  observer.observe(document.documentElement,{subtree:true,childList:true});

  scheduleNav();scheduleStats();scheduleMatch();ensureHub();
  window.TENIS_AI_SYMPHONY2=Object.freeze({version:VERSION,open,close,load,loadStats,renderStats,renderMatchDetail,cleanupLegacySymphony,compactSuperbet,bindNav});
})();