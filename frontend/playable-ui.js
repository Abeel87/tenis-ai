/* Tenis AI v9.4.8 — Symphony-final PLAYABLE gate for actionable UI.
   MODEL/RAW analytics stay independent. This bridge only verifies actionable
   Superbet surfaces against the current fixture offer.

   IMPORTANT UI OWNERSHIP:
   The current #product-shell/project-ui renderer owns presentation. Legacy
   PLAYABLE card/top/Decision Center decorators are kept only for old-shell
   compatibility and are never mounted into the current product shell.
*/
(()=>{
'use strict';
if(window.TENIS_AI_PLAYABLE_UI_V917)return;

const VERSION='v9.4.8';
const WRAP='__tenisAiPlayableUiV923';
const LINE_MARKETS=new Set([
  'match_total','set1_total','set2_total','set3_total','total_sets',
  'match_game_handicap','set1_game_handicap','set2_game_handicap','set3_game_handicap','set_handicap',
  'player_total_games','match_total_aces','player_aces','player_double_faults'
]);
const PLAYER_MARKETS=new Set(['player_total_games','player_aces','player_double_faults']);
const WINNER_MARKETS=new Set([
  'match_winner','set1_winner','set2_winner','set3_winner',
  'most_aces','most_double_faults','most_aces_plus_df'
]);
const ALIASES={
  match_win:'match_winner',
  first_set_win:'set1_winner',set1_win:'set1_winner',
  second_set_win:'set2_winner',set2_win:'set2_winner',
  third_set_win:'set3_winner',set3_win:'set3_winner',
  exact_set1:'set1_exact_score',exact_first_set:'set1_exact_score',
  exact_match:'exact_match_score',
  state2:'game_state',state4:'game_state',state6:'game_state'
};

const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const num=v=>finite(v)?Number(v):null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9:.+\-]+/g,' ').replace(/\s+/g,' ').trim();
const nameKey=v=>norm(v).replace(/[^a-z0-9]+/g,' ').split(' ').filter(Boolean).sort().join(' ');

