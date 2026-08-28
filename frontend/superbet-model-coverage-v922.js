/* Tenis AI v9.2.2 — model probability beside each real Superbet selection.
   UI-only bridge. MODEL/RAW ownership remains untouched. */
(()=>{
'use strict';
if(window.TENIS_AI_SUPERBET_MODEL_COVERAGE_V922)return;
const VERSION='v9.2.2';
let queued=false;

const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const decode=v=>{try{return decodeURIComponent(String(v||''))}catch{return String(v||'')}};
const fmt=v=>finite(v)?`${Number(v).toFixed(1).replace('.0','')}%`:'—';
const key=r=>[
  r?.market||'',r?.checkpoint||'',r?.player||'',
  r?.line!==null&&r?.line!==undefined?r.line:'',r?.pick||''
].map(String).join('|');

function style(){
 if(document.getElementById('sbmc922-style'))return;
 const s=document.createElement('style');s.id='sbmc922-style';s.textContent=`
 .rp921-line strong.sbmc922-value{display:flex;flex-direction:column;align-items:flex-end;justify-content:center;gap:.08rem;min-width:92px;line-height:1.15}
 .sbmc922-model{font-size:.67rem;color:#dfffb7;white-space:nowrap}.sbmc922-model.missing{color:#94a8b0;font-size:.59rem}.sbmc922-model.shadow{color:#e4c5ff}.sbmc922-meta{font-size:.52rem!important;color:#83a0aa!important;white-space:nowrap}
 `;document.head.appendChild(s)
}

function findMatch(raw){
 const k=decode(raw).replace(/^id:/,'');
 try{return window.TENIS_AI_PROJECT_UI?.findMatch?.(k)||null}catch{return null}
}

function superbetDetails(panel){
 for(const details of panel?.querySelectorAll?.('details')||[]){
  const summary=details.querySelector('summary');
  if(String(summary?.textContent||'').toUpperCase().includes('SUPERBET'))return details;
 }
 return null;
}

function renderValue(strong,signal){
 if(!strong)return;
 strong.classList.add('sbmc922-value');
 let html='';
 if(signal&&finite(signal.score)){
  const approximate=String(signal.probability_semantics||'').includes('approximation');
  const shadow=String(signal.coverage_status||'').includes('SHADOW');
  const push=finite(signal.push_probability)&&Number(signal.push_probability)>0.04?`PUSH ${fmt(signal.push_probability)} · `:'';
  const status=shadow?'SHADOW · ':'';
  html=`<span class="sbmc922-model${shadow?' shadow':''}">MODEL ${approximate?'~':''}${fmt(signal.score)}</span><small class="sbmc922-meta">${push}${status}Superbet ✓</small>`;
 }else{
  html='<span class="sbmc922-model missing">MODEL: niepokryty</span><small class="sbmc922-meta">Superbet ✓</small>';
 }
 if(strong.innerHTML!==html)strong.innerHTML=html;
}

function annotate(){
 queued=false;style();
 const overlay=document.querySelector('#p751-match-overlay:not([hidden])');
 if(!overlay)return;
 const match=findMatch(overlay.dataset.matchKey||'');
 if(!match)return;
 const panel=overlay.querySelector('[data-rp921-match]');
 const details=superbetDetails(panel);
 if(!details)return;
 const ctx=match.superbet_market_v91||{};
 const selections=(Array.isArray(ctx.canonical_selections)?ctx.canonical_selections:[]).filter(r=>r&&r.operator_available!==false);
 const playable=Array.isArray(ctx.model_signals)?ctx.model_signals:[];
 const shadow=Array.isArray(ctx.coverage_shadow_signals)?ctx.coverage_shadow_signals:[];
 const byKey=new Map([...playable,...shadow].map(r=>[key(r),r]));
 const rows=[...details.querySelectorAll('.rp921-line')];
 rows.forEach((row,i)=>{
  const selection=selections[i];
  if(!selection)return;
  renderValue(row.querySelector('strong'),byKey.get(key(selection))||null);
 });
}

function schedule(){if(queued)return;queued=true;queueMicrotask(annotate)}
const observer=new MutationObserver(schedule);
observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden','data-match-key']});
document.addEventListener('click',schedule,true);
document.addEventListener('visibilitychange',schedule);
setTimeout(schedule,0);

window.TENIS_AI_SUPERBET_MODEL_COVERAGE_V922=Object.freeze({version:VERSION,refresh:schedule,key});
})();