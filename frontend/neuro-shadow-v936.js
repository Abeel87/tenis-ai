/* Tenis AI v9.3.6 — isolated NEURO SHADOW dashboard.
   Read-only UI: never modifies MODEL/RAW, Symphony or PLAYABLE. */
(()=>{
'use strict';
if(window.TENIS_AI_NEURO_SHADOW_V936)return;
const VERSION='v9.3.6';
const PATHS={
  stats:'data/neuro_shadow_stats_v935.json',
  training:'data/neuro_shadow_neural_v936.json',
  current:'data/neuro_shadow_current_v936.json'
};
let cache=null,promise=null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>Number.isFinite(Number(v))?`${(Number(v)*100).toFixed(1).replace('.0','')}%`:'—';
const dec=v=>Number.isFinite(Number(v))?Number(v).toFixed(4):'—';
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const fetchJson=async path=>{try{const r=await fetch(`${path}?v=${Date.now()}`,{cache:'no-store'});return r.ok?await r.json():null}catch{return null}};
async function load(force=false){
  if(cache&&!force)return cache;
  if(promise&&!force)return promise;
  promise=Promise.all([fetchJson(PATHS.stats),fetchJson(PATHS.training),fetchJson(PATHS.current)]).then(([stats,training,current])=>{
    cache={stats:stats||{},training:training||{},current:current||{}};promise=null;return cache;
  });
  return promise;
}
function metric(label,value,sub=''){return `<div class="neuro936-metric"><span>${esc(label)}</span><b>${esc(value)}</b>${sub?`<small>${esc(sub)}</small>`:''}</div>`}
function progress(label,value,max){const n=Math.max(0,num(value)),m=Math.max(1,num(max)),p=Math.min(100,100*n/m);return `<div class="neuro936-progress"><div><span>${esc(label)}</span><b>${n} / ${m}</b></div><i><em style="width:${p.toFixed(1)}%"></em></i></div>`}
function marketRows(training){
  const rows=Object.entries(training?.markets||{}).map(([market,r])=>({market,...r})).sort((a,b)=>num(b?.gate?.settled)-num(a?.gate?.settled));
  if(!rows.length)return '<div class="neuro936-empty">Jeszcze nie ma zebranych rynków NEURO.</div>';
  return `<div class="neuro936-market-list">${rows.map(r=>{
    const ready=r.status==='SHADOW_MODEL_READY'; const gate=r.gate||{};
    const val=r.validation||{}; const base=r.state_baseline_validation||{};
    return `<div class="neuro936-market"><div class="neuro936-market-head"><b>${esc(r.market.replaceAll('_',' '))}</b><span class="${ready?'ready':'collecting'}">${ready?'SHADOW READY':'ZBIERANIE'}</span></div>${progress('Rozliczone',gate.settled||0,gate.min_settled||80)}<small>hit ${gate.hits||0} · miss ${gate.misses||0}${ready?` · Brier NEURO ${dec(val.brier)} vs state ${dec(base.brier)}`:''}</small></div>`;
  }).join('')}</div>`;
}
function dashboard(data){
  const s=data.stats||{},t=data.training||{},c=data.current||{},o=s.overall||{};
  const ready=Array.isArray(t.ready_markets)?t.ready_markets:[];
  return `<section class="neuro936-shell">
    <header class="neuro936-hero"><div><span>🧠 NEURO</span><h2>Neural Meta Model</h2><p>Oddzielny SHADOW. Uczy się na rozliczonych prognozach i nie wpływa na PLAYABLE ani Symfonię.</p></div><strong>SHADOW</strong></header>
    <div class="neuro936-grid">${metric('Historia',t.history_rows??s.total??0,'zapisanych prognoz')}${metric('Rozliczone',s.scored??o.n??0,'hit/miss')}${metric('Rynki gotowe',ready.length,`z ${t.markets_seen||0}`)}${metric('Aktualne selekcje',c.rows_count||0,`${c.neural_rows_count||0} z aktywnym NEURO`)}</div>
    <section class="neuro936-quality"><h3>Jakość SHADOW</h3><div class="neuro936-grid small">${metric('Accuracy',pct(o.accuracy))}${metric('Brier',dec(o.brier))}${metric('Log-loss',dec(o.log_loss))}${metric('Status',ready.length?'SHADOW READY':'COLLECTING DATA')}</div></section>
    <section class="neuro936-section"><h3>Postęp modeli per rynek</h3>${marketRows(t)}</section>
    <div class="neuro936-contract">🔒 Brak auto-promocji · brak wpływu PROD · brak kursów bukmachera w cechach · brak wymyślonych prawdopodobieństw.</div>
  </section>`;
}
async function renderDashboard(){
  const app=document.querySelector('#app'); if(!app)return;
  app.innerHTML='<div class="neuro936-loading">🧠 Ładowanie NEURO SHADOW…</div>';
  const data=await load();
  if(!document.querySelector('.main-tabs [data-view="neuro"]')?.classList.contains('active'))return;
  app.innerHTML=dashboard(data);
}
function activateTab(e){
  const btn=e.target.closest?.('.main-tabs [data-view="neuro"]'); if(!btn)return;
  e.preventDefault();e.stopImmediatePropagation();
  document.querySelectorAll('.main-tabs button').forEach(b=>b.classList.toggle('active',b===btn));
  const controls=document.querySelector('#match-controls'); if(controls)controls.hidden=true;
  renderDashboard();
}
function resetControls(e){
  const btn=e.target.closest?.('.main-tabs button:not([data-view="neuro"])'); if(!btn)return;
  const controls=document.querySelector('#match-controls'); if(controls)controls.hidden=false;
}
function normalizeId(v){return decodeURIComponent(String(v||'')).replace(/^id:/,'')}
function currentMatch(feed,overlay){
  const id=normalizeId(overlay?.dataset?.matchKey||'');
  return (feed?.matches||[]).find(m=>String(m.match_id||'')===id)||null;
}
function neuroLine(row){
  const label=[row.player,row.pick,row.line].filter(v=>v!==null&&v!==undefined&&v!=='').join(' · ')||row.market;
  const neural=row.neural_probability==null?'NEURO: zbieranie':`NEURO ${pct(row.neural_probability)}`;
  return `<div class="neuro936-detail-line"><span>${esc(label)}</span><small>${esc(String(row.market||'').replaceAll('_',' '))}</small><b>STATE ${pct(row.state_probability)}<em>${neural}</em></b></div>`;
}
async function toggleMatchPanel(button){
  const panel=button.closest('.sbmc922-panel'); const overlay=button.closest('#p751-match-overlay'); if(!panel||!overlay)return;
  let box=panel.querySelector('.neuro936-match-panel');
  if(box){box.remove();button.classList.remove('active');return}
  button.classList.add('active');
  const data=await load(); const match=currentMatch(data.current,overlay);
  box=document.createElement('div');box.className='neuro936-match-panel';
  box.innerHTML=match&&match.rows?.length?`<div class="neuro936-match-title"><b>🧠 NEURO SHADOW</b><span>${match.rows.length} selekcji</span></div>${match.rows.map(neuroLine).join('')}`:'<div class="neuro936-empty">NEURO: brak aktualnie przechwyconych selekcji dla tego meczu.</div>';
  panel.querySelector('.sbmc922-head')?.after(box);
}
function injectBrain(){
  document.querySelectorAll('.sbmc922-panel .sbmc922-head').forEach(head=>{
    if(head.querySelector('.neuro936-brain'))return;
    const b=document.createElement('button');b.type='button';b.className='neuro936-brain';b.title='NEURO SHADOW';b.setAttribute('aria-label','Pokaż NEURO SHADOW');b.textContent='🧠';
    b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();toggleMatchPanel(b)});
    head.appendChild(b);
  });
}
function boot(){
  document.addEventListener('click',activateTab,true);
  document.addEventListener('click',resetControls,false);
  const observer=new MutationObserver(injectBrain);observer.observe(document.documentElement,{subtree:true,childList:true});
  injectBrain();
}
window.TENIS_AI_NEURO_SHADOW_V936=Object.freeze({version:VERSION,load,renderDashboard,dashboard,injectBrain});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
