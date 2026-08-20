/* Tenis AI v7.1.1 — czytelne etykiety modelu i jakości danych */
(() => {
  function rewrite(root=document){
    root.querySelectorAll('.match-score > span, .player-current-meta span').forEach(el=>{
      const t=(el.textContent||'').trim();
      const m=t.match(/^MODEL\s+(\d+(?:\.\d+)?)$/i);
      if(m) el.textContent=`JAKOŚĆ DANYCH ${Math.round(Number(m[1]))}/100`;
    });

    root.querySelectorAll('.marketbox .tag').forEach(el=>{
      const t=(el.textContent||'').trim();
      if(/^MODEL BO3\b/i.test(t)){
        el.textContent=t.replace(/^MODEL BO3/i,'PREDYKCJA BO3');
      }else if(/^MODEL\b/i.test(t)){
        el.textContent=t.replace(/^MODEL/i,'PREDYKCJA');
      }
    });
  }

  let queued=false;
  const queue=()=>{
    if(queued)return;
    queued=true;
    requestAnimationFrame(()=>{
      queued=false;
      rewrite(document);
    });
  };

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',queue,{once:true});
  else queue();

  const obs=new MutationObserver(queue);
  obs.observe(document.body,{childList:true,subtree:true});
})();