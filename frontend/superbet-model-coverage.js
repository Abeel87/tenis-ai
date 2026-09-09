/* Tenis AI v9.3.3 — complete current Superbet offer with model coverage.
   Operator/UI only. MODEL/RAW remains owned by the base UI; PLAYABLE gating stays in v917. */
(()=>{
'use strict';
if(window.TENIS_AI_SUPERBET_MODEL_COVERAGE_V922)return;
const VERSION='v9.3.3';
let queued=false;
const LINE_MARKETS=new Set([
  'match_total','set1_total','set2_total','set3_total','total_sets',
  'match_game_handicap','set1_game_handicap','set2_game_handicap','set3_game_handicap','set_handicap',
  'player_total_games','match_total_aces','player_aces','player_double_faults'
]);

const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const decode=v=>{try{return decodeURIComponent(String(v||''))}catch{return String(v||'')}};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>finite(v)?`${Number(v).toFixed(1).replace('.0','')}%`:'—';
const key=r=>[
  r?.market||'',r?.checkpoint||'',r?.player||'',
  r?.line!==null&&r?.line!==undefined?r.line:'',r?.pick||''
].map(String).join('|');

function style(){}
function findMatch(raw){
  const k=decode(raw).replace(/^id:/,'');
  try{return window.TENIS_AI_PROJECT_UI?.findMatch?.(k)||null}catch{return null}
}
function context(match){return match?.superbet_market_v91||{}}
function currentContextActive(match){return window.TENIS_AI_PLAYABLE_UI_V917?.active?.(match)===true}
function operatorSelectionVerified(row){
  if(!row||typeof row!=='object'||row.operator_available!==true)return false;
  const market=String(row.market||'').trim();
  if(!LINE_MARKETS.has(market))return true;
  return finite(row.line)&&row.operator_line_verified===true&&row.fixture_line_verified===true;
}
function rowsOf(match){
  const ctx=context(match);
  const current=currentContextActive(match);
  const selections=current?(Array.isArray(ctx.canonical_selections)?ctx.canonical_selections:[]).filter(operatorSelectionVerified):[];
  const playable=current&&Array.isArray(ctx.model_signals)?ctx.model_signals:[];
  const shadow=current&&Array.isArray(ctx.coverage_shadow_signals)?ctx.coverage_shadow_signals:[];
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
  const active=currentContextActive(match);
  const rows=selections.map(selection=>{
    const signal=byKey.get(key(selection))||null;
    return `<div class="sbmc922-line" data-sbmc922-market="${esc(selection.market||'')}"><b>${esc(marketLabel(selection))}</b><small>${esc(String(selection.market||'rynek').replaceAll('_',' '))}</small><strong class="sbmc922-value">${signalHtml(signal)}</strong></div>`;
  }).join('');
  return `<div class="sbmc922-head"><b>🎯 SUPERBET — pełna aktualna oferta</b><span>${active?'ZWERYFIKOWANA':'N/D'}</span></div><p class="sbmc922-note">Realne rynki i linie operatora. MODEL/RAW pozostaje osobną warstwą; brak pokrycia oznacza „niepokryty”, a nie wymyślony wynik.</p>${rows?`<div class="sbmc922-lines">${rows}</div>`:`<div class="sbmc922-empty">${active?'Brak dostępnych selekcji w katalogu.':'Brak świeżej oferty Superbet dla tego meczu.'}</div>`}`;
}

function annotate(){
  queued=false;style();
  const host=document.querySelector('#app[data-match-key]');
  if(!host)return;
  const match=findMatch(host.dataset.matchKey||'');
  if(!match)return;
  let panel=host.querySelector('[data-superbet-model-coverage-v922]');
  if(!panel){
    panel=document.createElement('section');
    panel.className='sbmc922-panel';
    panel.dataset.superbetModelCoverageV922='1';
    const dc=host.querySelector('.dc87');
    const primary=host.querySelector('.match-page-primary');
    const screen=host.querySelector('.p751-detail-screen');
    if(dc)dc.before(panel);
    else if(primary)primary.prepend(panel);
    else screen?.prepend(panel);
  }
  const nextKey=coverageKey(match);
  if(panel.dataset.coverageKey===nextKey&&panel.dataset.matchKey===String(host.dataset.matchKey||''))return;
  panel.innerHTML=panelHtml(match);
  panel.dataset.coverageKey=nextKey;
  panel.dataset.matchKey=String(host.dataset.matchKey||'');
  delete panel.dataset.rp93gReady;
  document.dispatchEvent(new CustomEvent('tenis-ai:superbet-coverage-ready',{detail:{matchKey:String(host.dataset.matchKey||'')}}));
}

function schedule(){if(queued)return;queued=true;queueMicrotask(annotate)}
function boot(){
  style();
  document.addEventListener('tenis-ai:match-open',schedule);
  document.addEventListener('tenis-ai:match-refresh',schedule);
  setTimeout(schedule,0);
}

window.TENIS_AI_SUPERBET_MODEL_COVERAGE_V922=Object.freeze({version:VERSION,refresh:schedule,key,panelHtml,coverageKey});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
