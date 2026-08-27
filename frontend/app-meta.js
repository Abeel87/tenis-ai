/* Tenis AI v8.0.1 — central app metadata */
/* v8.7 Decision Center + controlled Adaptive PROD compatibility layer */
(() => {
  const META = Object.freeze({
    appVersion: 'v8.0.1',
    displayVersion: 'v8.8.7',
    modelVersion: 'v7.8D',
    calibrationModelVersion: 'v7.8D-calibration-guard',
    productionModelVersion: 'v8.4B',
    dynamicWeightsVersion: 'v8.4D',
    playerIntelligenceVersion: 'v8.5',
    generatorPolicyVersion: 'v8.8.10-cross-view-quality-source',
    modelName: 'AutoLearn Ensemble + Adaptive Learning',
    productionModelName: 'AutoLearn Ensemble + Dynamic Weights + Adaptive PROD',
    adaptiveVersion: 'v7.9B-bayesian-meta',
    uiArchitecture: 'v8.0.1-clean-core',
    currentUiArchitecture: 'v8.8.7-checkpoint-quality-lock',
    cacheVersion: 'v801',
    runtimeCacheVersion: 'v87',
    fastBootVersion: 'v8.8.8',
    playerHumanUiVersion: 'v8.8.8',
    generatorQualityLockVersion: 'v8.8.8'
  });

  window.TENIS_AI_META = META;

  function applyMeta(){
    document.documentElement.dataset.tenisAiVersion=META.displayVersion||META.appVersion;
    document.title=`Tenis AI · ${META.displayVersion||META.appVersion}`;
    const p=document.querySelector('.brand-copy p');
    if(p)p.textContent=`Tenis AI ${META.displayVersion||META.appVersion} · Decision Center + Adaptive PROD`;
  }

  window.TENIS_AI_APPLY_META=applyMeta;

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyMeta,{once:true});
  else applyMeta();
})();

/* v8.8.8 FAST BOOT
   app.js historically waits for results + ~10 MB history before showing matches and
   also cache-busts every JSON request. This compatibility layer starts results/meta
   immediately, canonicalizes /data JSON requests and renders matches as soon as
   results.json is ready. Manual refresh still clears this short-lived cache. */
(() => {
  'use strict';
  if (window.TENIS_AI_FAST_BOOT_V888) return;

  const browserFetch = window.fetch.bind(window);
  const inflight = new Map();
  const cache = new Map();
  const state = {loading:true, resultsReady:false, network:0, joined:0, cacheHits:0};

  function canonicalDataUrl(input){
    try {
      const raw = input instanceof Request ? input.url : String(input);
      const u = new URL(raw, location.href);
      if (u.origin !== location.origin || !u.pathname.includes('/data/') || !u.pathname.endsWith('.json')) return null;
      u.searchParams.delete('ts');
      return u;
    } catch { return null; }
  }
  function methodOf(input, init){
    return String(init?.method || (input instanceof Request ? input.method : 'GET') || 'GET').toUpperCase();
  }
  function ttl(path){
    if (path.endsWith('/data/results.json')) return 60000;
    if (path.endsWith('/data/meta.json')) return 30000;
    if (path.endsWith('/data/history.json')) return 60000;
    if (path.endsWith('/data/history_stats.json')) return 30000;
    return 15000;
  }
  function clearDataCache(){ cache.clear(); }

  async function fastFetch(input, init){
    const u = canonicalDataUrl(input);
    if (!u || methodOf(input,init) !== 'GET') return browserFetch(input,init);
    const key = `${u.pathname}${u.search}`;
    const now = Date.now();
    const hit = cache.get(key);
    if (hit && now-hit.at < ttl(u.pathname)) {
      state.cacheHits++;
      return hit.response.clone();
    }
    if (inflight.has(key)) {
      state.joined++;
      const r = await inflight.get(key);
      return r.clone();
    }
    state.network++;
    const cleanInit = {...(init || {})};
    // Browser cache policy can stay fresh; our in-memory layer handles request joining.
    if (cleanInit.cache === 'reload' || cleanInit.cache === 'no-cache') cleanInit.cache = 'no-store';
    const task = browserFetch(u.toString(), cleanInit).then(r => {
      if (r?.ok) cache.set(key,{at:Date.now(),response:r.clone()});
      return r;
    }).finally(()=>inflight.delete(key));
    inflight.set(key,task);
    const r = await task;
    return r.clone();
  }

  window.fetch = fastFetch;
  document.addEventListener('click', e => {
    if (e.target?.closest?.('#refresh')) clearDataCache();
  }, true);

  const app = document.querySelector('#app');
  if (app && !app.textContent.trim()) {
    app.innerHTML = '<div class="empty" data-v888-loading><b>Ładowanie meczów…</b><br><br>Pobieram najpierw dzisiejsze spotkania. Historia i statystyki doładują się osobno.</div>';
  }

  const earlyResults = fastFetch('data/results.json',{cache:'no-store'}).then(r=>r.ok?r.json():[]).catch(()=>[]);
  const earlyMeta = fastFetch('data/meta.json',{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({}));

  function applyMetaFast(meta){
    try {
      const updated=document.querySelector('#updated');
      if(updated)updated.textContent=meta?.updated_at?'Aktualizacja: '+new Date(meta.updated_at).toLocaleString('pl-PL'):'Aktualizacja: —';
      const mode=document.querySelector('#mode');
      if(mode)mode.textContent='Źródło: '+(meta?.fixtures_mode||'—');
    } catch {}
  }

  // Timer runs after parser-blocking scripts, so app.js bindings already exist.
  setTimeout(() => {
    Promise.all([earlyResults,earlyMeta]).then(([results,meta]) => {
      try {
        if (Array.isArray(results)) {
          all = results;
          state.resultsReady = true;
          applyMetaFast(meta || {});
          if (typeof updateCounts === 'function') updateCounts();
          if (typeof view === 'undefined' || view === 'matches') {
            if (typeof renderMatches === 'function') renderMatches();
          }
        }
      } catch {}
      state.loading = false;
    }).catch(()=>{ state.loading=false; });
  },0);

  function loadAddon(src,id){
    if(document.getElementById(id))return;
    const s=document.createElement('script');
    s.id=id;s.src=src;s.async=false;
    document.body.appendChild(s);
  }
  function loadUxHotfixes(){
    loadAddon('player-intelligence-v888-human.js?v=888','pi888-human-addon');
    loadAddon('generator-quality-v888.js?v=888','generator888-quality-addon');
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',loadUxHotfixes,{once:true});
  else loadUxHotfixes();

  window.TENIS_AI_FAST_BOOT_V888 = Object.freeze({
    version:'v8.8.8',
    clear:clearDataCache,
    snapshot:()=>({...state,cached:cache.size,inflight:inflight.size})
  });
})();
