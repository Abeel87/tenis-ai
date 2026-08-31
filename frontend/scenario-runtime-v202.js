/* Tenis AI — Scenario runtime v2.0.6
   Runtime-only reliability layer for the existing Scenario Composer.
   It does not change generator scoring, model math, market selection or thresholds. */
(() => {
  'use strict';

  const VERSION='v2.0.6';
  const READY_TIMEOUT_MS=1200;
  const API_TIMEOUT_MS=2200;
  const MAX_DRAFT_ITEMS=32;
  const DRAFT_KEY='tenis-ai-v82a-scenario-draft';
  const BROKEN_DRAFT_BACKUP_KEY='tenis-ai-v82a-scenario-draft-recovery';
  const STUDIO_SRC='scenario-studio-v82a.js?v=82a6&recovery=206';
  const NAV_SELECTOR='#p751-bottom-nav [data-p751-nav="scenarios"]';
  let studioReloadPromise=null;
  let navBindTimer=null;

  function resolvedAfter(ms,value){return new Promise(resolve=>setTimeout(()=>resolve(value),ms))}

  function hardenQualityGuard(){
    const guard=window.TENIS_AI_GENERATOR_QUALITY_V888;
    if(!guard||guard.__scenarioRuntimeV202)return guard||null;
    if(typeof guard.checkGroup!=='function')return guard;

    const guardedReady=Promise.race([
      Promise.resolve(guard.ready).catch(()=>undefined),
      resolvedAfter(READY_TIMEOUT_MS)
    ]);

    const wrapped=Object.freeze({
      ...guard,
      ready:guardedReady,
      __scenarioRuntimeV202:true,
      scenario_ready_timeout_ms:READY_TIMEOUT_MS
    });
    window.TENIS_AI_GENERATOR_QUALITY_V888=wrapped;
    return wrapped;
  }

  function scenarioApi(){
    const api=window.TENIS_AI_SCENARIOS;
    return api&&typeof api.open==='function'?api:null;
  }

  function panelVisible(){
    const panel=document.querySelector('#scenario-v82a-panel');
    if(!panel||panel.hidden)return false;
    try{return getComputedStyle(panel).display!=='none'}catch{return true}
  }

  function draftShape(raw){
    try{
      const data=JSON.parse(raw||'null');
      if(!data||typeof data!=='object'||Array.isArray(data)||!Array.isArray(data.items))return {valid:false,data:null};
      if(data.items.length>MAX_DRAFT_ITEMS)return {valid:false,data};
      const validItems=data.items.filter(item=>item&&typeof item==='object'&&!Array.isArray(item));
      return {valid:validItems.length===data.items.length,data,validItems};
    }catch{return {valid:false,data:null}}
  }

  function sanitizeLegacyDraft(){
    let raw=null;
    try{raw=localStorage.getItem(DRAFT_KEY)}catch{return false}
    if(!raw)return false;
    const shape=draftShape(raw);
    if(shape.valid)return false;
    try{
      localStorage.setItem(BROKEN_DRAFT_BACKUP_KEY,raw);
      localStorage.removeItem(DRAFT_KEY);
      console.warn('[Scenario runtime] Quarantined broken open draft; saved scenario history was untouched.');
    }catch{}
    return true;
  }

  function quarantineOpenDraft(reason='open-failed'){
    try{
      const raw=localStorage.getItem(DRAFT_KEY);
      if(raw)localStorage.setItem(BROKEN_DRAFT_BACKUP_KEY,raw);
      localStorage.removeItem(DRAFT_KEY);
      console.warn(`[Scenario runtime] Cleared only the open draft after ${reason}; saved scenario history was untouched.`);
      return !!raw;
    }catch{return false}
  }

  function removeBrokenShell(){
    document.querySelector('#scenario-v82a-panel')?.remove();
    document.querySelector('#scenario-v82a-dock')?.remove();
  }

  function resetStudioRuntime(){
    try{delete window.TENIS_AI_SCENARIOS}catch{window.TENIS_AI_SCENARIOS=null}
    removeBrokenShell();
  }

  function loadStudioFresh(){
    if(scenarioApi())return Promise.resolve(scenarioApi());
    if(studioReloadPromise)return studioReloadPromise;
    removeBrokenShell();
    studioReloadPromise=new Promise(resolve=>{
      document.getElementById('scenario-studio-recovery-v206')?.remove();
      const s=document.createElement('script');
      s.id='scenario-studio-recovery-v206';
      s.src=`${STUDIO_SRC}&ts=${Date.now()}`;
      s.async=false;
      s.onload=()=>resolve(scenarioApi());
      s.onerror=()=>resolve(null);
      document.body.appendChild(s);
    }).finally(()=>{studioReloadPromise=null});
    return Promise.race([studioReloadPromise,resolvedAfter(API_TIMEOUT_MS,null)]);
  }

  function markScenarioNav(){
    document.querySelectorAll('#p751-bottom-nav [data-p751-nav]').forEach(btn=>{
      btn.classList.toggle('active',btn.dataset.p751Nav==='scenarios');
    });
  }

  function tryOpen(api,tab){
    if(!api?.open)return false;
    api.open(tab);
    if(!panelVisible())return false;
    markScenarioNav();
    return true;
  }

  async function openScenarios(tab='home'){
    let api=scenarioApi();
    if(!api)api=await loadStudioFresh();
    let firstError=null;
    try{
      if(tryOpen(api,tab))return true;
    }catch(err){
      firstError=err;
      console.warn('[Scenario runtime] first open failed; rebuilding Studio with a clean open draft',err);
    }

    // Studio reads the open draft once during script evaluation. A malformed legacy
    // item can therefore remain broken in memory even after localStorage is cleaned.
    // Quarantine only the OPEN draft, rebuild Studio, and leave saved scenarios intact.
    quarantineOpenDraft(firstError?'render-exception':'panel-not-visible');
    resetStudioRuntime();
    api=await loadStudioFresh();
    try{
      return tryOpen(api,tab);
    }catch(err){
      console.error('[Scenario runtime] clean Studio bootstrap failed',err);
      return false;
    }
  }

  async function directNavClick(event){
    event?.preventDefault?.();
    event?.stopPropagation?.();
    hardenQualityGuard();
    const ok=await openScenarios('home');
    if(!ok)console.error('[Scenario runtime] Scenario Composer could not be opened');
    return ok;
  }

  function bindDirectNav(){
    const nav=document.querySelector(NAV_SELECTOR);
    if(!nav)return false;
    if(nav.dataset.scenarioDirectNav==='206')return true;
    nav.onclick=directNavClick;
    nav.dataset.scenarioDirectNav='206';
    return true;
  }

  function scheduleDirectNavBind(){
    clearTimeout(navBindTimer);
    if(bindDirectNav())return;
    [50,200,700,1500,3000].forEach(ms=>setTimeout(bindDirectNav,ms));
  }

  sanitizeLegacyDraft();
  hardenQualityGuard();
  scheduleDirectNavBind();

  document.addEventListener('click',e=>{
    const nav=e.target?.closest?.(NAV_SELECTOR);
    if(nav){
      if(nav.dataset.scenarioDirectNav!=='206')bindDirectNav();
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation?.();
      directNavClick(e);
      return;
    }
    if(e.target?.closest?.('[data-sc-generate]'))hardenQualityGuard();
  },true);

  document.addEventListener('tenis-ai:ui-ready',scheduleDirectNavBind);
  window.addEventListener('pageshow',()=>{
    hardenQualityGuard();
    scheduleDirectNavBind();
    if(!scenarioApi())loadStudioFresh();
  });

  setTimeout(()=>{
    scheduleDirectNavBind();
    if(!scenarioApi())loadStudioFresh();
  },300);

  window.TENIS_AI_SCENARIO_RUNTIME_V202=Object.freeze({
    version:VERSION,
    readyTimeoutMs:READY_TIMEOUT_MS,
    apiTimeoutMs:API_TIMEOUT_MS,
    hardenQualityGuard,
    sanitizeLegacyDraft,
    quarantineOpenDraft,
    loadStudioFresh,
    bindDirectNav,
    openScenarios
  });
})();