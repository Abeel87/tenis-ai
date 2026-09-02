/* Tenis AI v9.1.6 — separate match visibility from model / Superbet readiness.
   Main match list follows the current fixture set. Model readiness,
   Superbet availability and Symphony PLAYABLE only control content inside a match.
*/
(()=>{
'use strict';

const VERSION='v9.3.3';
const previousFilteredReady=typeof filteredReady==='function'?filteredReady:null;

function visibleMatches(now=Date.now()){
  return (Array.isArray(all)?all:[]).filter(m=>{
    if(!m)return false;
    const time=window.TENIS_AI_MATCH_TIME;
    if(time)return time.isCurrent(m,now);
    return (typeof clientCurrent!=='function'||clientCurrent(m))
      &&!window.TENIS_AI_E0_1?.isUnavailableFixture(m);
  });
}

function analysisReadyMatches(){
  try{return previousFilteredReady?previousFilteredReady():[]}
  catch{return []}
}

filteredReady=function(){return visibleMatches()};

const matchKey=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));

function refreshClock(){
  const visible=new Set(visibleMatches().map(matchKey));
  const known=new Set((Array.isArray(all)?all:[]).filter(Boolean).map(matchKey));
  let removed=false;
  document.querySelectorAll('#app .p751-match-card[data-p751-open], #app .p751-top [data-p751-open], #app .p751-signals-page [data-p751-open]').forEach(el=>{
    let key=el.dataset.p751Open;
    try{key=decodeURIComponent(key)}catch{}
    if(known.has(key)&&!visible.has(key)){el.remove();removed=true}
  });
  if(!removed)return;
  document.querySelectorAll('#app .p751-group').forEach(group=>{
    const cards=group.querySelectorAll('.p751-match-card');
    if(!cards.length){group.remove();return}
    const label=group.querySelector('summary small');
    if(label)label.textContent=label.textContent.replace(/^\d+\s+\S+/,`${cards.length} ${cards.length===1?'mecz':'meczów'}`);
  });
  document.querySelectorAll('#app .p751-top').forEach(top=>{
    const n=top.querySelectorAll('[data-p751-open]').length;
    if(!n)top.remove();
    else{
      const label=top.querySelector('header span');
      if(label)label.textContent=label.textContent.replace(/^\d+/,String(n));
    }
  });
  const groups=document.querySelector('#app .p751-groups');
  if(groups&&!groups.querySelector('.p751-group'))groups.innerHTML='<div class="p751-empty"><b>Brak aktualnych meczów dla tego filtra.</b><span>Minęła planowana godzina spotkań. Odśwież dane, aby sprawdzić nowy terminarz.</span></div>';
  if(typeof updateCounts==='function')updateCounts();
}

function refreshVisibleUi(){
  try{if(typeof updateCounts==='function')updateCounts()}catch{}
  try{
    if(typeof view==='undefined'||view==='matches'){
      if(typeof renderMatches==='function')renderMatches();
    }
  }catch{}
}

function loadMarketSegregationV93G(){
  if(window.TENIS_AI_MARKET_SEGREGATION_V93G||document.querySelector('script[data-market-segregation-v93g]'))return;
  const script=document.createElement('script');
  script.src='market-segregation-v93g.js?v=933&contract=superbet-coverage-ui-only';
  script.async=false;
  script.dataset.marketSegregationV93g='1';
  document.head.appendChild(script);
}

function loadSuperbetModelCoverageV922(){
  if(window.TENIS_AI_SUPERBET_MODEL_COVERAGE_V922||document.querySelector('script[data-superbet-model-coverage-v922]')){loadMarketSegregationV93G();return}
  const script=document.createElement('script');
  script.src='superbet-model-coverage-v922.js?v=933&contract=operator-model-coverage';
  script.async=false;
  script.dataset.superbetModelCoverageV922='1';
  script.addEventListener('load',loadMarketSegregationV93G,{once:true});
  document.head.appendChild(script);
}

function loadPlayableUiV917(){
  if(window.TENIS_AI_PLAYABLE_UI_V917){loadSuperbetModelCoverageV922();return}
  const existing=document.querySelector('script[data-playable-ui-v917]');
  if(existing){existing.addEventListener('load',loadSuperbetModelCoverageV922,{once:true});return}
  const script=document.createElement('script');
  script.src='playable-ui-coherence-v917.js?v=948&contract=raw-playable-filter-coherence';
  script.async=false;
  script.dataset.playableUiV917='1';
  script.addEventListener('load',loadSuperbetModelCoverageV922,{once:true});
  document.head.appendChild(script);
}

function loadMatchBrowserV945(){
  if(window.TENIS_AI_MATCH_BROWSER_V945||document.querySelector('script[data-match-browser-v945]'))return;
  const script=document.createElement('script');
  script.src='match-browser-v945.js?v=947&contract=model-output-readiness';
  script.async=false;
  script.dataset.matchBrowserV945='1';
  document.head.appendChild(script);
}

window.TENIS_AI_MATCH_VISIBILITY_V916=Object.freeze({
  version:VERSION,
  visibleMatches,
  analysisReadyMatches,
  refreshClock,
  refresh:refreshVisibleUi
});

if(Array.isArray(all)&&all.length){queueMicrotask(refreshVisibleUi)}

// Current ownership chain: strict PLAYABLE gate -> complete operator/model coverage
// -> presentation-only market grouping. Legacy v921 RAW/Symphony panel is gone.
setTimeout(loadPlayableUiV917,0);
setTimeout(loadMatchBrowserV945,0);
})();
