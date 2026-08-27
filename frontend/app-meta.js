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
    generatorPolicyVersion: 'v8.8.8-market-quality-lock',
    modelName: 'AutoLearn Ensemble + Adaptive Learning',
    productionModelName: 'AutoLearn Ensemble + Dynamic Weights + Adaptive PROD',
    adaptiveVersion: 'v7.9B-bayesian-meta',
    uiArchitecture: 'v8.0.1-clean-core',
    currentUiArchitecture: 'v8.8.7-checkpoint-quality-lock',
    cacheVersion: 'v801',
    runtimeCacheVersion: 'v87'
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
