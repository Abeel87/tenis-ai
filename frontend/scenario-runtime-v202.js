/* Tenis AI — Scenario runtime v2.0.2
   Runtime-only reliability layer for the existing Scenario Composer.
   It does not change generator scoring, model math, market selection or thresholds. */
(() => {
  'use strict';
  if(window.TENIS_AI_SCENARIO_RUNTIME_V202)return;

  const VERSION='v2.0.2';
  const READY_TIMEOUT_MS=1200;

  function resolvedAfter(ms){return new Promise(resolve=>setTimeout(resolve,ms))}

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

  function openScenarios(tab='home'){
    const api=window.TENIS_AI_SCENARIOS;
    if(!api?.open)return false;
    api.open(tab);
    document.querySelectorAll('#p751-bottom-nav [data-p751-nav]').forEach(btn=>{
      btn.classList.toggle('active',btn.dataset.p751Nav==='scenarios');
    });
    return true;
  }

  hardenQualityGuard();

  document.addEventListener('click',e=>{
    const nav=e.target?.closest?.('#p751-bottom-nav [data-p751-nav="scenarios"]');
    if(nav){
      if(openScenarios('home')){
        e.preventDefault();
        e.stopImmediatePropagation?.();
      }else{
        setTimeout(()=>openScenarios('home'),50);
      }
      return;
    }

    if(e.target?.closest?.('[data-sc-generate]')){
      hardenQualityGuard();
    }
  },true);

  window.addEventListener('pageshow',hardenQualityGuard);
  window.TENIS_AI_SCENARIO_RUNTIME_V202=Object.freeze({
    version:VERSION,
    readyTimeoutMs:READY_TIMEOUT_MS,
    hardenQualityGuard,
    openScenarios
  });
})();