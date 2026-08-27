/* Tenis AI v8.9.4 — SHADOW Signal Center
   Read-only manual-test view. It never changes PROD, Generator or final_score.
*/
(()=>{
'use strict';
if(window.TENIS_AI_SHADOW_SIGNAL_CENTER_V894)return;

const VERSION='v8.9.4';
const DATA_URL='data/shadow_signals_v894.json';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
const pc=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');

const state={model:'all',min:65,tour:'all',report:null,loading:false,active:false};

function modelStatus(status){
  const x=String(status||'shadow').toLowerCase();
  return ({
    strong_candidate:'MOCNY KANDYDAT',
    promising:'OBIECUJĄCY',
    watch:'OBSERWACJA',
    collecting:'ZBIERA DANE',
    shadow:'SHADOW'
  })[x]||String(status||'SHADOW').toUpperCase();
}
function statusClass(status){
  const x=String(status||'').toLowerCase();
  if(x==='strong_candidate'||x==='promising')return 'good';
  if(x==='watch')return 'watch';
  if(x==='collecting')return 'collecting';
  return 'shadow';
}
function tourLabel(v){
  const x=String(v||'').toLowerCase();
  if(x.includes('chall'))return 'CH';
  if(x.includes('itf'))return 'ITF';
  if(x.includes('atp'))return 'ATP';
  if(x.includes('wta'))return 'WTA';
  return String(v||'TENIS').toUpperCase();
}
function timeLabel(value){
  const d=new Date(value||'');
  return Number.isFinite(d.getTime())?d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—';
}
function matchStatus(m){
  const raw=String(m?.event_status||'').toLowerCase();
  if(raw.includes('live')||raw.includes('progress')||raw.includes('started'))return {text:'LIVE',cls:'live'};
  if(raw.includes('postpon'))return {text:'PRZEŁOŻONY',cls:'warn'};
  if(raw.includes('interrupt')||raw.includes('suspend'))return {text:'WSTRZYMANY',cls:'warn'};
  return {text:'PRZED MECZEM',cls:'ready'};
}

async function loadReport(force=false){
  if(state.report&&!force)return state.report;
  const r=await fetch(DATA_URL,{cache:'no-store'});
  if(!r.ok)throw new Error(`shadow_feed_${r.status}`);
  const data=await r.json();
  if(!data||data.production_influence!==false)throw new Error('shadow_contract_invalid');
  state.report=data;
  return data;
}

function ensureNav(){
  const nav=document.querySelector('#p751-bottom-nav');
  if(!nav)return false;
  let btn=nav.querySelector('[data-p751-nav="shadow-signals"]');
  if(!btn){
    btn=document.createElement('button');
    btn.type='button';
    btn.dataset.p751Nav='shadow-signals';
    btn.innerHTML='<span>👻</span><b>SHADOW</b>';
    const scenarios=nav.querySelector('[data-p751-nav="scenarios"]');
    if(scenarios)scenarios.insertAdjacentElement('afterend',btn);
    else nav.appendChild(btn);
  }
  btn.onclick=()=>open();
  document.documentElement.classList.add('sh894-nav-ready');
  return true;
}

function setActive(on){
  state.active=!!on;
  document.documentElement.classList.toggle('sh894-view',state.active);
  if(state.active){
    document.querySelectorAll('#p751-bottom-nav [data-p751-nav]').forEach(b=>b.classList.toggle('active',b.dataset.p751Nav==='shadow-signals'));
  }
}

function models(){return Array.isArray(state.report?.models)?state.report.models:[]}
function modelMap(){return new Map(models().map(m=>[m.id,m]))}

function scoreEntries(match,modelId){
  const out=[];
  (match?.signals||[]).forEach(signal=>{
    const scores=signal?.scores||{};
    if(modelId==='all'){
      Object.entries(scores).forEach(([id,value])=>{
        const v=num(value);if(v!=null&&v>=state.min)out.push({model:id,signal,value:v});
      });
    }else{
      const v=num(scores?.[modelId]);
      if(v!=null&&v>=state.min)out.push({model:modelId,signal,value:v});
    }
  });
  return out.sort((a,b)=>b.value-a.value);
}

function tourMatches(rows){
  if(state.tour==='all')return rows;
  return rows.filter(m=>{
    const t=norm(m?.tour);
    if(state.tour==='ch')return t.includes('chall');
    return t.includes(state.tour);
  });
}

function visibleMatches(){
  const rows=Array.isArray(state.report?.matches)?state.report.matches:[];
  return tourMatches(rows).filter(m=>scoreEntries(m,state.model).length>0);
}

function modelChip(m){
  const count=Number(state.report?.model_signal_counts?.[m.id]||0);
  return `<button class="${state.model===m.id?'active':''}" data-sh894-model="${esc(m.id)}"><span>${esc(m.icon||'🧪')} ${esc(m.label||m.id)}</span><small>${modelStatus(m.status)} · ${count}</small></button>`;
}

function controls(){
  const allCount=Object.values(state.report?.model_signal_counts||{}).reduce((a,b)=>a+Number(b||0),0);
  return `<section class="sh894-controls">
    <div class="sh894-models">
      <button class="${state.model==='all'?'active':''}" data-sh894-model="all"><span>🧪 Wszystkie modele</span><small>${allCount} wyników</small></button>
      ${models().map(modelChip).join('')}
    </div>
    <div class="sh894-subfilters">
      <div class="sh894-tours">
        ${[['all','Wszystkie'],['atp','ATP'],['wta','WTA'],['ch','CH'],['itf','ITF']].map(([id,label])=>`<button class="${state.tour===id?'active':''}" data-sh894-tour="${id}">${label}</button>`).join('')}
      </div>
      <div class="sh894-threshold"><span>Próg sygnału</span>${[60,65,70,75].map(v=>`<button class="${state.min===v?'active':''}" data-sh894-min="${v}">${v}+</button>`).join('')}</div>
    </div>
  </section>`;
}

function signalRow(entry,meta){
  const strong=entry.value>=75?'strong':entry.value>=70?'mid':'';
  return `<div class="sh894-signal ${strong}">
    <div><b>${esc(entry.signal?.label||'Sygnał')}</b><small>${esc(meta?.icon||'🧪')} ${esc(meta?.label||entry.model)} · ${modelStatus(meta?.status)}</small></div>
    <strong>${pc(entry.value)}</strong>
  </div>`;
}

function eloLine(match){
  const e=match?.elo;if(!e)return '';
  const p1=num(e.p1_surface),p2=num(e.p2_surface);
  if(p1==null||p2==null)return '';
  return `<div class="sh894-elo"><span>🏟️ Surface Elo</span><b>${esc(match.p1)} ${Math.round(p1)} <small>n=${Number(e.p1_surface_n||0)}</small></b><i>vs</i><b>${esc(match.p2)} ${Math.round(p2)} <small>n=${Number(e.p2_surface_n||0)}</small></b><em>${esc(String(e.quality||'N/D'))}</em></div>`;
}

function matchCard(match){
  const map=modelMap(), entries=scoreEntries(match,state.model);
  const top=entries[0],st=matchStatus(match);
  let body='';
  if(state.model==='all'){
    const byModel=new Map();
    entries.forEach(e=>{if(!byModel.has(e.model))byModel.set(e.model,e)});
    body=[...byModel.values()].sort((a,b)=>b.value-a.value).map(e=>signalRow(e,map.get(e.model))).join('');
  }else{
    body=entries.slice(0,8).map(e=>signalRow(e,map.get(e.model))).join('');
  }
  return `<article class="sh894-match-card">
    <header><span class="sh894-status ${st.cls}">${esc(st.text)}</span><b>${esc(tourLabel(match.tour))}</b><span>${esc(match.tournament||'Turniej')}</span><span>• ${esc(match.surface||'—')}</span><time>${esc(timeLabel(match.scheduled_time))}</time></header>
    <div class="sh894-matchup"><b>${esc(match.p1)}</b><span>VS</span><b>${esc(match.p2)}</b></div>
    <div class="sh894-best"><span>👻 Najmocniejszy SHADOW</span><b>${esc(top?.signal?.label||'—')}</b><strong>${top?pc(top.value):'—'}</strong><small>${top?esc(map.get(top.model)?.label||top.model):''}</small></div>
    ${eloLine(match)}
    <details class="sh894-details" ${state.model!=='all'?'open':''}><summary><b>Sygnały SHADOW</b><span>${entries.length} powyżej ${state.min}</span><i>⌄</i></summary><div>${body}</div></details>
    <footer><span>🧪 ${entries.length} testowych</span><span>🚫 0% PROD</span><b>tylko do ręcznego testu</b></footer>
  </article>`;
}

function groups(rows){
  const m=new Map();
  rows.forEach(row=>{
    const k=`${tourLabel(row.tour)}|${row.tournament||'Turniej'}`;
    if(!m.has(k))m.set(k,{tour:tourLabel(row.tour),name:row.tournament||'Turniej',rows:[]});
    m.get(k).rows.push(row);
  });
  return [...m.values()];
}

function render(){
  const app=document.querySelector('#app');if(!app)return;
  setActive(true);
  if(!state.report){
    app.innerHTML='<section class="sh894-loading"><b>👻 Ładowanie SHADOW…</b><span>Pobieram bieżące sygnały modeli testowych.</span></section>';
    return;
  }
  const rows=visibleMatches();
  app.innerHTML=`<section class="sh894-page">
    <header class="sh894-head"><div><span>👻 SHADOW SIGNAL CENTER · ${esc(VERSION)}</span><h2>Sygnały modeli testowych</h2><p>Te wyniki nie zmieniają normalnych typów. Możesz testować każdy model osobno, gdy dalej zbiera dane.</p></div><div><em>0% PROD</em><button data-sh894-refresh>↻</button></div></header>
    ${controls()}
    <div class="sh894-summary"><span>Mecze z sygnałem <b>${rows.length}</b></span><span>Historia Elo <b>${Number(state.report.elo_events||0).toLocaleString('pl-PL')}</b></span><span>Uczenie <b>${Number(state.report.training_rows||0)}</b></span></div>
    ${rows.length?`<div class="sh894-groups">${groups(rows).map((g,i)=>`<details class="sh894-group" ${i<5?'open':''}><summary><div><span>${esc(g.tour)}</span><b>${esc(g.name)}</b><small>${g.rows.length} ${g.rows.length===1?'mecz':'meczów'}</small></div><i>⌄</i></summary><div>${g.rows.map(matchCard).join('')}</div></details>`).join('')}</div>`:'<div class="sh894-empty"><b>Brak sygnałów dla tych filtrów.</b><span>Obniż próg albo wybierz inny model.</span></div>'}
    <p class="sh894-note">SHADOW = eksperyment. Wyniki służą do porównywania modeli i ręcznych testów; nie są częścią Generatora ani final_score.</p>
  </section>`;
  bind();
}

function bind(){
  document.querySelectorAll('[data-sh894-model]').forEach(b=>b.onclick=()=>{state.model=b.dataset.sh894Model||'all';render()});
  document.querySelectorAll('[data-sh894-tour]').forEach(b=>b.onclick=()=>{state.tour=b.dataset.sh894Tour||'all';render()});
  document.querySelectorAll('[data-sh894-min]').forEach(b=>b.onclick=()=>{state.min=Number(b.dataset.sh894Min)||65;render()});
  document.querySelector('[data-sh894-refresh]')?.addEventListener('click',async()=>{
    state.report=null;render();
    try{await loadReport(true);render()}catch{renderError()}
  });
}

function renderError(){
  const app=document.querySelector('#app');if(!app)return;
  setActive(true);
  app.innerHTML='<section class="sh894-loading error"><b>SHADOW jeszcze się aktualizuje</b><span>Feed testowych modeli nie jest teraz dostępny. Normalne mecze i PROD działają niezależnie.</span><button data-sh894-retry>Spróbuj ponownie</button></section>';
  document.querySelector('[data-sh894-retry]')?.addEventListener('click',open);
}

async function open(){
  ensureNav();setActive(true);render();
  try{await loadReport(false);render()}catch{renderError()}
}

function boot(){
  ensureNav();
}

document.addEventListener('click',e=>{
  const b=e.target?.closest?.('#p751-bottom-nav [data-p751-nav]');
  if(!b)return;
  if(b.dataset.p751Nav!=='shadow-signals')setActive(false);
},true);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)ensureNav()});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
setTimeout(ensureNav,350);

window.TENIS_AI_SHADOW_SIGNAL_CENTER_V894=Object.freeze({version:VERSION,open,render,productionInfluence:false});
})();
