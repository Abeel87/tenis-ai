/* Tenis AI v8.8.8 — CORE market quality layer
   v8.8.7 checkpoint lock + v8.8.8 winner-market lock.
   Selection/presentation only: model probabilities, Adaptive PROD math,
   Dynamic Weights and stored telemetry are never modified.
*/
(()=>{
'use strict';

const CHECKPOINT_VERSION='v8.8.7';
const WINNER_VERSION='v8.8.8';

const CP_MIN_SETTLED=30;
const CP_MIN_ACCURACY=65;
const CP_MIN_WILSON=45;
const CP_MIN_RECENT_WHEN_FALLING=60;

const WIN_MIN_SETTLED=30;
const WIN_MIN_ACCURACY=65;
const WIN_MIN_WILSON=45;

const WINNER_MARKETS=new Set(['match_winner','set1_winner','set2_winner','set3_winner']);
const MARKET_ALIASES={
  match_win:'match_winner',match_winner:'match_winner',
  set1_win:'set1_winner',set1_winner:'set1_winner',
  set2_win:'set2_winner',set2_winner:'set2_winner',
  set3_win:'set3_winner',set3_winner:'set3_winner'
};

const state={
  telemetry:null,
  telemetryLoaded:false,
  loading:null,
  api:null,
  rawAllSignals:null,
  rawSignals:null,
  coreEventDepth:0
};

const num=x=>Number.isFinite(Number(x))?Number(x):null;

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

function winnerRow(market){
  const canonical=canonicalMarket(market);
  return state.telemetry?.segments_30d?.market?.[canonical]?.adaptive_prod||null;
}

function winnerEligible(market){
  const canonical=canonicalMarket(market);
  if(!WINNER_MARKETS.has(canonical))return true;

  // Fail closed until FINAL Adaptive PROD has a real, settled selected sample.
  const row=winnerRow(canonical);
  if(!row)return false;

  const n=num(row.selected_n)??0;
  const hits=num(row.hits)??0;
  const accuracy=num(row.accuracy);
  const lower=wilsonLower(hits,n);
  return n>=WIN_MIN_SETTLED&&accuracy!=null&&accuracy>=WIN_MIN_ACCURACY&&lower!=null&&lower>=WIN_MIN_WILSON;
}

function signalEligible(signal,match){
  const cp=checkpointOf(signal);
  if(cp&&!checkpointEligible(cp,match))return false;
  const market=canonicalMarket(signal);
  if(WINNER_MARKETS.has(market)&&!winnerEligible(market))return false;
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
  if(!api||api.__marketQualityV888||typeof api.openMatch!=='function')return;
  const open=api.openMatch;
  api.openMatch=(...args)=>{
    const result=open.apply(api,args);
    queueMicrotask(patchDecisionCenters);
    return result;
  };
  Object.defineProperty(api,'__marketQualityV888',{value:true,configurable:false});
}

function checkpointStatusText(){
  return ['2','4','6'].map(cp=>{
    const row=checkpointRow(cp);
    if(!row)return `${cp}g N/D`;
    const acc=num(row.accuracy),n=num(row.settled)||0;
    return `${cp}g ${acc==null?'N/D':acc.toFixed(1)+'%'} (n=${n})`;
  }).join(' · ');
}

function winnerStatusText(){
  const short={match_winner:'Mecz',set1_winner:'1S',set2_winner:'2S',set3_winner:'3S'};
  return [...WINNER_MARKETS].map(market=>{
    const row=winnerRow(market);
    if(!row)return `${short[market]} N/D`;
    const acc=num(row.accuracy),n=num(row.selected_n)||0;
    return `${short[market]} ${acc==null?'N/D':acc.toFixed(1)+'%'} (n=${n})`;
  }).join(' · ');
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
  note.innerHTML='<b>🔒 CORE Market Quality Lock:</b> checkpoint 2/4/6g wymaga PBP + ≥65% (n≥30, Wilson ≥45%); zwycięzca meczu/setu wymaga FINAL Adaptive PROD ≥65% (n≥30, Wilson ≥45%). Manual i Model Test/SHADOW zachowują pełne rynki. <span data-v888-status></span>';
  const span=note.querySelector('[data-v888-status]');
  if(span)span.textContent=state.telemetryLoaded?`Checkpointy: ${checkpointStatusText()}. Winner: ${winnerStatusText()}.`:'Telemetria: ładowanie…';
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
    const blockedWinner=WINNER_MARKETS.has(canonicalMarket(market))&&!winnerEligible(market);
    if(blockedCheckpoint||blockedWinner){card.remove();removed+=1}
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
    note.textContent=`🔒 CORE Quality Lock: checkpointy wymagają PBP + n≥30; winner markets wymagają FINAL ≥65% przy n≥30. ${pbp}. ${state.telemetryLoaded?winnerStatusText():'Telemetria: ładowanie…'}`;
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
  thresholds:Object.freeze({minSettled:WIN_MIN_SETTLED,minAccuracy:WIN_MIN_ACCURACY,minWilson:WIN_MIN_WILSON}),
  canonicalMarket,
  row:winnerRow,
  eligible:winnerEligible,
  signalEligible,
  telemetry:()=>state.telemetry
});
})();
