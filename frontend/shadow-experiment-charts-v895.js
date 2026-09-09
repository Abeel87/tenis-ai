/* Tenis AI v8.9.5 — SHADOW Experiment Charts
   Read-only charts built from persisted holdout snapshots.
   Never changes model scores, PROD, Generator or final_score.
*/
(()=>{
'use strict';
if(window.TENIS_AI_SHADOW_CHARTS_V895)return;

const VERSION='v8.9.5';
const DATA_URL='data/shadow_experiment_trends_v895.json';
let report=null;
let loading=null;

const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const MODEL_IDS=[
  ['CatBoost + Player + Surface Elo','catboost_player_elo'],
  ['Ensemble + Player + Surface Elo','ensemble_player_elo'],
  ['TabPFN + Surface Elo','tabpfn_elo'],
  ['Ensemble + Player Learning','ensemble_player'],
  ['CatBoost + Player Intelligence','catboost_player']
];

async function load(force=false){
  if(report&&!force)return report;
  if(loading&&!force)return loading;
  loading=fetch(DATA_URL,{cache:'no-store'}).then(async r=>{
    if(!r.ok)throw new Error(`trend_${r.status}`);
    const x=await r.json();
    if(x?.production_influence!==false)throw new Error('trend_contract');
    report=x;return x;
  }).catch(()=>{report=null;return null}).finally(()=>{loading=null});
  return loading;
}

function modelId(card){
  const title=String(card?.querySelector('header b')?.textContent||'').trim();
  return MODEL_IDS.find(([prefix])=>title.startsWith(prefix))?.[1]||null;
}

function series(id,field){
  const pts=report?.models?.[id]?.points||[];
  return pts.map(p=>({v:num(p?.[field]),at:p?.source_generated_at||''})).filter(p=>p.v!=null).slice(-20);
}

function svgLine(rows,klass=''){
  if(rows.length<2)return '<div class="sh895-empty">Trend zbiera punkty.<br>Po kolejnych odświeżeniach pojawi się linia.</div>';
  const W=220,H=48,P=4;
  const vals=rows.map(x=>x.v),mn=Math.min(...vals),mx=Math.max(...vals),span=Math.max(mx-mn,Math.abs(mx)*.025,0.001);
  const lo=mn-span*.18,hi=mx+span*.18;
  const pts=rows.map((x,i)=>{
    const px=P+(W-2*P)*(rows.length===1?0.5:i/(rows.length-1));
    const py=H-P-(H-2*P)*(x.v-lo)/(hi-lo);
    return [px,py];
  });
  const poly=pts.map(p=>p.map(v=>v.toFixed(1)).join(',')).join(' ');
  const last=pts[pts.length-1];
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><line class="sh895-gridline" x1="0" y1="24" x2="${W}" y2="24"/><polyline class="sh895-line ${klass}" points="${poly}"/><circle class="sh895-dot ${klass}" cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="2.7"/></svg>`;
}

function lastPoint(id){
  const pts=report?.models?.[id]?.points||[];
  return pts.length?pts[pts.length-1]:null;
}

function bar(label,value,base=false){
  const v=num(value);
  const w=v==null?0:Math.max(0,Math.min(100,v));
  return `<div class="sh895-barrow ${base?'base':''}"><span>${esc(label)}</span><i style="--w:${w}%"></i><strong>${v==null?'—':v.toFixed(1)+'%'}</strong></div>`;
}

function chartHtml(id){
  const p=lastPoint(id)||{};
  const acc=series(id,'accuracy'),br=series(id,'brier');
  const points=Number(report?.models?.[id]?.points_count||0);
  const accNow=num(p.accuracy),accBase=num(p.base_accuracy);
  const brNow=num(p.brier),brBase=num(p.base_brier);
  const accDelta=accNow!=null&&accBase!=null?accNow-accBase:null;
  const brGain=brNow!=null&&brBase!=null?brBase-brNow:null;
  return `<section class="sh895-chartbox" data-sh895-chart="${esc(id)}">
    <div class="sh895-charthead"><b>📈 Jak model idzie?</b><span>${points} ${points===1?'punkt':'punktów'} historii</span></div>
    ${(accBase!=null||accNow!=null)?`<div class="sh895-comparebars">${bar('Baza',accBase,true)}${bar('Teraz',accNow,false)}</div>`:''}
    <div class="sh895-plots">
      <div class="sh895-plot"><header><b>Trafność</b><small>${accDelta==null?'trend holdoutu':`${accDelta>=0?'+':''}${accDelta.toFixed(1)} pp vs baza`}</small></header>${svgLine(acc)}</div>
      <div class="sh895-plot"><header><b>Brier</b><small>${brGain==null?'niżej = lepiej':brGain===0?'bez zmiany':`${Math.abs(brGain).toFixed(5)} ${brGain>0?'poprawy':'pogorszenia'}`}</small></header>${svgLine(br,'brier')}</div>
    </div>
    <div class="sh895-foot"><span>Ostatnie maks. 20 przebiegów</span><b>SHADOW · 0% PROD</b></div>
  </section>`;
}

function decorate(){
  if(!report)return false;
  const cards=[...document.querySelectorAll('#coh892-shadow .coh892-card')];
  if(!cards.length)return false;
cards.forEach(card=>{
    const id=modelId(card);if(!id)return;
    const html=chartHtml(id);
    const existing=card.querySelector('.sh895-chartbox');
    if(existing&&card.__shadowChartHtml===html)return;
    existing?.remove();
    const host=card.querySelector('.coh892-compare')||card.querySelector('.coh892-metric');
    if(!host)return;
    host.insertAdjacentHTML('afterend',html);
    card.__shadowChartHtml=html;
  });
  return true;
}

async function refresh(){await load(true);decorate()}
async function schedule(){await load(false);decorate()}
async function boot(){await schedule()}

document.addEventListener('tenis-ai:shadow-experiments-ready',schedule);
document.addEventListener('tenis-ai:stats-ready',schedule);
document.addEventListener('tenis-ai:stats-dashboard-ready',schedule);
document.addEventListener('click',e=>{
  if(e.target?.closest?.('[data-view="stats"]'))schedule();
  if(e.target?.closest?.('#refresh'))setTimeout(refresh,1800);
},true);
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();

window.TENIS_AI_SHADOW_CHARTS_V895=Object.freeze({version:VERSION,decorate,refresh,productionInfluence:false});
})();
