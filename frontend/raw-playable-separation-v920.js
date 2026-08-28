/* Tenis AI v9.2.0 — RAW analysis and Superbet PLAYABLE are separate UI layers.
   UI-only: does not change model math, training, thresholds, history or settlement. */
(()=>{
'use strict';
if(window.TENIS_AI_RAW_PLAYABLE_V920)return;

const VERSION='v9.2.0';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const score=v=>finite(v)?`${Math.round(Number(v))}/100`:'N/D';
const pct=v=>finite(v)?`${Number(v).toFixed(1).replace('.0','')}%`:'N/D';
const valueOf=row=>{
  for(const k of ['v','final_score','adaptive_prod_score','score','current','evidence_score','prod_score']){
    if(finite(row?.[k]))return Number(row[k]);
  }
  return null;
};
const decode=v=>{try{return decodeURIComponent(String(v||''))}catch{return String(v||'')}};
const keyOf=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));

let compactPromise=null;
let fullPromise=null;
let telemetryPromise=null;
let statsScope='30d';
let timer=null;

function injectStyle(){
  if(document.getElementById('rp920-style'))return;
  const s=document.createElement('style');
  s.id='rp920-style';
  s.textContent=`
    .rp920-raw-card{margin:.5rem 0;padding:.55rem .65rem;border:1px solid rgba(100,219,255,.18);border-radius:11px;background:rgba(40,181,220,.045);display:grid;grid-template-columns:1fr auto;gap:.18rem .65rem;align-items:center}
    .rp920-raw-card small,.rp920-block small{color:#7f9eab;font-size:.62rem}.rp920-raw-card b{font-size:.78rem;color:#dff8ff}.rp920-raw-card strong{grid-row:1/3;grid-column:2;font-size:1rem;color:#aeeaff}.rp920-raw-card em{font-style:normal;font-size:.58rem;color:#7694a2}
    .rp920-block{margin:.65rem 0;padding:.75rem;border:1px solid rgba(81,210,245,.17);border-radius:14px;background:rgba(3,22,33,.72)}
    .rp920-head{display:flex;justify-content:space-between;gap:.7rem;align-items:flex-start;margin-bottom:.55rem}.rp920-head b{font-size:.82rem;color:#eafcff}.rp920-head span{font-size:.58rem;padding:.3rem .45rem;border-radius:999px;border:1px solid rgba(81,210,245,.18);color:#9adff0;white-space:nowrap}
    .rp920-note{margin:.35rem 0 .55rem;color:#8da6b1;font-size:.63rem;line-height:1.45}
    .rp920-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.4rem}.rp920-row{padding:.48rem .55rem;border-radius:9px;background:rgba(255,255,255,.025);min-width:0}.rp920-row b{display:block;font-size:.68rem;color:#e9faff;overflow-wrap:anywhere}.rp920-row small{display:block;margin-top:.15rem}.rp920-row strong{display:block;margin-top:.22rem;font-size:.78rem;color:#b9ecff}
    .rp920-lines{display:grid;gap:.35rem}.rp920-line{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.35rem .65rem;align-items:center;padding:.45rem .5rem;border-radius:9px;background:rgba(255,255,255,.024)}.rp920-line b{font-size:.68rem;overflow-wrap:anywhere}.rp920-line small{grid-column:1/2}.rp920-line strong{grid-column:2;grid-row:1/3;font-size:.72rem;color:#baff76;white-space:nowrap}
    .rp920-model-table{display:grid;gap:.34rem}.rp920-model{display:grid;grid-template-columns:minmax(120px,1.3fr) repeat(5,minmax(58px,.62fr));gap:.35rem;align-items:center;padding:.42rem .48rem;border-radius:8px;background:rgba(255,255,255,.022);font-size:.62rem}.rp920-model b{font-size:.67rem}.rp920-model span{text-align:right;color:#9ab0ba}.rp920-model strong{text-align:right;color:#dff8ff}
    .rp920-scope{display:flex;gap:.3rem;margin:.45rem 0 .55rem}.rp920-scope button{border:1px solid rgba(81,210,245,.16);border-radius:999px;background:rgba(81,210,245,.04);color:#91aab5;padding:.3rem .55rem;font:inherit;font-size:.62rem;font-weight:800}.rp920-scope button.active{color:#dffcff;border-color:rgba(186,255,97,.3);background:rgba(186,255,97,.07)}
    .rp920-shadow{margin-top:.55rem;border-top:1px dashed rgba(255,255,255,.08);padding-top:.5rem}.rp920-shadow h4{margin:0 0 .4rem;font-size:.7rem}.rp920-shadow-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.35rem}
    .rp920-symphony-raw{margin:.55rem 0;padding:.62rem;border:1px solid rgba(165,126,255,.2);border-radius:12px;background:rgba(136,91,220,.045)}.rp920-symphony-raw header{display:flex;justify-content:space-between;gap:.5rem;align-items:center}.rp920-symphony-raw header b{font-size:.72rem}.rp920-symphony-raw header strong{font-size:.78rem;color:#cfbaff}.rp920-symphony-raw .rp920-sym-legs{display:grid;gap:.28rem;margin-top:.42rem}.rp920-symphony-raw .rp920-sym-legs span{font-size:.62rem;color:#b7c7ce;padding:.32rem .4rem;border-radius:7px;background:rgba(255,255,255,.025)}
    .rp920-superbet-empty{color:#8ca5af;font-size:.64rem;padding:.45rem .1rem}
    @media(max-width:720px){.rp920-grid,.rp920-shadow-grid{grid-template-columns:1fr}.rp920-model{grid-template-columns:minmax(110px,1.2fr) repeat(3,minmax(52px,.6fr))}.rp920-model .rp920-hide-mobile{display:none}}
  `;
  document.head.appendChild(s);
}

