/* Tenis AI v9.1.2 — Superbet PLAYABLE statistics */
(()=>{
'use strict';
const VERSION='v9.1.2';
const DATA='./data/superbet_playable_stats_v912.json';
const ID='superbet-playable-stats-v912';
const LABELS={
  current_prod:'PROD / bieżący model',
  shadow_lab_v78e6:'Shadow Lab 55–71',
  autolearn_current:'AutoLearn · Current',
  autolearn_catboost:'AutoLearn · CatBoost',
  autolearn_tabpfn:'AutoLearn · TabPFN',
  autolearn_ensemble:'AutoLearn · Ensemble',
  autolearn_adaptive_prod:'Adaptive PROD',
  shadow_player_intelligence:'Player Intelligence',
  shadow_catboost_player:'CatBoost + Player',
  shadow_ensemble_player:'Ensemble + Player',
  shadow_catboost_player_elo:'CatBoost + Player + Elo',
  shadow_ensemble_player_elo:'Ensemble + Player + Elo',
  shadow_tabpfn_elo:'TabPFN + Elo'
};
let data=null;
function finite(v){return v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))}
function pct(v){return finite(v)?`${Number(v).toFixed(1)}%`:'N/D'}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function host(){return document.querySelector('#pc77')}
function cardHtml(){
  const cur=data?.current||{};
  const verified=Number(cur.verified_superbet_matches||0);
  const coverage=finite(cur.verified_match_coverage)?Number(cur.verified_match_coverage)*100:null;
  const feedActive=verified>0;
  const models=Object.entries(data?.models||{});
  const modelRows=models.map(([id,row])=>{
    const n=Number(row?.settled||0);
    const status=n?`${pct(row?.accuracy)} · n=${n}`:'zbieramy próbkę';
    return `<div class="sp912-model"><span>${esc(LABELS[id]||id)}</span><b>${esc(status)}</b></div>`;
  }).join('');
  const subtitle=feedActive
    ? 'statystyki tylko dla realnie dostępnych rynków i linii · bez kursów'
    : 'feed Superbet niezweryfikowany — PLAYABLE jest chwilowo wstrzymane';
  const note=feedActive
    ? 'Normalny widok i SHADOW używają zweryfikowanej oferty Superbet. Surowe drabinki modeli zostają wyłącznie diagnostyką; stare wyniki bez zamrożonej oferty operatora nie są dopisywane do PLAYABLE.'
    : '⚠ Brak zweryfikowanej oferty Superbet w ostatnim przebiegu. Linie widoczne w RAW/diagnostyce nie są w tej chwili potwierdzone jako grywalne u operatora i nie są liczone do statystyk PLAYABLE.';
  return `<section id="${ID}" class="pc77-card sp912-card" data-superbet-playable-v912="1" data-feed-active="${feedActive?'1':'0'}">
    <div class="pc77-card-head"><div><b>🎯 Superbet PLAYABLE</b><small>${esc(subtitle)}</small></div><strong>${feedActive?pct(coverage):'FEED N/D'}</strong></div>
    <div class="sp912-grid">
      <div><span>Mecze zweryfikowane</span><b>${verified} / ${Number(cur.model_ready_matches||0)}</b></div>
      <div><span>Zielone sygnały grywalne</span><b>${Number(cur.playable_green_signals||0)}</b></div>
      <div><span>Ukryte linie RAW</span><b>${Number(cur.suppressed_raw_display_estimate||0)}</b></div>
    </div>
    <p class="sp912-note">${esc(note)}</p>
    <details class="sp912-details"><summary>Skuteczność modeli PLAYABLE</summary><div class="sp912-models">${modelRows||'<div class="sp912-empty">Zbieramy pierwszą próbkę.</div>'}</div></details>
  </section>`;
}
function render(){
  const h=host(); if(!h||!data)return false;
  document.getElementById(ID)?.remove();
  const wrap=document.createElement('div'); wrap.innerHTML=cardHtml(); const card=wrap.firstElementChild;
  const sym=document.querySelector('#symphony-performance-v90d');
  const trend=h.querySelector('.pc12-main-trend');
  const summary=h.querySelector('.pc12-summary');
  if(sym?.parentNode===h)sym.insertAdjacentElement('afterend',card);
  else if(trend?.parentNode===h)trend.insertAdjacentElement('afterend',card);
  else if(summary?.parentNode===h)summary.insertAdjacentElement('afterend',card);
  else h.prepend(card);
  return true;
}
function schedule(){[0,120,500,1200].forEach(ms=>setTimeout(render,ms))}
async function load(){
  try{const r=await fetch(`${DATA}?v=912`,{cache:'no-store'});if(!r.ok)throw new Error(String(r.status));data=await r.json();schedule();}
  catch(_){data=null;}
}
function boot(){load();document.addEventListener('tenis-ai:stats-ready',schedule);document.addEventListener('tenis-ai:stats-dashboard-ready',schedule);document.addEventListener('click',e=>{if(e.target?.closest?.('[data-view="stats"],[data-pc77]'))schedule()},true)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
window.TENIS_AI_SUPERBET_PLAYABLE_V912=Object.freeze({version:VERSION,render,load});
})();