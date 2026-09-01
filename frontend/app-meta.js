/* Tenis AI v8.0.1 — central app metadata */
/* v8.9.2 Full App Coherence + controlled Adaptive PROD compatibility layer */
(() => {
  const META = Object.freeze({
    appVersion: 'v8.0.1',
    displayVersion:'v8.8.7',
    currentUiArchitecture:'v8.8.7-checkpoint-quality-lock',
    releaseVersion:'v9.2.3',
    modelVersion:'v7.8D',
    calibrationModelVersion:'v7.8D-calibration-guard',
    productionModelVersion:'v8.4B',
    dynamicWeightsVersion:'v8.4D',
    playerIntelligenceVersion:'v8.5',
    playerModelShadowVersion:'v8.9',
    ensemblePlayerLearningVersion:'v8.9.1',
    appCoherenceVersion:'v8.9.2',
    symphonyVersion:'v2.1',
    modelName:'AutoLearn Ensemble + Adaptive Learning',
    productionModelName:'AutoLearn Ensemble + Dynamic Weights + Adaptive PROD',
    adaptiveVersion:'v7.9B-bayesian-meta',
    uiArchitecture:'v8.0.1-clean-core',
    cacheVersion: 'v801',
    runtimeCacheVersion:'v87',
    fastBootVersion:'v8.8.8',
    playerHumanUiVersion:'v8.8.8'
  });

  window.TENIS_AI_META=META;
  function applyMeta(){
    const shown=META.releaseVersion||META.displayVersion||META.appVersion;
    document.documentElement.dataset.tenisAiVersion=shown;
    document.title=`Tenis AI · ${shown}`;
    const p=document.querySelector('.brand-copy p');
    if(p)p.textContent=`Tenis AI ${shown} · Adaptive PROD + Player Learning SHADOW`;
    const foot=document.querySelector('body > footer > div:nth-child(2)');
    if(foot)foot.textContent=`${shown} · Player Intelligence i Player Learning działają w SHADOW. Modele nie gwarantują wygranej ani zysku.`;
  }
  window.TENIS_AI_APPLY_META=applyMeta;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyMeta,{once:true});else applyMeta();
})();

