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

window.TENIS_AI_MARKET_QUALITY={signalEligible,checkpointEligible,resultEligible,wilsonLower,selected:finalSelectedSignals,setTelemetry(value){state.telemetry=value;state.telemetryLoaded=!!value;installModelGate()}};
installModelGate();
})();
