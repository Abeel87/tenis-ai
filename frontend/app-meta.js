/* Tenis AI v7.9B — central app metadata + Adaptive Learning assets */
(() => {
  const META = Object.freeze({
    appVersion: 'v7.9B',
    modelVersion: 'v7.8D',
    modelName: 'Calibration Guard + Adaptive Learning',
    adaptiveVersion: 'v7.9B-bayesian-meta',
    cacheVersion: 'v79b'
  });

  window.TENIS_AI_META = META;

  function loadAdaptiveAssets(){
    if(!document.querySelector('link[data-v79-adaptive]')){
      const css=document.createElement('link');
      css.rel='stylesheet';
      css.href=`adaptive-learning-v79.css?v=${META.cacheVersion}`;
      css.dataset.v79Adaptive='css';
      document.head.appendChild(css);
    }

    if(!document.querySelector('script[data-v79-adaptive]')){
      const js=document.createElement('script');
      js.src=`adaptive-learning-v79.js?v=${META.cacheVersion}`;
      js.dataset.v79Adaptive='js';
      js.async=false;
      document.body.appendChild(js);
    }
  }

  function applyMeta(){
    document.documentElement.dataset.tenisAiVersion = META.appVersion;
    document.title = `Tenis AI · ${META.appVersion}`;

    const p = document.querySelector('.brand-copy p');
    if(p){
      p.textContent = `Tenis AI ${META.appVersion} · model ${META.modelVersion} ${META.modelName}`;
    }

    loadAdaptiveAssets();
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', applyMeta, {once:true});
  }else{
    applyMeta();
  }
})();
