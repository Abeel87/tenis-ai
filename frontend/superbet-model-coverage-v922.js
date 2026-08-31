/* Tenis AI v9.3.3 — complete current Superbet offer with model coverage.
   Operator/UI only. MODEL/RAW remains owned by the base UI; PLAYABLE gating stays in v917. */
(()=>{
'use strict';
if(window.TENIS_AI_SUPERBET_MODEL_COVERAGE_V922)return;
const VERSION='v9.3.3';
let queued=false;

const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const decode=v=>{try{return decodeURIComponent(String(v||''))}catch{return String(v||'')}};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>finite(v)?`${Number(v).toFixed(1).replace('.0','')}%`:'—';
const key=r=>[
  r?.market||'',r?.checkpoint||'',r?.player||'',
  r?.line!==null&&r?.line!==undefined?r.line:'',r?.pick||''
].map(String).join('|');

function style(){
  if(document.getElementById('sbmc922-style'))return;
  const s=document.createElement('style');
  s.id='sbmc922-style';
  s.textContent=`
    .sbmc922-panel{margin:.65rem 0;padding:.72rem;border:1px solid rgba(81,210,245,.17);border-radius:14px;background:rgba(3,22,33,.76)}
    .sbmc922-head{display:flex;justify-content:space-between;gap:.6rem;align-items:flex-start;margin-bottom:.4rem}.sbmc922-head b{font-size:.8rem}.sbmc922-head span{font-size:.57rem;padding:.28rem .42rem;border:1px solid rgba(81,210,245,.18);border-radius:999px;color:#9adff0}
    .sbmc922-note{font-size:.61rem;color:#87a2ae;line-height:1.45;margin:.25rem 0 .5rem}
    .sbmc922-lines{display:grid;gap:.3rem;margin-top:.35rem}.sbmc922-line{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.2rem .55rem;padding:.42rem .48rem;border-radius:8px;background:rgba(255,255,255,.025)}
    .sbmc922-line b{font-size:.65rem;overflow-wrap:anywhere}.sbmc922-line small{font-size:.56rem;color:#7897a4}.sbmc922-value{grid-column:2;grid-row:1/3;display:flex;flex-direction:column;align-items:flex-end;justify-content:center;gap:.08rem;min-width:92px;line-height:1.15}
    .sbmc922-model{font-size:.67rem;color:#dfffb7;white-space:nowrap}.sbmc922-model.missing{color:#94a8b0;font-size:.59rem}.sbmc922-model.shadow{color:#e4c5ff}.sbmc922-meta{font-size:.52rem!important;color:#83a0aa!important;white-space:nowrap}
    .sbmc922-empty{font-size:.61rem;color:#809da9;padding:.35rem 0}
  `;
  document.head.appendChild(s);
}

function findMatch(raw){
  const k=decode(raw).replace(/^id:/,'');
  try{return window.TENIS_AI_PROJECT_UI?.findMatch?.(k)||null}catch{return null}
}
function context(match){return match?.superbet_market_v91||{}}
function rowsOf(match){
  const ctx=context(match);
  const selections=(Array.isArray(ctx.canonical_selections)?ctx.canonical_selections:[]).filter(r=>r&&r.operator_available!==false);
  const playable=Array.isArray(ctx.model_signals)?ctx.model_signals:[];
  const shadow=Array.isArray(ctx.coverage_shadow_signals)?ctx.coverage_shadow_signals:[];
  return {ctx,selections,playable,shadow};
}
function coverageKey(match){
  const {ctx,selections,playable,shadow}=rowsOf(match);
  return [ctx.source_generated_at||'',ctx.status||'',ctx.suspended===true?'1':'0',selections.length,playable.length,shadow.length].join('|');
}
function marketLabel(r){
  const parts=[];
  const market=String(r?.market||'rynek').replaceAll('_',' ');
  if(r?.player)parts.push(String(r.player));
  if(r?.pick)parts.push(String(r.pick).toUpperCase());
  if(finite(r?.line))parts.push(Number(r.line).toFixed(1).replace('.0',''));
  if(finite(r?.checkpoint)&&Number(r.checkpoint)>0)parts.push(`po ${Number(r.checkpoint)} gemach`);
  return parts.length?parts.join(' · '):market;
}
function signalHtml(signal){
  if(signal&&finite(signal.score)){
    const approximate=String(signal.probability_semantics||'').includes('approximation');
    const shadow=String(signal.coverage_status||'').includes('SHADOW');
    const push=finite(signal.push_probability)&&Number(signal.push_probability)>0.04?`PUSH ${fmt(signal.push_probability)} · `:'';
    return `<span class="sbmc922-model${shadow?' shadow':''}">MODEL ${approximate?'~':''}${fmt(signal.score)}</span><small class="sbmc922-meta">${push}${shadow?'SHADOW · ':''}Superbet ✓</small>`;
  }
  return '<span class="sbmc922-model missing">MODEL: niepokryty</span><small class="sbmc922-meta">Superbet ✓</small>';
}
function panelHtml(match){
  const {selections,playable,shadow}=rowsOf(match);
  const byKey=new Map([...playable,...shadow].map(r=>[key(r),r]));
  const active=window.TENIS_AI_PLAYABLE_UI_V917?.active?.(match)===true;
  const rows=selections.map(selection=>{
    const signal=byKey.get(key(selection))||null;
    return `<div class="sbmc922-line" data-sbmc922-market="${esc(selection.market||'')}"><b>${esc(marketLabel(selection))}</b><small>${esc(String(selection.market||'rynek').replaceAll('_',' '))}</small><strong class="sbmc922-value">${signalHtml(signal)}</strong></div>`;
  }).join('');
  return `<div class="sbmc922-head"><b>🎯 SUPERBET — pełna aktualna oferta</b><span>${active?'ZWERYFIKOWANA':'N/D'}</span></div><p class="sbmc922-note">Realne rynki i linie operatora. MODEL/RAW pozostaje osobną warstwą; brak pokrycia oznacza „niepokryty”, a nie wymyślony wynik.</p>${rows?`<div class="sbmc922-lines">${rows}</div>`:`<div class="sbmc922-empty">${active?'Brak dostępnych selekcji w katalogu.':'Brak świeżej oferty Superbet dla tego meczu.'}</div>`}`;
}

function annotate(){
  queued=false;style();
  const overlay=document.querySelector('#p751-match-overlay:not([hidden])');
  if(!overlay)return;
  const match=findMatch(overlay.dataset.matchKey||'');
  if(!match)return;
  let panel=overlay.querySelector('[data-superbet-model-coverage-v922]');
  if(!panel){
    panel=document.createElement('section');
    panel.className='sbmc922-panel';
    panel.dataset.superbetModelCoverageV922='1';
    const dc=overlay.querySelector('.dc87');
    const screen=overlay.querySelector('.p751-detail-screen');
    if(dc)dc.before(panel);else screen?.prepend(panel);
  }
  const nextKey=coverageKey(match);
  if(panel.dataset.coverageKey===nextKey&&panel.dataset.matchKey===String(overlay.dataset.matchKey||''))return;
  panel.innerHTML=panelHtml(match);
  panel.dataset.coverageKey=nextKey;
  panel.dataset.matchKey=String(overlay.dataset.matchKey||'');
  delete panel.dataset.rp93gReady;
}

function schedule(){if(queued)return;queued=true;queueMicrotask(annotate)}
const observer=new MutationObserver(schedule);
function boot(){
  style();
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden','data-match-key']});
  document.addEventListener('click',schedule,true);
  document.addEventListener('visibilitychange',schedule);
  setTimeout(schedule,0);
}

window.TENIS_AI_SUPERBET_MODEL_COVERAGE_V922=Object.freeze({version:VERSION,refresh:schedule,key,panelHtml,coverageKey});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
