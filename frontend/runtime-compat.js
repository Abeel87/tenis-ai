/* Tenis AI v8.4E0.1 — Fixture + History Freshness Hotfix
   - terminal/unavailable fixtures never reach active match lists / Scenario Generator
   - entering History refreshes only history.json + history_stats.json
   - never re-downloads results.json for a History-tab refresh
*/
(function(root){
  'use strict';

  const VERSION='v8.5.3-runtime';
  const HISTORY_REFRESH_MIN_MS=60000;

  function lifecycleStatus(match){
    const candidates=[match?.event_status,match?.feed_status,match?.status];
    const value=candidates.find(v=>String(v??'').trim().length>0);
    return String(value??'').trim().toLowerCase();
  }

  function isUnavailableFixture(match){
    const s=lifecycleStatus(match);
    if(!s)return false;
    return (
      /cancelled|canceled/.test(s) ||
      /walk\s*over|walkover/.test(s) ||
      /abandoned/.test(s) ||
      /postponed/.test(s) ||
      /retired|retirement/.test(s) ||
      /finished|complete|completed|ended/.test(s)
    );
  }

  // CommonJS support for the small pure-status unit test.
  if(typeof module!=='undefined' && module.exports){
    module.exports={VERSION,lifecycleStatus,isUnavailableFixture};
    return;
  }

  let baseFilteredReady=null;
  try{
    if(typeof filteredReady==='function')baseFilteredReady=filteredReady;
  }catch{}

  if(baseFilteredReady && !baseFilteredReady.__v84e01_wrapped){
    const wrapped=function(){
      const rows=baseFilteredReady();
      return Array.isArray(rows)?rows.filter(m=>!isUnavailableFixture(m)):[];
    };
    wrapped.__v84e01_wrapped=true;
    wrapped.__v84e01_base=baseFilteredReady;
    try{ filteredReady=wrapped; }catch{ root.filteredReady=wrapped; }
  }

  let historyRefreshPromise=null;
  let lastHistoryRefreshAt=0;

  function historyAlreadyLoaded(){
    try{return Array.isArray(historyRows)}catch{return false}
  }

  async function freshJson(path){
    const sep=path.includes('?')?'&':'?';
    const response=await fetch(`${path}${sep}ts=${Date.now()}&hf=84e01`,{cache:'no-store'});
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function refreshHistoryOnly(force=false){
    const now=Date.now();
    if(!force && lastHistoryRefreshAt===0 && historyAlreadyLoaded()){
      lastHistoryRefreshAt=now;
      return true;
    }
    if(!force && now-lastHistoryRefreshAt<HISTORY_REFRESH_MIN_MS)return true;
    if(historyRefreshPromise)return historyRefreshPromise;

    historyRefreshPromise=(async()=>{
      try{
        const [hist,stats]=await Promise.all([
          freshJson('data/history.json'),
          freshJson('data/history_stats.json')
        ]);

        if(Array.isArray(hist)){
          try{ historyRows=hist; }catch{}
        }
        if(stats && typeof stats==='object' && !Array.isArray(stats)){
          try{ statsData=stats; }catch{}
        }

        lastHistoryRefreshAt=Date.now();

        try{
          if(typeof view!=='undefined' && view==='history' && typeof renderHistory==='function'){
            renderHistory();
          }
        }catch{}
        return true;
      }catch(error){
        console.warn('[Tenis AI v8.4E0.1] History refresh failed:',error);
        return false;
      }finally{
        historyRefreshPromise=null;
      }
    })();

    return historyRefreshPromise;
  }

  function bindHistoryRefresh(){
    document.addEventListener('click',event=>{
      const button=event.target?.closest?.('.main-tabs button[data-view="history"]');
      if(button)refreshHistoryOnly(false);
    });

    document.addEventListener('visibilitychange',()=>{
      try{
        if(!document.hidden && typeof view!=='undefined' && view==='history'){
          refreshHistoryOnly(false);
        }
      }catch{}
    });
  }

  root.TENIS_AI_E0_1=Object.freeze({
    version:VERSION,
    lifecycleStatus,
    isUnavailableFixture,
    refreshHistory:()=>refreshHistoryOnly(true)
  });

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',bindHistoryRefresh,{once:true});
  }else{
    bindHistoryRefresh();
  }
})(typeof window!=='undefined'?window:globalThis);
