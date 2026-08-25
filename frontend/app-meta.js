/* Tenis AI v8.0.1 — central app metadata */
/* v8.5.3 display/runtime compatibility layer */
(() => {
  const META = Object.freeze({
    appVersion: 'v8.0.1',
    displayVersion: 'v8.5.3',
    modelVersion: 'v7.8D',
    calibrationModelVersion: 'v7.8D-calibration-guard',
    productionModelVersion: 'v8.4B',
    dynamicWeightsVersion: 'v8.4D',
    playerIntelligenceVersion: 'v8.5',
    generatorPolicyVersion: 'v8.5.2-quality-lock',
    modelName: 'Calibration Guard + Adaptive Learning',
    productionModelName: 'AutoLearn Ensemble + Dynamic Weights + Player Intelligence',
    adaptiveVersion: 'v7.9B-bayesian-meta',
    uiArchitecture: 'v8.0.1-clean-core',
    currentUiArchitecture: 'v8.5.3-grouped-signals',
    cacheVersion: 'v801',
    runtimeCacheVersion: 'v853'
  });

  window.TENIS_AI_META = META;

  function applyMeta(){
    document.documentElement.dataset.tenisAiVersion=META.displayVersion||META.appVersion;
    document.title=`Tenis AI · ${META.displayVersion||META.appVersion}`;
    const p=document.querySelector('.brand-copy p');
    if(p)p.textContent=`Tenis AI ${META.displayVersion||META.appVersion} · AutoLearn + Player Intelligence`;
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyMeta,{once:true});
  else applyMeta();
})();