function findMatch(raw){
  const k=decode(raw).replace(/^id:/,'');
  try{return window.TENIS_AI_PROJECT_UI?.findMatch?.(k)||null}catch{return null}
}
function matchFromCard(card){return findMatch(card?.getAttribute?.('data-p751-open')||'')}
function rawSignals(match,limit=100){
  const api=window.TENIS_AI_MODEL_API;
  let rows=[];
  try{rows=typeof api?.allSignals==='function'?(api.allSignals(match)||[]):[]}catch{return[]}
  return rows.filter(x=>valueOf(x)!=null).sort((a,b)=>Number(valueOf(b))-Number(valueOf(a))).slice(0,limit);
}
function rawLabel(row){return String(row?.label||row?.pick||row?.key||row?.market||'Sygnał modelowy')}

function patchCards(){
  for(const card of document.querySelectorAll('#app .p751-match-card[data-p751-open]')){
    const match=matchFromCard(card);if(!match)continue;
    const top=rawSignals(match,1)[0]||null;
    let raw=card.querySelector('.rp920-raw-card');
    if(!raw){
      raw=document.createElement('div');raw.className='rp920-raw-card';raw.dataset.rp920RawCard='1';
      const existing=card.querySelector('.p751-top-pick');
      if(existing)existing.before(raw);else card.querySelector('.p751-card-center')?.append(raw);
    }
    raw.innerHTML=`<small>🧠 MODEL / RAW · analiza</small><b>${esc(top?rawLabel(top):'Brak gotowego sygnału modelowego')}</b><strong>${score(valueOf(top))}</strong><em>Niezależne od dostępności Superbet</em>`;
    const playable=card.querySelector('.p751-top-pick');
    if(playable){
      const label=playable.querySelector('span');
      if(label&&!/SUPERBET/i.test(label.textContent||''))label.textContent='◎ SUPERBET PLAYABLE';
    }
  }
}

