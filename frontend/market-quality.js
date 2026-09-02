/* Tenis AI v8.8.11 — CORE market quality layer
   v8.8.7 checkpoint lock + v8.8.8 winner lock + v8.8.9 result-market lock
   + v8.8.10 cross-view recommendation source + v8.8.11 exact-score LAB labels.
   Selection/presentation only: model probabilities, Adaptive PROD math,
   Dynamic Weights and stored telemetry are never modified.
*/
(()=>{
'use strict';

const CHECKPOINT_VERSION='v8.8.7';
const WINNER_VERSION='v8.8.8';
const RESULT_VERSION='v8.8.9';
const CROSS_VIEW_VERSION='v8.8.10';
const EXACT_LAB_VERSION='v8.8.11';

const CP_MIN_SETTLED=30;
const CP_MIN_ACCURACY=65;
const CP_MIN_WILSON=45;
const CP_MIN_RECENT_WHEN_FALLING=60;

const RESULT_MIN_SETTLED=30;
const RESULT_MIN_ACCURACY=65;
const RESULT_MIN_WILSON=45;

const WINNER_MARKETS=new Set(['match_winner','set1_winner','set2_winner','set3_winner']);
const RESULT_MARKETS=new Set([...WINNER_MARKETS,'total_sets']);
const MARKET_ALIASES={
  match_win:'match_winner',match_winner:'match_winner',
  set1_win:'set1_winner',set1_winner:'set1_winner',
  set2_win:'set2_winner',set2_winner:'set2_winner',
  set3_win:'set3_winner',set3_winner:'set3_winner',
  total_sets:'total_sets'
};

const state={
  telemetry:null,
  telemetryLoaded:false,
  loading:null,
  api:null,
  rawAllSignals:null,
  rawSignals:null,
  coreEventDepth:0,
  legacyBridgeInstalled:false,
  legacyRerenderDone:false,
  exactLabInstalled:false
};

const num=x=>Number.isFinite(Number(x))?Number(x):null;
const qEsc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const qCls=x=>x==null?'':x>=80?'elite':x>=72?'good':x<55?'warn':'';

function wilsonLower(hits,n){
  hits=num(hits);n=num(n);
  if(hits==null||n==null||n<=0)return null;
  const p=Math.max(0,Math.min(1,hits/n));
  const z=1.96,z2=z*z;
  const den=1+z2/n;
  const center=p+z2/(2*n);
  const adj=z*Math.sqrt((p*(1-p)+z2/(4*n))/n);
  return Math.max(0,(center-adj)/den)*100;
}

function checkpointOf(signal){
  const market=String(signal?.market||'').toLowerCase();
  const direct=num(signal?.checkpoint);
  if([2,4,6].includes(direct))return String(direct);
  const mm=market.match(/^state([246])$/);
  if(mm)return mm[1];
  if(market==='game_state'){
    const part=String(signal?.key||signal?.signal_key||'').split('|').find(x=>['2','4','6'].includes(String(x)));
    return part?String(part):null;
  }
  const key=String(signal?.key||signal?.signal_key||'');
  const km=key.match(/^state\|([246])\|/);
  return km?km[1]:null;
}

function canonicalMarket(signalOrMarket){
  if(typeof signalOrMarket==='string')return MARKET_ALIASES[String(signalOrMarket).toLowerCase()]||String(signalOrMarket).toLowerCase();
  const signal=signalOrMarket||{};
  const direct=MARKET_ALIASES[String(signal.market||'').toLowerCase()];
  if(direct)return direct;
  const key=String(signal.key||signal.signal_key||'').toLowerCase();
  const first=key.split('|')[0];
  return MARKET_ALIASES[first]||String(signal.market||first||'').toLowerCase();
}

function checkpointRow(cp){
  return state.telemetry?.game_state_progress_v84e2?.checkpoints?.[String(cp)]||null;
}

function checkpointEligible(cp,match){
  cp=String(cp||'');
  if(!['2','4','6'].includes(cp))return true;
  if(match?.early_hold_v7?.ready!==true)return false;

  const row=checkpointRow(cp);
  if(!row)return false;

  const n=num(row.settled)??0;
  const accuracy=num(row.accuracy);
  const lower=wilsonLower(row.hits,n);
  if(n<CP_MIN_SETTLED||accuracy==null||accuracy<CP_MIN_ACCURACY||lower==null||lower<CP_MIN_WILSON)return false;

  const trend=row.trend||{};
  const recent=num(trend.recent_accuracy);
  if(String(trend.status||'').toLowerCase()==='falling'&&recent!=null&&recent<CP_MIN_RECENT_WHEN_FALLING)return false;
  return true;
}

function resultRow(market){
  const canonical=canonicalMarket(market);
  return state.telemetry?.segments_30d?.market?.[canonical]?.adaptive_prod||null;
}

function resultEligible(market){
  const canonical=canonicalMarket(market);
  if(!RESULT_MARKETS.has(canonical))return true;

  // Fail closed until FINAL Adaptive PROD has a real settled selected sample.
  const row=resultRow(canonical);
  if(!row)return false;

  const n=num(row.selected_n)??0;
  const hits=num(row.hits)??0;
  const accuracy=num(row.accuracy);
  const lower=wilsonLower(hits,n);
  return n>=RESULT_MIN_SETTLED&&accuracy!=null&&accuracy>=RESULT_MIN_ACCURACY&&lower!=null&&lower>=RESULT_MIN_WILSON;
}

function winnerRow(market){return resultRow(market)}
function winnerEligible(market){
  const canonical=canonicalMarket(market);
  return WINNER_MARKETS.has(canonical)?resultEligible(canonical):true;
}

function signalEligible(signal,match){
  const cp=checkpointOf(signal);
  if(cp&&!checkpointEligible(cp,match))return false;
  const market=canonicalMarket(signal);
  if(RESULT_MARKETS.has(market)&&!resultEligible(market))return false;
  return true;
}

function filteredSignals(raw,match){
  const rows=Array.isArray(raw)?raw:[];
  return rows.filter(signal=>signalEligible(signal,match));
}

function installModelGate(){
  const api=window.TENIS_AI_MODEL_API;
  if(!api||typeof api.allSignals!=='function'||api===state.api)return false;

  state.api=api;
  state.rawAllSignals=api.allSignals;
  state.rawSignals=typeof api.signals==='function'?api.signals:null;

  const rawAll=state.rawAllSignals;
  api.allSignals=function(match){
    const rows=rawAll.call(api,match);
    // Full diagnostics/manual/SHADOW stay untouched. Only one synchronous
    // CORE "Generate" event activates the allSignals filter.
    return state.coreEventDepth>0?filteredSignals(rows,match):rows;
  };

  if(state.rawSignals){
    const rawSelected=state.rawSignals;
    api.signals=function(match,limit=20){
      const wanted=Math.max(1,Number(limit)||20);
      const rows=rawSelected.call(api,match,Math.max(wanted,20));
      return filteredSignals(rows,match).slice(0,wanted);
    };
  }

  if(typeof api.rawAllSignalsV887!=='function')api.rawAllSignalsV887=(match)=>rawAll.call(api,match);
  return true;
}

function finalSelectedSignals(match,limit=3){
  const api=window.TENIS_AI_MODEL_API;
  if(!api||typeof api.signals!=='function')return [];
  const wanted=Math.max(1,Number(limit)||3);
  try{return (api.signals(match,Math.max(wanted,3))||[]).slice(0,wanted)}catch{return []}
}

function signalDisplayLabel(signal){
  const votes=Number(signal?.votes);
  const prefix=Number.isFinite(votes)&&votes>0?`${votes}/5 · `:'';
  return `${prefix}${String(signal?.label||signal?.pick||signal?.key||'Sygnał')}`;
}

function legacyPill(signal){
  const v=num(signal?.v);
  if(v==null)return '';
  return `<div class="market ${qCls(v)}"><span>${qEsc(signalDisplayLabel(signal))}</span><b>${Math.round(v)} / 100</b></div>`;
}

function installLegacyRecommendationBridge(){
  if(state.legacyBridgeInstalled)return false;
  if(!window.TENIS_AI_MODEL_API||typeof window.TENIS_AI_MODEL_API.signals!=='function')return false;

  // app.js and multi-model.js used to keep their own raw "strongest" path.
  // Replace only presentation helpers so cards use the same FINAL + Quality
  // source as Decision Center and Generator. Model math remains untouched.
  if(typeof window.bestSignalsData==='function'){
    window.bestSignalsData=(match,limit=3)=>finalSelectedSignals(match,limit).map(x=>({label:signalDisplayLabel(x),v:x.v,market:x.market,pick:x.pick,key:x.key}));
  }
  if(typeof window.bestSignals==='function'){
    window.bestSignals=match=>{
      const top=finalSelectedSignals(match,3);
      if(!top.length)return '';
      return `<div class="signals"><div class="signals-title">FINAL Adaptive PROD · Quality Lock</div><div class="signals-grid">${top.map(legacyPill).join('')}</div></div>`;
    };
  }
  if(typeof window.compactSignals==='function'){
    window.compactSignals=match=>{
      const top=finalSelectedSignals(match,2);
      if(!top.length)return '';
      return `<div class="compact-signals">${top.map(x=>`<span class="compact-signal ${qCls(x.v)}">${qEsc(signalDisplayLabel(x))} <b>${Math.round(Number(x.v))}</b></span>`).join('')}</div>`;
    };
  }

  state.legacyBridgeInstalled=true;

  // If cards were rendered unusually early, do exactly one controlled refresh.
  if(!state.legacyRerenderDone&&document.querySelector('#app .match-card')&&typeof window.renderMatches==='function'){
    state.legacyRerenderDone=true;
    queueMicrotask(()=>{try{window.renderMatches()}catch{}});
  }
  return true;
}

function exactLabPill(label,value){
  const v=num(value);
  if(v==null)return '';
  return `<div class="market"><span>${qEsc(label)}</span><b>${Math.round(v)} / 100</b><em>LAB · niezwalidowane</em></div>`;
}

function exactLabBox(title,body,format=''){
  if(!body)return '';
  const suffix=format?` · ${qEsc(format)}`:'';
  return `<details class="marketbox exact-lab"><summary><span class="summary-title">${qEsc(title)}</span><span class="tag">MODEL LAB${suffix} · N/D</span><span class="chev">⌄</span></summary><div class="marketbody">${body}<p class="modelnote">Rynek informacyjny: brak osobnej telemetrii FINAL i potwierdzonej trafności. Nie wchodzi do CORE.</p></div></details>`;
}

function installExactScoreLabLabels(){
  if(state.exactLabInstalled)return false;
  if(typeof window.exactSet!=='function'||typeof window.exactMatch!=='function')return false;

  window.exactSet=match=>{
    if(!match?.exact_first_set)return '';
    const entries=Object.entries(match.exact_first_set).filter(([,v])=>num(v)!=null&&num(v)>=1).slice(0,14);
    if(!entries.length)return '';
    return exactLabBox('🎯 Dokładny wynik 1. seta',`<div class="pillgrid exact">${entries.map(([score,value])=>exactLabPill(score,value)).join('')}</div>`);
  };

  window.exactMatch=match=>{
    if(!match?.exact_match_score)return '';
    const entries=Object.entries(match.exact_match_score).filter(([,v])=>num(v)!=null);
    if(!entries.length)return '';
    return exactLabBox('🎯 Dokładny wynik meczu',`<div class="pillgrid exact four">${entries.map(([score,value])=>exactLabPill(score,value)).join('')}</div>`,'BO3');
  };

  state.exactLabInstalled=true;
  return true;
}

function activeScenarioProfile(){
  return String(document.querySelector('#scenario-v82a-panel .sc82-profiles .active[data-sc-profile]')?.dataset.scProfile||'balanced').toLowerCase();
}

function isCoreGenerateEvent(event){
  const button=event.target?.closest?.('#scenario-v82a-panel [data-sc-generate]');
  return !!button&&activeScenarioProfile()!=='experimental';
}

function beginCoreEvent(){
  state.coreEventDepth+=1;
  queueMicrotask(()=>{state.coreEventDepth=Math.max(0,state.coreEventDepth-1)});
}

function wrapProjectOpen(){
  const api=window.TENIS_AI_PROJECT_UI;
  if(!api||api.__marketQualityV8811||typeof api.openMatch!=='function')return;
  const open=api.openMatch;
  api.openMatch=(...args)=>{
    const result=open.apply(api,args);
    queueMicrotask(patchDecisionCenters);
    return result;
  };
  Object.defineProperty(api,'__marketQualityV8811',{value:true,configurable:false});
}

function checkpointStatusText(){
  return ['2','4','6'].map(cp=>{
    const row=checkpointRow(cp);
    if(!row)return `${cp}g N/D`;
    const acc=num(row.accuracy),n=num(row.settled)||0;
    return `${cp}g ${acc==null?'N/D':acc.toFixed(1)+'%'} (n=${n})`;
  }).join(' · ');
}

function resultStatusText(){
  const short={match_winner:'Mecz',set1_winner:'1S',set2_winner:'2S',set3_winner:'3S',total_sets:'Sety'};
  return [...RESULT_MARKETS].map(market=>{
    const row=resultRow(market);
    if(!row)return `${short[market]} N/D`;
    const acc=num(row.accuracy),n=num(row.selected_n)||0;
    return `${short[market]} ${acc==null?'N/D':acc.toFixed(1)+'%'} (n=${n})`;
  }).join(' · ');
}

function winnerStatusText(){
  return resultStatusText().split(' · ').filter(x=>!x.startsWith('Sety ')).join(' · ');
}

function patchScenarioNote(){
  const builder=document.querySelector('#scenario-v82a-panel .sc82-builder');
  if(!builder)return;
  let note=builder.querySelector('[data-v887-checkpoint-note]');
  if(!note){
    note=document.createElement('p');
    note.className='sc82-small';
    note.dataset.v887CheckpointNote='1';
    builder.appendChild(note);
  }
  note.innerHTML='<b>🔒 CORE Market Quality Lock:</b> checkpoint 2/4/6g wymaga PBP + ≥65% (n≥30, Wilson ≥45%); zwycięzca meczu/setu i liczba setów wymagają FINAL Adaptive PROD ≥65% (n≥30, Wilson ≥45%). Karty meczu, Top i Generator korzystają z jednego źródła FINAL. Exact score pozostaje MODEL LAB / N/D. Manual i Model Test/SHADOW zachowują pełne rynki. <span data-v889-status></span>';
  const span=note.querySelector('[data-v889-status]');
  if(span)span.textContent=state.telemetryLoaded?`Checkpointy: ${checkpointStatusText()}. Rynki wyniku: ${resultStatusText()}.`:'Telemetria: ładowanie…';
}

function currentDecisionMatch(root){
  const overlay=root?.closest?.('#p751-match-overlay')||document.querySelector('#p751-match-overlay');
  const key=overlay?.dataset?.matchKey;
  if(!key)return null;
  try{return window.TENIS_AI_PROJECT_UI?.findMatch?.(key)||null}catch{return null}
}

function patchDecisionCenter(root){
  if(!root)return;
  const topSelected=root.querySelector('[data-dc-mode="top"][aria-selected="true"]');
  const oldNote=root.querySelector('[data-v887-dc-note]');
  if(!topSelected){oldNote?.remove();return}

  const match=currentDecisionMatch(root);
  const grid=root.querySelector('[data-dc-grid]');
  if(!grid)return;

  let removed=0;
  [...grid.querySelectorAll('.dc87-card')].forEach(card=>{
    const market=String(card.dataset.dcMarket||'').toLowerCase();
    const cp=market.match(/^state([246])$/)?.[1];
    const blockedCheckpoint=cp&&!checkpointEligible(cp,match);
    const canonical=canonicalMarket(market);
    const blockedResult=RESULT_MARKETS.has(canonical)&&!resultEligible(canonical);
    if(blockedCheckpoint||blockedResult){card.remove();removed+=1}
  });

  const visible=grid.querySelectorAll('.dc87-card').length;
  const count=root.querySelector('[data-dc-count]');
  if(count&&removed)count.innerHTML=count.innerHTML.replace(/Widoczne\s*<b>\d+<\/b>/i,`Widoczne <b>${visible}</b>`);

  if(!visible&&!grid.querySelector('.dc87-empty')){
    grid.innerHTML='<div class="dc87-empty"><b>Brak rynków spełniających CORE Quality Lock</b>Pełne dane pozostają w „Wszystkie” i „PRO”; Top pokazuje tylko rynki z potwierdzoną historią.</div>';
  }

  let note=oldNote;
  if(!note){
    note=document.createElement('p');
    note.className='dc87-note';
    note.dataset.v887DcNote='1';
    count?.insertAdjacentElement('afterend',note);
  }
  if(note){
    const pbp=match?.early_hold_v7?.ready===true?'PBP OK':'PBP N/D';
    note.textContent=`🔒 CORE Quality Lock: checkpointy wymagają PBP + n≥30; rynki wyniku wymagają FINAL ≥65% przy n≥30. ${pbp}. ${state.telemetryLoaded?resultStatusText():'Telemetria: ładowanie…'}`;
  }
}

function patchDecisionCenters(){document.querySelectorAll('.dc87').forEach(patchDecisionCenter)}

function loadTelemetry(){
  if(state.loading)return state.loading;
  state.loading=fetch('data/model_telemetry_v84c.json')
    .then(response=>response.ok?response.json():null)
    .then(data=>{state.telemetry=data||null;state.telemetryLoaded=!!data;return data})
    .catch(()=>{state.telemetry=null;state.telemetryLoaded=false;return null})
    .finally(()=>{patchScenarioNote();patchDecisionCenters()});
  return state.loading;
}

function patchAll(){
  installModelGate();
  installLegacyRecommendationBridge();
  installExactScoreLabLabels();
  wrapProjectOpen();
  patchScenarioNote();
  patchDecisionCenters();
}

function boot(){
  patchAll();
  loadTelemetry();

  document.addEventListener('click',event=>{
    if(isCoreGenerateEvent(event))beginCoreEvent();
    queueMicrotask(patchAll);
  },true);

  setTimeout(patchAll,300);
  setTimeout(patchAll,1150);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_CHECKPOINT_QUALITY_V887=Object.freeze({
  version:CHECKPOINT_VERSION,
  thresholds:Object.freeze({minSettled:CP_MIN_SETTLED,minAccuracy:CP_MIN_ACCURACY,minWilson:CP_MIN_WILSON,minRecentWhenFalling:CP_MIN_RECENT_WHEN_FALLING}),
  checkpointOf,
  checkpointEligible,
  signalEligible,
  wilsonLower,
  telemetry:()=>state.telemetry
});

window.TENIS_AI_WINNER_QUALITY_V888=Object.freeze({
  version:WINNER_VERSION,
  markets:Object.freeze([...WINNER_MARKETS]),
  thresholds:Object.freeze({minSettled:RESULT_MIN_SETTLED,minAccuracy:RESULT_MIN_ACCURACY,minWilson:RESULT_MIN_WILSON}),
  canonicalMarket,
  row:winnerRow,
  eligible:winnerEligible,
  signalEligible,
  telemetry:()=>state.telemetry
});

window.TENIS_AI_RESULT_QUALITY_V889=Object.freeze({
  version:RESULT_VERSION,
  markets:Object.freeze([...RESULT_MARKETS]),
  thresholds:Object.freeze({minSettled:RESULT_MIN_SETTLED,minAccuracy:RESULT_MIN_ACCURACY,minWilson:RESULT_MIN_WILSON}),
  canonicalMarket,
  row:resultRow,
  eligible:resultEligible,
  signalEligible,
  telemetry:()=>state.telemetry
});

window.TENIS_AI_CROSS_VIEW_QUALITY_V8810=Object.freeze({
  version:CROSS_VIEW_VERSION,
  selected:finalSelectedSignals,
  bridge:installLegacyRecommendationBridge
});

window.TENIS_AI_EXACT_SCORE_LAB_V8811=Object.freeze({
  version:EXACT_LAB_VERSION,
  install:installExactScoreLabLabels
});
})();
