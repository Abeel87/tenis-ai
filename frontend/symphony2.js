(() => {
  'use strict';
  const VERSION='2.0';
  const DATA_URL='./data/symphony2_current.json';
  const STATS_URL='./data/symphony2_stats.json';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pct=v=>num(v)==null?'N/D':`${Number(v).toFixed(1)}%`;
  const nfmt=v=>Number(v||0).toLocaleString('pl-PL');
  let cache=null,statsCache=null;

  async function fetchJson(url){
    const r=await fetch(`${url}?v=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error(`${url} HTTP ${r.status}`);
    return r.json();
  }
  async function load(force=false){
    if(cache&&!force)return cache;
    cache=await fetchJson(DATA_URL);return cache;
  }
  async function loadStats(force=false){
    if(statsCache&&!force)return statsCache;
    statsCache=await fetchJson(STATS_URL);return statsCache;
  }

  function panel(){return document.querySelector('#scenario-v82a-panel')}
  function body(){return panel()?.querySelector('.sc82-body')||null}
  function homeButton(){return panel()?.querySelector('[data-sc-go="generator"]')||null}

  function decorate(){
    const b=homeButton();if(!b)return;
    b.innerHTML='<b>🎼 Symfonia 2.0</b><span>Realne linie Superbet → kalibrowane P(hit) → exact joint → najlepsza spójna kompozycja</span>';
    b.dataset.symphony2='1';
  }

  function status(data){
    return `<div class="s2-status">
      <div class="s2-stat"><small>Model linii</small><strong>${esc(data?.model_status||'N/D')}</strong></div>
      <div class="s2-stat"><small>Mecze z ofertą</small><strong>${Number(data?.matches_count||0)}</strong></div>
      <div class="s2-stat"><small>Wygenerowano</small><strong>${esc((data?.generated_at||'').replace('T',' ').slice(0,16)||'N/D')}</strong></div>
    </div>`;
  }

  function leg(x){
    const state=num(x.state_probability)==null?'':` · STATE ${pct(x.state_probability)}`;
    const support=Number(x.learning_support_rows||0);
    return `<div class="s2-leg"><div><strong>${esc(x.label||x.selection_id)}</strong><small>${esc(x.market||'')} · dokładna linia Superbet${x.operator_line_source?` · ${esc(x.operator_line_source)}`:''}${state} · historia n=${support}</small></div><div class="s2-prob">${pct(x.operator_model_probability)}</div></div>`;
  }

  function card(m,c){
    return `<article class="s2-card">
      <div class="s2-head"><div><small>${esc(m.tour||'')} ${m.surface?`· ${esc(m.surface)}`:''}</small><h3>${esc(m.p1)} <span>vs</span> ${esc(m.p2)}</h3><div class="s2-muted">${c.legs} zdarzenia · wszystkie z bieżącej oferty Superbet</div></div><div class="s2-score"><small>quality</small><strong>${Number(c.score||0).toFixed(1)}</strong></div></div>
      <div>${(c.selection||[]).map(leg).join('')}</div>
      <div class="s2-joint"><span>Wspólne P kompozycji</span><strong>${pct(c.joint_probability)}</strong><small>${esc(c.joint_status||'')} · policzone na tej samej dystrybucji stanów meczu</small></div>
    </article>`;
  }

  function render(data,count,legs){
    const rows=(data.matches||[]).map(m=>{
      const n=legs==='auto'?m.recommended_leg_count:Number(legs);
      return {m,c:n?m.compositions?.[String(n)]:null};
    }).filter(x=>x.c).sort((a,b)=>Number(b.c.score||0)-Number(a.c.score||0)).slice(0,count);
    if(!rows.length)return '<div class="s2-empty">Brak kompozycji Symfonii 2.0. RAW może mieć sygnały, ale do generatora wchodzą tylko wystarczająco jakościowe selekcje z dokładnej bieżącej oferty Superbet, które można policzyć we wspólnym state-space.</div>';
    return rows.map(x=>card(x.m,x.c)).join('');
  }

  function shell(data){
    return `<section class="s2-shell" data-symphony2-version="${VERSION}">
      <button type="button" class="s2-back" data-s2-back>← Scenariusze</button>
      <div class="s2-hero"><div class="s2-kicker">TENIS AI · SYMFONIA 2.0</div><h2>Symfonia 2.0</h2><p>Nie wymyślam linii do kuponu. Biorę dokładną aktualną ofertę Superbet, oceniam każdą selekcję modelem uczonym na historycznych realnych liniach i składam tylko kombinacje z prawdziwym joint probability.</p></div>
      ${status(data)}
      <div class="s2-controls"><label>Mecze<select id="s2-count"><option>1</option><option>2</option><option>3</option><option selected>4</option><option>5</option><option>6</option></select></label><label>Zdarzenia / mecz<select id="s2-legs"><option value="auto" selected>AUTO 2–6</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option></select></label><button class="s2-generate" id="s2-generate" type="button">🎼 Ułóż Symfonię 2.0</button></div>
      <div id="s2-results" class="s2-grid">${render(data,4,'auto')}</div>
    </section>`;
  }

  async function open(){
    const b=body();if(!b)return;
    b.innerHTML='<div class="s2-empty">Ładuję aktualny snapshot Superbet i model Symfonii 2.0…</div>';
    try{
      const data=await load(true);b.innerHTML=shell(data);
      b.querySelector('[data-s2-back]')?.addEventListener('click',()=>window.TENIS_AI_SCENARIOS_V82A?.open?.('home'));
      b.querySelector('#s2-generate')?.addEventListener('click',()=>{const c=Number(b.querySelector('#s2-count')?.value||4);const l=b.querySelector('#s2-legs')?.value||'auto';b.querySelector('#s2-results').innerHTML=render(data,c,l)});
    }catch(e){console.warn('[Symphony2]',e);b.innerHTML='<div class="s2-empty">Symfonia 2.0 nie ma opublikowanego feedu. Stara Symfonia nie jest używana jako fallback.</div>'}
  }

  function calibrationHtml(training){
    const global=training?.global_calibration||{};
    const markets=training?.market_calibration||{};
    const accepted=Object.entries(markets).filter(([,v])=>v?.accepted).length;
    const raw=num(global.raw_brier),cal=num(global.calibrated_brier);
    return `<div class="s2stats-cal"><span>Time split <b>${training?.time_split?'TAK':'NIE'}</b></span><span>Global calibration <b>${global.accepted?'AKTYWNA':'RAW'}</b></span><span>Brier <b>${raw==null?'N/D':raw.toFixed(4)}${cal==null?'':` → ${cal.toFixed(4)}`}</b></span><span>Kalibracje rynków <b>${accepted}</b></span></div>`;
  }

  function byLegHtml(perf){
    return `<div class="s2stats-legs">${[2,3,4,5,6].map(n=>{const r=perf?.by_leg_count?.[String(n)]||{};return `<div><span>${n} zd.</span><b>${pct(r.accuracy)}</b><small>${nfmt(r.hits)}/${nfmt(r.settled)} trafionych kompozycji</small></div>`}).join('')}</div>`;
  }

  function statsCard(stats){
    const train=stats?.training||{},offer=stats?.current_offer||{},perf=stats?.performance||{};
    return `<section id="symphony2-performance" class="s2stats-card" data-version="${VERSION}">
      <header class="s2stats-head"><div><span>🎼 SYMFONIA 2.0 · STATYSTYKI</span><h3>Realne linie Superbet</h3><p>Nowa historia od zera. Wyniki starej Symfonii v9.x nie są importowane ani mieszane z tym panelem.</p></div><div class="s2stats-state"><small>model</small><b>${esc(stats?.model_status||'N/D')}</b></div></header>
      <div class="s2stats-kpis">
        <div><span>Trening exact-line</span><b>${nfmt(train.training_rows)}</b><small>walidacja ${nfmt(train.validation_rows)}</small></div>
        <div><span>Oferta teraz</span><b>${nfmt(offer.exact_operator_selections)}</b><small>${nfmt(offer.verified_fixtures)} fixture · state ${nfmt(offer.state_supported_selections)}</small></div>
        <div><span>Kompozycje rozliczone</span><b>${nfmt(perf.compositions_settled)}</b><small>${pct(perf.composition_accuracy)} skuteczności</small></div>
        <div><span>Nogi rozliczone</span><b>${nfmt(perf.legs_settled)}</b><small>${pct(perf.leg_accuracy)} skuteczności</small></div>
      </div>
      ${calibrationHtml(train)}
      <div class="s2stats-section"><div class="s2stats-title"><b>Skuteczność wg liczby zdarzeń</b><small>wyłącznie Symfonia 2.0</small></div>${byLegHtml(perf)}</div>
      <div class="s2stats-note">Akcyjne teraz: <b>${nfmt(offer.selections_above_actionable_threshold)}</b> selekcji przy progu ${pct(offer.threshold)}. Oczekujące kompozycje 2.0: <b>${nfmt(perf.predictions_pending)}</b>. Joint: <b>${esc(stats?.joint_probability_policy||'EXACT_SHARED_STATE_ONLY')}</b>. Stare statystyki użyte: <b>NIE</b>.</div>
    </section>`;
  }

  async function renderStats(force=false){
    const host=document.querySelector('#pc77');if(!host)return false;
    try{
      const stats=await loadStats(force);
      host.querySelector('#symphony2-performance')?.remove();
      const wrap=document.createElement('div');wrap.innerHTML=statsCard(stats);const card=wrap.firstElementChild;
      const anchor=host.querySelector('.pc12-main-trend')||host.querySelector('.pc12-summary');
      anchor?anchor.insertAdjacentElement('afterend',card):host.prepend(card);
      return true;
    }catch(e){console.warn('[Symphony2 stats]',e);return false}
  }
  function scheduleStats(force=false){[0,150,600,1300].forEach((d,i)=>setTimeout(()=>renderStats(force&&i===0),d))}

  document.addEventListener('click',e=>{
    const t=e.target?.closest?.('[data-sc-go="generator"]');
    if(t){e.preventDefault();e.stopImmediatePropagation();open();return}
    if(e.target?.closest?.('[data-view="stats"],[data-p751-nav="stats"]'))scheduleStats(true);
  },true);
  document.addEventListener('tenis-ai:stats-ready',()=>scheduleStats());
  document.addEventListener('tenis-ai:stats-dashboard-ready',()=>scheduleStats());

  const observer=new MutationObserver(()=>decorate());
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden']});
  decorate();scheduleStats();
  window.TENIS_AI_SYMPHONY2={version:VERSION,open,load,loadStats,renderStats};
})();