function marketText(row){
  if(row?.label)return String(row.label);
  const bits=[];
  if(row?.market)bits.push(String(row.market).replaceAll('_',' '));
  if(row?.player)bits.push(String(row.player));
  if(row?.pick)bits.push(String(row.pick).toUpperCase());
  if(finite(row?.line))bits.push(String(Number(row.line).toFixed(1).replace('.0','')));
  if(finite(row?.checkpoint))bits.push(`po ${Number(row.checkpoint)} gemach`);
  return bits.join(' · ')||'Rynek Superbet';
}
function rawLinesHtml(match){
  const rows=rawSignals(match,40);
  if(!rows.length)return '<div class="rp920-superbet-empty">Brak gotowych linii/sygnałów modelowych dla tego meczu.</div>';
  return `<div class="rp920-lines">${rows.map(r=>`<div class="rp920-line"><b>${esc(rawLabel(r))}</b><small>${esc(String(r.market||'MODEL / RAW').replaceAll('_',' '))}</small><strong>${score(valueOf(r))}</strong></div>`).join('')}</div>`;
}
function superbetLinesHtml(match){
  const ctx=match?.superbet_market_v91||{};
  const rows=Array.isArray(ctx.canonical_selections)?ctx.canonical_selections.filter(x=>x&&x.operator_available!==false):[];
  const active=window.TENIS_AI_PLAYABLE_UI_V917?.active?.(match)===true;
  if(!rows.length)return `<div class="rp920-superbet-empty">${active?'Brak dostępnych selekcji w bieżącym katalogu.':'Brak świeżo zweryfikowanej oferty Superbet. MODEL / RAW powyżej pozostaje normalnie dostępny.'}</div>`;
  return `<div class="rp920-lines">${rows.map(r=>`<div class="rp920-line"><b>${esc(marketText(r))}</b><small>${esc(String(r.market||'rynek').replaceAll('_',' '))}</small><strong>Superbet ✓</strong></div>`).join('')}</div>`;
}

function loadCompact(){
  if(compactPromise)return compactPromise;
  compactPromise=fetch('./data/symphony_match_cards_v90.json?raw=920',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null);
  return compactPromise;
}
function loadFull(){
  if(fullPromise)return fullPromise;
  fullPromise=fetch('./data/symphony_v90.json?raw=920',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null);
  return fullPromise;
}
function reportFind(report,match,raw=''){
  const id=String(match?.id??match?.match_id??'');
  const decoded=decode(raw).replace(/^id:/,'');
  return (report?.matches||[]).find(r=>String(r?.id??'')===id||String(r?.match_key||'').replace(/^id:/,'')===decoded||(
    String(r?.p1||'')===String(match?.p1||'')&&String(r?.p2||'')===String(match?.p2||'')
  ))||null;
}
function bestModelComposition(fullRow,compactRow){
  const roots=[fullRow?.raw_compositions,fullRow?.model_compositions];
  for(const root of roots){
    if(!root||typeof root!=='object')continue;
    for(const n of [6,5,4,3,2]){
      const c=root[String(n)];if(Array.isArray(c?.selection)&&c.selection.length>=2)return c;
    }
  }
  if(Array.isArray(fullRow?.raw_full_composition?.selection)&&fullRow.raw_full_composition.selection.length>=2)return fullRow.raw_full_composition;
  if(Array.isArray(compactRow?.composition?.selection)&&compactRow.composition.selection.length>=2)return compactRow.composition;
  return null;
}
function symphonyHtml(comp,compactRow){
  if(!comp)return '<div class="rp920-superbet-empty">Brak zapisanej Symfonii modelowej dla tego spotkania.</div>';
  const legs=comp.selection||[];
  return `<div class="rp920-symphony-raw"><header><b>🎼 SYMFONIA MODELOWA · ANALIZA</b><strong>${score(comp.symphony_score)}</strong></header><small>${legs.length} zdarzenia · ${esc(comp.story_type||compactRow?.composition?.story_type||'scenariusz modelowy')} · niezależnie od Superbet</small><div class="rp920-sym-legs">${legs.map((l,i)=>`<span>${i+1}. ${esc(l?.label||l?.key||'Zdarzenie modelowe')}${window.TENIS_AI_PLAYABLE_UI_V917?.isPlayable?.(findMatch(keyOf(compactRow)||''),l)?' · Superbet ✓':''}</span>`).join('')}</div></div>`;
}

