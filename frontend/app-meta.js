/* Tenis AI v7.8E10 — central app metadata */
(() => {
  const META = Object.freeze({
    appVersion: 'v7.8E11.4',
    modelVersion: 'v7.8D',
    modelName: 'Calibration Guard',
    cacheVersion: 'v78e114'
  });

  window.TENIS_AI_META = META;

  function applyMeta(){
    document.documentElement.dataset.tenisAiVersion = META.appVersion;
    document.title = `Tenis AI · ${META.appVersion}`;

    const p = document.querySelector('.brand-copy p');
    if(p){
      p.textContent = `Tenis AI ${META.appVersion} · model ${META.modelVersion} ${META.modelName}`;
    }
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', applyMeta, {once:true});
  }else{
    applyMeta();
  }
})();
