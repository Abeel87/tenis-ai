/* Tenis AI v9.1.6 — separate match visibility from model / Superbet readiness.
   Main match list follows the backend-visible fixture set. Model readiness,
   Superbet availability and Symphony PLAYABLE only control content inside a match.
*/
(()=>{
'use strict';

const VERSION='v9.1.6';
const previousFilteredReady=typeof filteredReady==='function'?filteredReady:null;

function visibleMatches(){
  return (Array.isArray(all)?all:[]).filter(Boolean);
}

function analysisReadyMatches(){
  try{return previousFilteredReady?previousFilteredReady():[]}
  catch{return []}
}

// ui-v751 currentRows(), legacy renderMatches() and updateCounts() all resolve
// filteredReady dynamically. Point only that display selector at the complete
// backend-visible fixture list; do not touch model math or PLAYABLE gates.
filteredReady=function(){return visibleMatches()};

function refreshVisibleUi(){
  try{if(typeof updateCounts==='function')updateCounts()}catch{}
  try{
    if(typeof view==='undefined'||view==='matches'){
      if(typeof renderMatches==='function')renderMatches();
    }
  }catch{}
}

window.TENIS_AI_MATCH_VISIBILITY_V916=Object.freeze({
  version:VERSION,
  visibleMatches,
  analysisReadyMatches,
  refresh:refreshVisibleUi
});

// If app.js has already finished loading data, refresh immediately. Otherwise
// its normal load() path will use the replacement selector when results arrive.
if(Array.isArray(all)&&all.length){queueMicrotask(refreshVisibleUi)}
})();