async function patchRawSymphonyMinis(){
  const compact=await loadCompact();if(!compact)return;
  for(const card of document.querySelectorAll('#app .p751-match-card[data-p751-open]')){
    const match=matchFromCard(card);if(!match)continue;
    const row=reportFind(compact,match,card.getAttribute('data-p751-open')||'');
    const comp=row?.composition;
    if(!Array.isArray(comp?.selection)||comp.selection.length<2)continue;
    let raw=card.querySelector('[data-rp920-symphony-raw]');
    if(!raw){raw=document.createElement('div');raw.dataset.rp920SymphonyRaw='1';const foot=card.querySelector('footer');if(foot)foot.before(raw);else card.append(raw)}
    raw.className='rp920-symphony-raw';
    raw.innerHTML=`<header><b>🎼 Symfonia modelowa · RAW</b><strong>${score(comp.symphony_score)}</strong></header><small>${comp.selection.length} zdarzenia · analiza modelowa</small><div class="rp920-sym-legs">${comp.selection.slice(0,3).map((l,i)=>`<span>${i+1}. ${esc(l?.label||l?.key||'Zdarzenie')}</span>`).join('')}</div>`;
  }
}

async function patchOverlay(){
  const overlay=document.querySelector('#p751-match-overlay:not([hidden])');
  if(!overlay)return;
  const rawKey=overlay.dataset.matchKey||'';
  const match=findMatch(rawKey);if(!match)return;
  let block=overlay.querySelector('[data-rp920-match-raw]');
  if(!block){
    block=document.createElement('section');block.className='rp920-block';block.dataset.rp920MatchRaw='1';
    const dc=overlay.querySelector('.dc87');
    if(dc)dc.before(block);else overlay.querySelector('.p751-detail-screen')?.prepend(block);
  }
  const raw=rawSignals(match,1)[0]||null;
  block.innerHTML=`<div class="rp920-head"><b>🧠 MODEL / RAW — pełna analiza meczu</b><span>${raw?score(valueOf(raw)):'N/D'}</span></div><p class="rp920-note">Ta warstwa nie zależy od Superbet. Linie i wyniki modelowe zostają widoczne także wtedy, gdy operator nie ma danego rynku.</p><details open><summary>Modelowe sygnały i linie</summary>${rawLinesHtml(match)}</details><details open><summary>🎯 SUPERBET — realne rynki i linie</summary>${superbetLinesHtml(match)}</details>`;

  const [compact,full]=await Promise.all([loadCompact(),loadFull()]);
  if(document.querySelector('#p751-match-overlay:not([hidden])')!==overlay)return;
  const cr=reportFind(compact,match,rawKey);const fr=reportFind(full,match,rawKey);const comp=bestModelComposition(fr,cr);
  let sym=overlay.querySelector('[data-rp920-symphony-detail]');
  if(!sym){sym=document.createElement('section');sym.className='rp920-block';sym.dataset.rp920SymphonyDetail='1';const playable=overlay.querySelector('[data-symphony-match-detail]');if(playable)playable.before(sym);else block.after(sym)}
  sym.innerHTML=`<div class="rp920-head"><b>🎼 SYMFONIA MODELOWA</b><span>RAW / analiza</span></div><p class="rp920-note">Scenariusz modelowy pozostaje widoczny niezależnie od tego, czy da się z niego zbudować zakład Superbet PLAYABLE.</p>${symphonyHtml(comp,cr)}`;
}

