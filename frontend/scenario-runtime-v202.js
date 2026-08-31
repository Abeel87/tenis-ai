/* Tenis AI — Scenario runtime v2.0.4
   Runtime-only reliability layer for the existing Scenario Composer.
   It does not change generator scoring, model math, market selection or thresholds. */
(() => {
  'use strict';

  const VERSION='v2.0.4';
  const READY_TIMEOUT_MS=1200;
  const API_TIMEOUT_MS=2200;
  const MAX_DRAFT_ITEMS=32;
  const DRAFT_KEY='tenis-ai-v82a-scenario-draft';
  const STUDIO_SRC='scenario-studio-v82a.js?v=82a6&recovery=204';
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

  function sanitizeLegacyDraft(){
    try{
      const raw=localStorage.getItem(DRAFT_KEY);
      if(!raw)return false;
      const data=JSON.parse(raw);
      const invalid=!data||typeof data!=='object'||!Array.isArray(data.items)||data.items.length>MAX_DRAFT_ITEMS;
      if(!invalid)return false;
      localStorage.removeItem(DRAFT_KEY);
      console.warn('[Scenario runtime] Removed corrupted legacy open draft; saved scenario history was untouched.');
      return true;
    }catch{
      try{localStorage.removeItem(DRAFT_KEY)}catch{}
      return true;
    }
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
      document.getElementById('scenario-studio-recovery-v204')?.remove();
      const s=document.createElement('script');
      s.id='scenario-studio-recovery-v204';
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
    try{
      if(tryOpen(api,tab))return true;
    }catch(err){
      console.warn('[Scenario runtime] first open failed; retrying clean Studio bootstrap',err);
    }

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
    if(nav.dataset.scenarioDirectNav==='204')return true;

    // ui-v751 used to own this button and could silently mark it active even when
    // TENIS_AI_SCENARIOS was missing. v2.0.4 replaces that handler directly.
    nav.onclick=directNavClick;
    nav.dataset.scenarioDirectNav='204';
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

  // Capture fallback: protects against another late UI layer replacing onclick.
  document.addEventListener('click',e=>{
    const nav=e.target?.closest?.(NAV_SELECTOR);
    if(nav){
      if(nav.dataset.scenarioDirectNav!=='204')bindDirectNav();
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation?.();
      directNavClick(e);
      return;
    }

    if(e.target?.closest?.('[data-sc-generate]')){
      hardenQualityGuard();
    }
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
    loadStudioFresh,
    bindDirectNav,
    openScenarios
  });
})();