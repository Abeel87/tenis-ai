/* Tenis AI v8.0.1 — central app metadata */
(() => {
  const META = Object.freeze({
    appVersion: 'v8.0.1',
    modelVersion: 'v7.8D',
    modelName: 'Calibration Guard + Adaptive Learning',
    adaptiveVersion: 'v7.9B-bayesian-meta',
    uiArchitecture: 'v8.0.1-clean-core',
    cacheVersion: 'v801'
  });

  window.TENIS_AI_META = META;

  function applyMeta(){
    document.documentElement.dataset.tenisAiVersion=META.appVersion;
    document.title=`Tenis AI · ${META.appVersion}`;
    const p=document.querySelector('.brand-copy p');
    if(p)p.textContent=`Tenis AI ${META.appVersion} · Adaptive Learning`;
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyMeta,{once:true});
  else applyMeta();
})();
