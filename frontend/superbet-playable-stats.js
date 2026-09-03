/* Tenis AI · Superbet PLAYABLE statistics + real-line coverage */
(()=>{
'use strict';
const VERSION='v9.2.3-ui';
const DATA='./data/superbet_playable_stats_v912.json';
const META='./data/meta.json';
const ID='superbet-playable-stats-v912';
const MARKET_LABELS={
  match_winner:'Zwycięzca meczu',
  match_total:'Suma gemów · mecz',
  set1_total:'Suma gemów · set 1',
  set1_exact_score:'Dokładny wynik · set 1',
  exact_match_score:'Dokładny wynik meczu',
  total_sets:'Liczba setów'
};
let data=null;
let coverage=null;
function finite(v){return v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))}
function pct(v){return finite(v)?`${Number(v).toFixed(1)}%`:'N/D'}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function host(){return document.querySelector('#pc77')}
function coverageHtml(){
  const c=coverage||{};
  const available=Number(c.available_selections||0);
  const playable=Number(c.playable_model_covered_selections||0);
  const shadow=Number(c.shadow_model_covered_selections||0);
  const displayed=Number(c.display_model_covered_selections||0);
  const operatorOnly=Number(c.operator_only_selections||Math.max(0,available-displayed));
  const playableCoverage=available?100*playable/available:null;
  const displayCoverage=available?100*displayed/available:null;
  if(!coverage){
    return `<details class="sp912-details"><summary>Pokrycie realnych linii Superbet</summary><p class="sp912-note">Raport pokrycia v9.2.2 jest chwilowo N/D. Nie wpływa to na MODEL/RAW ani na historyczną skuteczność PLAYABLE.</p></details>`;
  }
  return `<details class="sp912-details" data-superbet-coverage-v923="1"><summary>Pokrycie realnych linii Superbet</summary>
    <div class="sp912-grid">
      <div><span>Realne selekcje operatora</span><b>${available}</b></div>
      <div><span>Pokryte przez PLAYABLE model</span><b>${playable} · ${pct(playableCoverage)}</b></div>
      <div><span>Dodatkowo pokryte SHADOW</span><b>${shadow}</b></div>
      <div><span>Pokrycie do wyświetlenia</span><b>${displayed} · ${pct(displayCoverage)}</b></div>
      <div><span>Tylko operator · bez modelu</span><b>${operatorOnly}</b></div>
      <div><span>Nowe linie bez dodatkowych API</span><b>${Number(c.signals_added||0)} + ${Number(c.shadow_signals_added||0)} SHADOW</b></div>
    </div>
    <p class="sp912-note">To jest statystyka pokrycia realnej oferty, nie skuteczność typów. SHADOW służy tylko do diagnostyki/pokrycia i nie wchodzi do skuteczności PLAYABLE, dopóki nie ma właściwej próbki settlementu. MODEL/RAW pozostaje niezależny.</p>
  </details>`;
}
function cardHtml(){
  const matches=Number(data?.matches||0);
  const signals=Number(data?.signals||0);
  const feedActive=matches>0;
  const history=Object.entries(data?.history||{});
  const historyRows=history.map(([market,row])=>{
    const n=Number(row?.n||0);
    const status=n?`${pct(row?.accuracy)} · n=${n}`:'zbieramy próbkę';
    return `<div class="sp912-model"><span>${esc(MARKET_LABELS[market]||market)}</span><b>${esc(status)}</b></div>`;
  }).join('');
  const rawPreserved=data?.contract?.raw_model_fields_preserved===true;
  const stamp=new Date(data?.generated_at||'');
  const timestamp=Number.isFinite(stamp.getTime())?stamp.toLocaleString('pl-PL'):'N/D';
  const subtitle=`Ostatni raport: ${timestamp} · nie jest to stan oferty na żywo`;
  const note=feedActive
    ? 'Liczby opisują ofertę w chwili wygenerowania raportu. Aktualna dostępność jest sprawdzana osobno przy meczu. Skuteczność obejmuje wyłącznie rozliczone sygnały z zamrożoną ofertą operatora; RAW nie jest do niej dopisywany.'
    : 'Brak zweryfikowanej oferty Superbet w tym raporcie. Historyczne rozliczenia pozostają dostępne; brak bieżących danych nie oznacza skuteczności 0%. MODEL / RAW pozostaje niezależny i widoczny.';
  return `<section id="${ID}" class="pc77-card sp912-card" data-superbet-playable-v912="1" data-feed-active="${feedActive?'1':'0'}">
    <div class="pc77-card-head"><div><b>🎯 Superbet PLAYABLE</b><small>${esc(subtitle)}</small></div><strong>${feedActive?`${matches} MECZÓW`:'FEED N/D'}</strong></div>
    <div class="sp912-grid">
      <div><span>Mecze PLAYABLE w raporcie</span><b>${matches}</b></div>
      <div><span>Sygnały PLAYABLE w raporcie</span><b>${signals}</b></div>
      <div><span>MODEL / RAW zachowany</span><b>${rawPreserved?'TAK':'N/D'}</b></div>
    </div>
    <p class="sp912-note">${esc(note)}</p>
    ${coverageHtml()}
    <details class="sp912-details"><summary>Historyczna skuteczność PLAYABLE</summary><div class="sp912-models">${historyRows||'<div class="sp912-empty">Zbieramy pierwszą próbkę.</div>'}</div></details>
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
  const [statsResult,metaResult]=await Promise.allSettled([
    fetch(`${DATA}?v=912`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(String(r.status));return r.json()}),
    fetch(`${META}?v=923`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(String(r.status));return r.json()})
  ]);
  data=statsResult.status==='fulfilled'?statsResult.value:null;
  const meta=metaResult.status==='fulfilled'?metaResult.value:null;
  coverage=meta&&typeof meta==='object'?(meta.superbet_line_coverage_v922||null):null;
  if(data)schedule();
}
function boot(){load();document.addEventListener('tenis-ai:stats-ready',schedule);document.addEventListener('tenis-ai:stats-dashboard-ready',schedule);document.addEventListener('click',e=>{if(e.target?.closest?.('[data-view="stats"],[data-pc77]'))schedule()},true)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
window.TENIS_AI_SUPERBET_PLAYABLE_V912=Object.freeze({version:VERSION,render,load});
})();