function canonicalShell(){
  return typeof document!=='undefined'&&typeof document.getElementById==='function'&&!!document.getElementById('product-shell');
}
function canonicalMarket(value){
  const raw=norm(value).replace(/ /g,'_');
  return ALIASES[raw]||raw;
}
function context(match){
  const x=match?.superbet_market_v91;
  return x&&typeof x==='object'?x:{};
}
function freshContext(x,now=Date.now()){
  const generated=Date.parse(x?.source_generated_at||'');
  const maxHours=x?.source_max_age_hours??1.8;
  const age=Number(now)-generated;
  return finite(maxHours)&&Number(maxHours)>0&&Number.isFinite(age)&&age>=0&&age<=Number(maxHours)*3600000;
}
function fallbackNonPrematchStatus(match){
  const result=match?.result&&typeof match.result==='object'?match.result:{};
  const raw=[match?.event_status,match?.feed_status,match?.status,result.status]
    .map(v=>norm(v)).filter(Boolean).join(' ')
    .replace(/\bnot[- ]started\b/g,' ');
  return /\b(?:live|playing|started|in[- ]progress|completed|finished|settled|retired|cancelled|canceled|postponed|abandoned|walkover|void|suspended|interrupted)\b/.test(raw);
}
function preMatch(match,now=Date.now()){
  const scheduled=Date.parse(match?.scheduled_time||'');
  if(!Number.isFinite(scheduled)||scheduled<=Number(now))return false;
  const kind=window.TENIS_AI_MATCH_TIME?.statusKind?.(match);
  return kind?kind==='scheduled':!fallbackNonPrematchStatus(match);
}
function active(match,now=Date.now()){
  const x=context(match);
  return x.operator_verified===true&&x.status==='VERIFIED'&&x.suspended!==true&&Array.isArray(x.canonical_selections)
    &&freshContext(x,now)&&preMatch(match,now);
}
function keyParts(row){return String(row?.key||row?.signal_key||'').split('|')}
function rowLine(row,market=canonicalMarket(row?.market)){
  const direct=num(row?.line??row?.selected_line??row?.suggested_line);
  if(direct!=null)return direct;
  const pick=String(row?.pick||row?.displayPick||'');
  if(market==='total_sets'){
    const m=pick.match(/(-?\d+(?:\.\d+)?)/);
    if(m)return Number(m[1]);
  }
  const p=keyParts(row);
  if(p[0]==='superbet'&&num(p[4])!=null)return Number(p[4]);
  if(LINE_MARKETS.has(market)&&num(p[1])!=null)return Number(p[1]);
  return null;
}
function rowCheckpoint(row,market=canonicalMarket(row?.market)){
  const direct=num(row?.checkpoint);
  if(direct!=null)return Math.trunc(direct);
  const raw=norm(row?.market).replace(/ /g,'_');
  const state=raw.match(/^state([246])$/);
  if(state)return Number(state[1]);
  const p=keyParts(row);
  if(p[0]==='superbet'&&num(p[2])!=null)return Math.trunc(Number(p[2]));
  if(market==='game_state'&&num(p[1])!=null)return Math.trunc(Number(p[1]));
  return 0;
}
function rowPlayer(row,market=canonicalMarket(row?.market)){
  if(!PLAYER_MARKETS.has(market))return'';
  const direct=row?.player??row?.extra;
  if(direct)return nameKey(direct);
  const p=keyParts(row);
  return p[0]==='superbet'?nameKey(p[3]):'';
}
function pickKey(value,market){
  const raw=norm(value);
  if(WINNER_MARKETS.has(market))return nameKey(value);
  if(['set1_exact_score','exact_match_score','game_state'].includes(market)){
    const m=String(value??'').match(/(\d+)\s*[:\-]\s*(\d+)/);
    return m?`${Number(m[1])}:${Number(m[2])}`:raw;
  }
  if(raw==='o'||raw==='over'||raw.startsWith('over ')||raw==='powyzej')return'over';
  if(raw==='u'||raw==='under'||raw.startsWith('under ')||raw==='ponizej')return'under';
  if(raw==='tak'||raw==='yes')return'yes';
  if(raw==='nie'||raw==='no')return'no';
  return raw;
}
function rowPick(row,market=canonicalMarket(row?.market)){
  let value=row?.pick??'';
  const p=keyParts(row);
  if(!value&&p[0]==='superbet')value=p[5]||'';
  return pickKey(value,market);
}
function signature(row){
  const market=canonicalMarket(row?.market);
  const line=LINE_MARKETS.has(market)?rowLine(row,market):null;
  const checkpoint=market==='game_state'?rowCheckpoint(row,market):0;
  const player=rowPlayer(row,market);
  return [market,rowPick(row,market),line==null?'':Number(line).toFixed(6),checkpoint||0,player].join('¦');
}
function operatorEvidenceVerified(row){
  if(!row||typeof row!=='object'||row.operator_available!==true)return false;
  const market=canonicalMarket(row.market);
  if(!LINE_MARKETS.has(market))return true;
  return rowLine(row,market)!=null&&row.operator_line_verified===true&&row.fixture_line_verified===true;
}
function availability(match){
  const out=new Map();
  if(!active(match))return out;
  for(const row of context(match).canonical_selections||[]){
    if(!operatorEvidenceVerified(row))continue;
    out.set(signature(row),row);
  }
  return out;
}
function isPlayable(match,row){
  if(!active(match)||!row||typeof row!=='object')return false;
  return availability(match).has(signature(row));
}
function valueOf(row){return num(row?.operator_model_probability??row?.v??row?.final_score??row?.adaptive_prod_score??row?.score??row?.current)}
function modelSignals(match,limit=100){
  const api=window.TENIS_AI_MODEL_API;
  let rows=[];
  try{
    if(typeof api?.signals==='function')rows=api.signals(match,Math.max(100,Number(limit)||100))||[];
    else if(typeof api?.allSignals==='function')rows=api.allSignals(match)||[];
  }catch{return[]}
  return rows.filter(row=>valueOf(row)!=null)
    .sort((a,b)=>(valueOf(b)||0)-(valueOf(a)||0))
    .slice(0,Math.max(1,Number(limit)||100));
}
function projectionSignals(match){
  const layer=match?.symphony2_playable;
  if(!layer||typeof layer!=='object'||layer.final_playable_authority!==true||layer.playable!==true||!Array.isArray(layer.signals))return[];
  return layer.signals
    .filter(row=>row&&typeof row==='object'&&valueOf(row)!=null&&isPlayable(match,row))
    .sort((a,b)=>(valueOf(b)||0)-(valueOf(a)||0));
}
function playableSignals(match,limit=100){
  if(!active(match))return[];
  const max=Math.max(1,Number(limit)||100);
  return projectionSignals(match).slice(0,max);
}
function scoreText(v){return finite(v)?`${Math.round(Number(v))}/100`:'N/D'}
function decode(value){try{return decodeURIComponent(String(value||''))}catch{return String(value||'')}}
function findMatch(raw){
  const key=decode(raw).replace(/^id:/,'');
  try{return window.TENIS_AI_PROJECT_UI?.findMatch?.(key)||null}catch{return null}
}
function matchFor(el){
  const holder=el?.closest?.('[data-p751-open]')||el;
  return findMatch(holder?.getAttribute?.('data-p751-open')||'');
}
function sameSelection(a,b){return !!a&&!!b&&signature(a)===signature(b)}
function compositionPlayable(match,comp){
  const legs=comp?.selection;
  return active(match)&&Array.isArray(legs)&&legs.length>=2&&legs.every(leg=>isPlayable(match,leg));
}

