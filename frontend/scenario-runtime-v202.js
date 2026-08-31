/* Tenis AI — Scenario runtime v2.0.3
   Runtime-only reliability layer for the existing Scenario Composer.
   It does not change generator scoring, model math, market selection or thresholds. */
(() => {
  'use strict';
  if(window.TENIS_AI_SCENARIO_RUNTIME_V202)return;

  const VERSION='v2.0.3';
  const READY_TIMEOUT_MS=1200;
  const API_TIMEOUT_MS=2200;
  const STUDIO_SRC='scenario-studio-v82a.js?v=82a6&recovery=203';
  let studioReloadPromise=null;

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

  function removeBrokenShell(){
    const panel=document.querySelector('#scenario-v82a-panel');
    if(panel&&!scenarioApi())panel.remove();
    const dock=document.querySelector('#scenario-v82a-dock');
    if(dock&&!scenarioApi())dock.remove();
  }

  function loadStudioFresh(){
    if(scenarioApi())return Promise.resolve(scenarioApi());
    if(studioReloadPromise)return studioReloadPromise;
    removeBrokenShell();
    studioReloadPromise=new Promise(resolve=>{
      const old=document.getElementById('scenario-studio-recovery-v203');
      old?.remove();
      const s=document.createElement('script');
      s.id='scenario-studio-recovery-v203';
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

  async function openScenarios(tab='home'){
    let api=scenarioApi();
    if(!api)api=await loadStudioFresh();
    if(!api?.open)return false;
    try{
      api.open(tab);
      markScenarioNav();
      return !document.querySelector('#scenario-v82a-panel')?.hidden;
    }catch(err){
      console.warn('[Scenario runtime] open failed; retrying clean studio bootstrap',err);
      try{delete window.TENIS_AI_SCENARIOS}catch{window.TENIS_AI_SCENARIOS=null}
      removeBrokenShell();
      api=await loadStudioFresh();
      if(!api?.open)return false;
      api.open(tab);
      markScenarioNav();
      return !document.querySelector('#scenario-v82a-panel')?.hidden;
    }
  }

  hardenQualityGuard();

  document.addEventListener('click',e=>{
    const nav=e.target?.closest?.('#p751-bottom-nav [data-p751-nav="scenarios"]');
    if(nav){
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation?.();
      openScenarios('home').then(ok=>{
        if(!ok)console.error('[Scenario runtime] Scenario Composer could not be opened');
      });
      return;
    }

    if(e.target?.closest?.('[data-sc-generate]')){
      hardenQualityGuard();
    }
  },true);

  window.addEventListener('pageshow',()=>{
    hardenQualityGuard();
    if(!scenarioApi())loadStudioFresh();
  });

  setTimeout(()=>{
    if(!scenarioApi())loadStudioFresh();
  },300);

  window.TENIS_AI_SCENARIO_RUNTIME_V202=Object.freeze({
    version:VERSION,
    readyTimeoutMs:READY_TIMEOUT_MS,
    apiTimeoutMs:API_TIMEOUT_MS,
    hardenQualityGuard,
    loadStudioFresh,
    openScenarios
  });
})();