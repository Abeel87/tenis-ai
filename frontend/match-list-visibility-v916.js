/* Tenis AI v9.1.6 — separate match visibility from model / Superbet readiness.
   Main match list follows the current fixture set. Model readiness,
   Superbet availability and Symphony PLAYABLE only control content inside a match.
*/
(()=>{
'use strict';

const VERSION='v9.1.8';
const previousFilteredReady=typeof filteredReady==='function'?filteredReady:null;

function visibleMatches(now=Date.now()){
  return (Array.isArray(all)?all:[]).filter(m=>{
    if(!m)return false;
    const time=window.TENIS_AI_MATCH_TIME;
    if(time)return time.isCurrent(m,now);
    // Compatibility fallback if the shared clock has not loaded yet.
    return (typeof clientCurrent!=='function'||clientCurrent(m))
      &&!window.TENIS_AI_E0_1?.isUnavailableFixture(m);
  });
}

function analysisReadyMatches(){
  try{return previousFilteredReady?previousFilteredReady():[]}
  catch{return []}
}

// ui-v751 currentRows(), legacy renderMatches() and updateCounts() all resolve
// filteredReady dynamically. Model readiness must not hide fixtures, but the
// backend snapshot still ages between deployments: retain lifecycle/time guards.
filteredReady=function(){return visibleMatches()};

const matchKey=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));

// Called by the existing global clock and on foreground return. Remove only
// expired entries; do not rebuild cards, collapse groups or close match details.
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
  const top=document.querySelector('#app .p751-top');
  if(top){
    const n=top.querySelectorAll('[data-p751-open]').length;
    if(!n)top.remove();
    else{
      const label=top.querySelector('header span');
      if(label)label.textContent=label.textContent.replace(/^\d+/,String(n));
    }
  }
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

function loadPlayableUiV917(){
  if(window.TENIS_AI_PLAYABLE_UI_V917||document.querySelector('script[data-playable-ui-v917]'))return;
  const script=document.createElement('script');
  script.src='playable-ui-coherence-v917.js?v=917&audit=919';
  script.async=false;
  script.dataset.playableUiV917='1';
  document.head.appendChild(script);
}

window.TENIS_AI_MATCH_VISIBILITY_V916=Object.freeze({
  version:VERSION,
  visibleMatches,
  analysisReadyMatches,
  refreshClock,
  refresh:refreshVisibleUi
});

// If app.js has already finished loading data, refresh immediately. Otherwise
// its normal load() path will use the replacement selector when results arrive.
if(Array.isArray(all)&&all.length){queueMicrotask(refreshVisibleUi)}

// v9.1.7 is intentionally loaded on the next task. match-list-visibility-v916
// sits before Symphony scripts in index.html; waiting one task guarantees that
// the PLAYABLE coherence layer wraps the final UI APIs instead of racing them.
setTimeout(loadPlayableUiV917,0);
})();