function statsMetric(row){
  if(!row)return {n:0,hits:0,misses:0,acc:'N/D',brier:'N/D'};
  return {n:Number(row.selected_n??row.n??0),hits:Number(row.hits??0),misses:Number(row.misses??0),acc:pct(row.accuracy),brier:finite(row.brier)?Number(row.brier).toFixed(5):'N/D'};
}
function shadowRow(label,row,status='SHADOW'){
  const m=statsMetric(row);return `<div class="rp920-model"><b>${esc(label)}</b><span>n ${m.n}</span><span>${m.acc}</span><span>B ${m.brier}</span><span class="rp920-hide-mobile">${esc(status)}</span><strong class="rp920-hide-mobile">0% PROD</strong></div>`;
}
function loadTelemetry(){
  if(telemetryPromise)return telemetryPromise;
  telemetryPromise=Promise.all([
    fetch('./data/model_telemetry_v84c.json?raw=920',{cache:'no-store'}).then(r=>r.ok?r.json():null),
    fetch('./data/player_model_shadow_v89.json?raw=920',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('./data/ensemble_player_learning_v891.json?raw=920',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('./data/surface_elo_integration_v893.json?raw=920',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)
  ]).catch(()=>[null,null,null,null]);
  return telemetryPromise;
}
async function renderStats(){
  const host=document.querySelector('#pc77');if(!host)return;
  const [telemetry,player,learning,elo]=await loadTelemetry();if(!telemetry||document.querySelector('#pc77')!==host)return;
  const scopes=telemetry.scopes||{};
  if(!scopes[statsScope])statsScope=scopes['30d']?'30d':Object.keys(scopes)[0]||'30d';
  const rows=scopes?.[statsScope]?.by_model||{};
  let panel=host.querySelector('#rp920-raw-model-stats');
  if(!panel){panel=document.createElement('section');panel.id='rp920-raw-model-stats';panel.className='rp920-block';const superbet=host.querySelector('#superbet-playable-stats-v912');if(superbet)superbet.before(panel);else host.prepend(panel)}
  const modelOrder=Object.keys(telemetry.models||{});
  const base=modelOrder.map(id=>{
    const m=statsMetric(rows[id]);
    return `<div class="rp920-model"><b>${esc(telemetry.models[id]||id)}</b><span>n ${m.n}</span><span>✓ ${m.hits}</span><span>✗ ${m.misses}</span><span>${m.acc}</span><strong>B ${m.brier}</strong></div>`;
  }).join('');
  const shadow=[
    shadowRow('Player Model + CatBoost',player?.holdout?.player_catboost_shadow,player?.gate?.status||player?.status||'SHADOW'),
    shadowRow('Ensemble + Player Learning',learning?.holdout?.ensemble_player_learning,learning?.gate?.status||learning?.status||'SHADOW'),
    shadowRow('CatBoost + Player + Surface Elo',elo?.holdout?.catboost_player_elo,elo?.gates?.catboost_player_elo?.status||'SHADOW'),
    shadowRow('Ensemble + Player + Surface Elo',elo?.holdout?.ensemble_player_elo,elo?.gates?.ensemble_player_elo?.status||'SHADOW'),
    shadowRow('TabPFN + Surface Elo',elo?.holdout?.tabpfn_elo,elo?.gates?.tabpfn_elo?.status||'SHADOW')
  ].join('');
  panel.innerHTML=`<div class="rp920-head"><div><b>📊 MODEL / RAW — statystyki wszystkich modeli</b><small>Pełna próbka modelowa jest niezależna od Superbet PLAYABLE.</small></div><span>${esc(statsScope)}</span></div><div class="rp920-scope">${Object.keys(scopes).map(k=>`<button type="button" data-rp920-scope="${esc(k)}" class="${k===statsScope?'active':''}">${esc(k)}</button>`).join('')}</div><div class="rp920-model-table"><div class="rp920-model"><b>Model</b><span>próbka</span><span>traf.</span><span>pudła</span><span>accuracy</span><strong>Brier</strong></div>${base}</div><div class="rp920-shadow"><h4>🧪 SHADOW — testowane warstwy, 0% wpływu na PROD</h4><div class="rp920-model-table">${shadow}</div></div><p class="rp920-note">🎯 Superbet PLAYABLE ma osobny panel i osobną próbkę. Nie zastępuje ani nie zeruje tych statystyk RAW.</p>`;
  panel.querySelectorAll('[data-rp920-scope]').forEach(btn=>btn.addEventListener('click',()=>{statsScope=btn.dataset.rp920Scope;renderStats()}));
}

async function renderRawSymphonyPage(){
  const shell=document.querySelector('#tennis-symphony-v90');if(!shell)return;
  const compact=await loadCompact();if(!compact||document.querySelector('#tennis-symphony-v90')!==shell)return;
  let panel=shell.querySelector('[data-rp920-symphony-page]');
  if(!panel){panel=document.createElement('section');panel.className='rp920-block';panel.dataset.rp920SymphonyPage='1';const controls=shell.querySelector('.symphony-controls');if(controls)controls.before(panel);else shell.prepend(panel)}
  const current=(compact.matches||[]).filter(r=>{
    const m=findMatch(String(r.match_key||r.id||''));
    return m&&(!window.TENIS_AI_MATCH_TIME?.isCurrent||window.TENIS_AI_MATCH_TIME.isCurrent(m));
  }).sort((a,b)=>Number(b?.composition?.symphony_score||0)-Number(a?.composition?.symphony_score||0)).slice(0,6);
  panel.innerHTML=`<div class="rp920-head"><b>🎼 SYMFONIA MODELOWA · RAW</b><span>${current.length} scenariuszy</span></div><p class="rp920-note">To niezależna analiza modelowa. Generator Superbet PLAYABLE poniżej może pokazać mniej meczów lub mniej nóg, bo wymaga realnych linii operatora.</p><div class="rp920-grid">${current.map(r=>`<div class="rp920-row"><b>${esc(r.p1)} vs ${esc(r.p2)}</b><small>${esc(r?.composition?.story_type||'scenariusz')} · ${Number(r?.composition?.selection?.length||0)} zdarzenia</small><strong>${score(r?.composition?.symphony_score)}</strong></div>`).join('')||'<div class="rp920-superbet-empty">Brak aktualnej Symfonii modelowej.</div>'}</div>`;
}

function patchAll(){
  injectStyle();patchCards();patchRawSymphonyMinis();patchOverlay();renderStats();renderRawSymphonyPage();
}
function schedule(ms=40){clearTimeout(timer);timer=setTimeout(patchAll,ms)}
function boot(){
  injectStyle();schedule(0);[180,700,1600].forEach(ms=>setTimeout(()=>schedule(0),ms));
  document.addEventListener('tenis-ai:stats-ready',()=>schedule(20));
  document.addEventListener('tenis-ai:stats-dashboard-ready',()=>schedule(20));
  document.addEventListener('click',e=>{
    if(e.target?.closest?.('[data-p751-open],[data-view="stats"],[data-p751-nav="matches"],[data-p751-nav="signals"],[data-sc-go="generator"],[data-rp920-scope]'))schedule(100);
  },true);
  if('MutationObserver'in window){
    const observer=new MutationObserver(records=>{
      if(records.some(r=>[...r.addedNodes].some(n=>n?.nodeType===1&&!n?.closest?.('[data-rp920-match-raw],#rp920-raw-model-stats,[data-rp920-symphony-raw]'))))schedule(90);
    });
    observer.observe(document.body,{childList:true,subtree:true});
  }
}

window.TENIS_AI_RAW_PLAYABLE_V920=Object.freeze({version:VERSION,patchAll,renderStats,patchOverlay,patchCards});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