window.TENIS_AI_PLAYABLE_UI_V917=Object.freeze({version:VERSION,active,freshContext,preMatch,compositionPlayable,canonicalMarket,signature,isPlayable,playableSignals,availability});
})();

/* Existing freshness and schedule-alignment guard, consolidated without its DOM loader. */
(()=>{
  'use strict';
  if(window.TENIS_AI_PLAYABLE_LINE_FRESHNESS_V925)return;
  const base=window.TENIS_AI_PLAYABLE_UI_V917;
  if(!base)return;

  const VERSION='v9.2.8';
  const MAX_OPERATOR_AGE_MS=90*60*1000;
  const MAX_START_DRIFT_MS=35*60*1000;
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));

  function context(match){
    const x=match?.superbet_market_v91;
    return x&&typeof x==='object'?x:{};
  }
  function sourceAgeMs(match,now=Date.now()){
    const generated=Date.parse(context(match)?.source_generated_at||'');
    return Number.isFinite(generated)?Number(now)-generated:Infinity;
  }
  function sourceFresh(match,now=Date.now()){
    const age=sourceAgeMs(match,now);
    return Number.isFinite(age)&&age>=0&&age<=MAX_OPERATOR_AGE_MS;
  }
  function startAligned(match){
    const op=Date.parse(context(match)?.operator_start_time||'');
    const fixture=Date.parse(match?.scheduled_time||'');
    if(!Number.isFinite(op)||!Number.isFinite(fixture))return true;
    return Math.abs(op-fixture)<=MAX_START_DRIFT_MS;
  }
  function strictActive(match,now=Date.now()){
    return base.active?.(match,now)===true&&sourceFresh(match,now)&&startAligned(match);
  }
  function strictIsPlayable(match,row){
    return strictActive(match)&&base.isPlayable?.(match,row)===true;
  }
  function strictCompositionPlayable(match,comp){
    const legs=comp?.selection;
    return strictActive(match)&&Array.isArray(legs)&&legs.length>=2&&legs.every(leg=>strictIsPlayable(match,leg));
  }
  function strictPlayableSignals(match,limit=100){
    if(!strictActive(match))return[];
    const rows=base.playableSignals?.(match,Math.max(100,Number(limit)||100))||[];
    return rows.filter(row=>strictIsPlayable(match,row)).slice(0,Math.max(1,Number(limit)||100));
  }

  const wrapped=Object.freeze({
    ...base,
    version:VERSION,
    active:strictActive,
    isPlayable:strictIsPlayable,
    compositionPlayable:strictCompositionPlayable,
    playableSignals:strictPlayableSignals,
    sourceFresh,
    sourceAgeMs,
    startAligned,
    maxOperatorAgeMinutes:MAX_OPERATOR_AGE_MS/60000
  });
  window.TENIS_AI_PLAYABLE_UI_V917=wrapped;
  window.TENIS_AI_PLAYABLE_LINE_FRESHNESS_V925=Object.freeze({
    version:VERSION,sourceFresh,sourceAgeMs,startAligned,maxOperatorAgeMinutes:MAX_OPERATOR_AGE_MS/60000
  });

})();
