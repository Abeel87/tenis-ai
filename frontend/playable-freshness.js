/* Tenis AI v9.2.8 — bounded freshness wrapper for actionable Superbet PLAYABLE.
   Presentation gate only. MODEL/RAW, scores, training, prices and history remain untouched.

   IMPORTANT: the Superbet catalogue refresh is hourly and the operator-aware Symphony
   rebuild can take ~20 minutes. A 12-minute UI TTL therefore expired before a freshly
   rebuilt report was even published. Keep the gate strict/exact, but make its age bound
   compatible with the real refresh cadence: one hourly interval + rebuild/deploy margin.
*/
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

  // Match Browser is a stable presentation runtime. Load it only after the
  // strict PLAYABLE gate has replaced the base API so Top SUPERBET and the
  // main list evaluate the exact same final predicates.
  if(typeof document!=='undefined'&&document.body&&!document.getElementById('tenis-ai-match-browser')){
    const script=document.createElement('script');
    script.id='tenis-ai-match-browser';
    script.src='match-browser.js';
    script.async=false;
    document.body.appendChild(script);
  }
})();
