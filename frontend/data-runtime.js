/* Tenis AI · shared heavy-data runtime.
   Keeps the main app as the single network owner of large JSON payloads.
   Later modules receive the already parsed global data instead of downloading
   and JSON-parsing results/history again. Model calculations are untouched. */
(()=>{
  'use strict';

  const VERSION='v8.4E0';
  const nativeFetch=window.fetch.bind(window);
  const MAX_WAIT_MS=20000;
  const POLL_MS=50;
  const diag={intercepted:0,shared_reads:0,waits:0,fallbacks:0,bypassed_main:0};

  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

  function appSettled(){
    const txt=String(document.querySelector('#updated')?.textContent||'').trim();
    return !!txt && !txt.toLowerCase().startsWith('ładowanie');
  }

  function sharedState(kind){
    try{
      if(kind==='results'){
        const value=Array.isArray(all)?all:null;
        return {ready:!!value&&(value.length>0||appSettled()),value};
      }
      if(kind==='history'){
        const value=Array.isArray(historyRows)?historyRows:null;
        return {ready:!!value&&(value.length>0||appSettled()),value};
      }
      if(kind==='history_stats'){
        const value=statsData&&typeof statsData==='object'?statsData:null;
        return {ready:!!value,value};
      }
    }catch{}
    return {ready:false,value:null};
  }

  async function waitShared(kind){
    let state=sharedState(kind);
    if(state.ready){
      diag.shared_reads++;
      return state;
    }
    diag.waits++;
    const deadline=Date.now()+MAX_WAIT_MS;
    while(Date.now()<deadline){
      await sleep(POLL_MS);
      state=sharedState(kind);
      if(state.ready){
        diag.shared_reads++;
        return state;
      }
    }
    return state;
  }

  function requestInfo(input,init){
    const method=String(init?.method||(input instanceof Request?input.method:'GET')||'GET').toUpperCase();
    if(method!=='GET')return null;
    let url;
    try{url=new URL(input instanceof Request?input.url:String(input),location.href)}catch{return null}
    if(url.origin!==location.origin)return null;

    if(url.searchParams.has('ts')){
      diag.bypassed_main++;
      return null;
    }

    const path=url.pathname;
    if(path.endsWith('/data/results.json'))return {kind:'results',fallback:[]};
    if(path.endsWith('/data/history.json'))return {kind:'history',fallback:[]};
    if(path.endsWith('/data/history_stats.json'))return {kind:'history_stats',fallback:{}};
    return null;
  }

  async function loadShared(info,input,init){
    const state=await waitShared(info.kind);
    if(state.ready)return state.value;

    diag.fallbacks++;
    try{
      const response=await nativeFetch(input,init);
      if(!response.ok)return info.fallback;
      return await response.json();
    }catch{
      return info.fallback;
    }
  }

  function sharedResponse(info,input,init){
    const response=new Response(null,{
      status:200,
      headers:{'Content-Type':'application/json','X-Tenis-AI-Shared-Data':VERSION}
    });
    const json=()=>loadShared(info,input,init);
    response.json=json;
    response.text=async()=>JSON.stringify(await json());
    response.clone=()=>sharedResponse(info,input,init);
    return response;
  }

  window.fetch=function(input,init){
    const info=requestInfo(input,init);
    if(!info)return nativeFetch(input,init);
    diag.intercepted++;
    return Promise.resolve(sharedResponse(info,input,init));
  };

  async function apiGet(kind,path,fallback){
    const state=await waitShared(kind);
    if(state.ready)return state.value;
    diag.fallbacks++;
    try{
      const sep=path.includes('?')?'&':'?';
      const response=await nativeFetch(`${path}${sep}shared=84e0&v=${Date.now()}`,{cache:'no-store'});
      if(!response.ok)return fallback;
      return await response.json();
    }catch{
      return fallback;
    }
  }

  window.TENIS_AI_DATA=Object.freeze({
    version:VERSION,
    results:()=>apiGet('results','data/results.json',[]),
    history:()=>apiGet('history','data/history.json',[]),
    historyStats:()=>apiGet('history_stats','data/history_stats.json',{}),
    diagnostics:()=>({...diag})
  });
})();