/* v8.8.8 FAST BOOT — results first, history/statistics separately. */
(() => {
  'use strict';
  if(window.TENIS_AI_FAST_BOOT_V888)return;
  if(typeof window.fetch!=='function'){
    window.TENIS_AI_FAST_BOOT_V888=Object.freeze({version:'v8.8.8',disabled:true});
    return;
  }

  const browserFetch=window.fetch.bind(window),inflight=new Map(),cache=new Map();
  const state={loading:true,resultsReady:false,network:0,joined:0,cacheHits:0};

  function canonicalDataUrl(input){
    try{
      const raw=input instanceof Request?input.url:String(input),u=new URL(raw,location.href);
      if(u.origin!==location.origin||!u.pathname.includes('/data/')||!u.pathname.endsWith('.json'))return null;
      u.searchParams.delete('ts');return u;
    }catch{return null}
  }
  function methodOf(input,init){return String(init?.method||(input instanceof Request?input.method:'GET')||'GET').toUpperCase()}
  function ttl(path){
    if(path.endsWith('/data/results.json'))return 60000;
    if(path.endsWith('/data/meta.json'))return 30000;
    if(path.endsWith('/data/history.json'))return 60000;
    if(path.endsWith('/data/history_stats.json'))return 30000;
    return 15000;
  }
  function clearDataCache(){cache.clear()}
  async function fastFetch(input,init){
    const u=canonicalDataUrl(input);if(!u||methodOf(input,init)!=='GET')return browserFetch(input,init);
    const key=`${u.pathname}${u.search}`,now=Date.now(),hit=cache.get(key);
    if(hit&&now-hit.at<ttl(u.pathname)){state.cacheHits++;return hit.response.clone()}
    if(inflight.has(key)){state.joined++;const r=await inflight.get(key);return r.clone()}
    state.network++;
    const cleanInit={...(init||{})};if(cleanInit.cache==='reload'||cleanInit.cache==='no-cache')cleanInit.cache='no-store';
    const task=browserFetch(u.toString(),cleanInit).then(r=>{if(r?.ok)cache.set(key,{at:Date.now(),response:r.clone()});return r}).finally(()=>inflight.delete(key));
    inflight.set(key,task);const r=await task;return r.clone();
  }

  window.fetch=fastFetch;
  document.addEventListener('click',e=>{if(e.target?.closest?.('#refresh'))clearDataCache()},true);
  const app=document.querySelector('#app');
  if(app&&!app.textContent.trim())app.innerHTML='<div class="empty" data-v888-loading><b>Ładowanie meczów…</b><br><br>Pobieram najpierw dzisiejsze spotkania. Historia i statystyki doładują się osobno.</div>';

  const earlyResults=fastFetch('data/results.json',{cache:'no-store'}).then(r=>r.ok?r.json():[]).catch(()=>[]);
  const earlyMeta=fastFetch('data/meta.json',{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({}));
  function applyMetaFast(meta){
    try{
      const updated=document.querySelector('#updated');if(updated)updated.textContent=meta?.updated_at?'Aktualizacja: '+new Date(meta.updated_at).toLocaleString('pl-PL'):'Aktualizacja: —';
      const mode=document.querySelector('#mode');if(mode)mode.textContent='Źródło: '+(meta?.fixtures_mode||'—');
    }catch{}
  }
  setTimeout(()=>{
    Promise.all([earlyResults,earlyMeta]).then(([results,meta])=>{
      try{
        if(Array.isArray(results)){
          all=results;state.resultsReady=true;applyMetaFast(meta||{});
          if(typeof updateCounts==='function')updateCounts();
          if(typeof view==='undefined'||view==='matches'){if(typeof renderMatches==='function')renderMatches()}
        }
      }catch{}
      state.loading=false;
    }).catch(()=>{state.loading=false});
  },0);

  function loadAddon(src,id){
    if(document.getElementById(id))return;
    const s=document.createElement('script');s.id=id;s.src=src;s.async=false;document.body.appendChild(s);
  }
  function loadStyle(href,id){
    if(document.getElementById(id))return;
    const l=document.createElement('link');l.id=id;l.rel='stylesheet';l.href=href;document.head.appendChild(l);
  }
  function loadUxHotfixes(){
    loadAddon('player-intelligence-v888-human.js?v=888','pi888-human-addon');
    loadAddon('app-coherence-v892.js?v=892&audit=919','app892-coherence-addon');
    loadAddon('symphony2-live-ui-v201.js?v=201','symphony2-live-ui-v201');
    loadStyle('neuro-shadow-v936.css?v=936','neuro-shadow-v936-css');
    loadAddon('neuro-shadow-v936.js?v=936','neuro-shadow-v936-js');
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',loadUxHotfixes,{once:true});else loadUxHotfixes();
  window.TENIS_AI_FAST_BOOT_V888=Object.freeze({version:'v8.8.8',clear:clearDataCache,snapshot:()=>({...state,cached:cache.size,inflight:inflight.size})});
})();

/* Exact Superbet UI bootstrap for Symphony 2.0 era. */
(() => {
  'use strict';
  function fullDom(){return typeof document!=='undefined'&&typeof document.getElementById==='function'&&typeof document.createElement==='function'&&!!document.body&&typeof document.body.appendChild==='function'}
  function load(src,id,onload){
    if(!fullDom())return;if(document.getElementById(id)){onload?.();return}
    const s=document.createElement('script');s.id=id;s.src=src;s.async=false;
    if(onload&&typeof s.addEventListener==='function')s.addEventListener('load',onload,{once:true});document.body.appendChild(s);
  }
  function boot(){
    if(!fullDom())return;
    const freshness=()=>load('playable-line-freshness-v925.js?v=925','playable-line-freshness-v925');
    if(window.TENIS_AI_PLAYABLE_UI_V917)freshness();else load('playable-ui-coherence-v917.js?v=925','playable-ui-coherence-v917',freshness);
  }
  if(typeof document!=='undefined'&&document.readyState==='loading'&&typeof document.addEventListener==='function')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();