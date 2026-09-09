/* Tenis AI v9.5.0.1 — canonical Match Detail information architecture.
   Presentation only. It does not calculate model scores, Symphony decisions,
   Superbet availability, PLAYABLE status, calibration or Player Intelligence.
   Order contract: Symphony 2.0 final PLAYABLE -> model context -> diagnostics.
*/
(()=>{
'use strict';
if(window.TENIS_AI_MATCH_DETAIL_V950)return;
const VERSION='v9.5.0.1';
// Contract: final PLAYABLE = Symfonia 2.0; zweryfikowana oferta Superbet jest osobną warstwą.
const ROOT='#app[data-match-key] .p751-detail-screen';
function label(text,kind){const el=document.createElement('div');el.className='p751-note v950-detail-label';el.dataset.v950Label=kind;const b=document.createElement('b');b.textContent=text;el.append(b);return el}
function removeOldLabels(root){root.querySelectorAll('[data-v950-label]').forEach(el=>el.remove())}
function organize(){
  const root=document.querySelector(ROOT);if(!root)return false;
  removeOldLabels(root);
  root.dataset.v950Organized='1';
  return true;
}
let timer=0;function schedule(ms=0){clearTimeout(timer);timer=setTimeout(organize,ms)}
function boot(){schedule(0);document.addEventListener('click',event=>{if(event.target?.closest?.('[data-p751-open],[data-v917-top]'))schedule(40)},true)}
window.TENIS_AI_MATCH_DETAIL_V950=Object.freeze({version:VERSION,organize,schedule});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
