/* Tenis AI v8.8.3 · final UI cleanup.
   No model math changes. This layer only unifies visible versioning
   and removes legacy stats clutter.
   v8.8.20 runtime cleanup: explicit events replace delayed global polish loops.
*/
(()=>{
'use strict';

const VERSION='v8.8.3';
const RUNTIME_FIX='v8.8.20';

function cleanupStats(){
  document.querySelectorAll('#pc88-dashboard').forEach(x=>x.remove());

  const host=document.querySelector('#pc77');
  const dash=document.querySelector('#pc882-dashboard');
  if(!host||!dash)return;

  const title=dash.querySelector('.pc882-head span');
  if(title)title.textContent='CENTRUM SKUTECZNOŚCI';

  let legacy=host.querySelector('#pc882-legacy');
  if(!legacy){
    legacy=document.createElement('details');
    legacy.id='pc882-legacy';
    legacy.className='pc882-legacy';
    legacy.innerHTML='<summary><b>PRO / pełna diagnostyka</b><span>starsze tabele, Player SH, telemetry i audyt</span></summary><div class="pc882-legacy-body"></div>';
    host.append(legacy);
  }else{
    const b=legacy.querySelector('summary b');
    const s=legacy.querySelector('summary span');
    if(b)b.textContent='PRO / pełna diagnostyka';
    if(s)s.textContent='starsze tabele, Player SH, telemetry i audyt';
  }

  const body=legacy.querySelector('.pc882-legacy-body');
  if(!body)return;
  const head=host.querySelector('.pc77-head');

  [...host.children].forEach(node=>{
    if(node===head||node===dash||node===legacy||node.id==='coh892-shadow')return;
    body.append(node);
  });
}

function brand(){
  window.TENIS_AI_APPLY_META?.();
  document.documentElement.dataset.tenisAiFeatureVersion=window.TENIS_AI_META?.displayVersion||VERSION;

  // Visible release labels belong to app-meta; feature versions stay internal.
}

function compactAdaptive(){
  const h=document.querySelector('#v79-health');
  if(!h)return;
  let expanded='0';
  try{expanded=localStorage.getItem('tenis-ai-v882-adaptive-expanded')||'0'}catch{}
  if(expanded!=='1')h.classList.remove('expanded');
}

function polish(){
  brand();
  compactAdaptive();
  cleanupStats();
}

function boot(){
  brand();
  compactAdaptive();
  cleanupStats();
}

document.addEventListener('tenis-ai:stats-ready',()=>queueMicrotask(cleanupStats));
document.addEventListener('tenis-ai:stats-dashboard-ready',()=>queueMicrotask(cleanupStats));
document.addEventListener('visibilitychange',()=>{
  if(document.hidden)return;
  brand();
  compactAdaptive();
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_V883=Object.freeze({
  version:VERSION,
  runtimeFix:RUNTIME_FIX,
  polish,
  cleanupStats
});
})();
