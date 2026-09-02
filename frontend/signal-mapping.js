/* Tenis AI v8.4D.4 — Signal Mapping Bridge
   Exact semantic aliases only. No fuzzy matching.
   Bridges equivalent game-state keys:
   state|2|1:1 <-> game_state|2|1:1 <-> state2|1:1
*/
(()=>{
  'use strict';

  const VERSION='v8.4D.4';
  const ROOT=typeof window!=='undefined'?window:globalThis;

  const norm=(v)=>String(v??'').trim().toLowerCase();
  const cleanPick=(v)=>norm(v).replace(/\s+/g,'');

  function parseStateSignal(signal){
    if(signal==null)return null;
    if(typeof signal==='string')signal={key:signal};

    const raw=String(signal?.key||signal?.signal_key||'').trim();
    const market=norm(signal?.market);
    let checkpoint=signal?.checkpoint!=null?String(signal.checkpoint):null;
    let pick=cleanPick(signal?.pick);

    const parts=raw.split('|').map(x=>String(x).trim());
    const head=norm(parts[0]);

    if(parts.length>=3 && ['state','game_state','gamestate'].includes(head)){
      if(['2','4','6'].includes(parts[1])){
        checkpoint=parts[1];
        if(!pick)pick=cleanPick(parts.slice(2).join('|'));
      }
    }

    if(parts.length>=2){
      const m=head.match(/^(?:state|game_state|gamestate)[_-]?([246])$/);
      if(m){
        checkpoint=m[1];
        if(!pick)pick=cleanPick(parts.slice(1).join('|'));
      }
    }

    if(!checkpoint){
      const m=market.match(/^(?:state|game_state|gamestate)[_-]?([246])$/);
      if(m)checkpoint=m[1];
    }

    if(!checkpoint && ['game_state','state'].includes(market)){
      const cp=String(signal?.checkpoint??'');
      if(['2','4','6'].includes(cp))checkpoint=cp;
    }

    if(!pick && raw){
      const tail=parts[parts.length-1];
      if(/^\d+:\d+$/.test(tail))pick=cleanPick(tail);
    }

    if(!['2','4','6'].includes(String(checkpoint||'')))return null;
    if(!/^\d+:\d+$/.test(pick))return null;

    return {checkpoint:String(checkpoint),pick};
  }

  function aliasesFor(signal){
    const raw=String(
      typeof signal==='string'
        ? signal
        : signal?.key||signal?.signal_key||''
    ).trim();

    const out=new Set();
    if(raw)out.add(raw);

    const state=parseStateSignal(signal);
    if(!state)return [...out];

    const cp=state.checkpoint;
    const pick=state.pick;

    [
      `state|${cp}|${pick}`,
      `game_state|${cp}|${pick}`,
      `gamestate|${cp}|${pick}`,
      `state${cp}|${pick}`,
      `state_${cp}|${pick}`,
      `game_state${cp}|${pick}`,
      `game_state_${cp}|${pick}`,
    ].forEach(x=>out.add(x));

    return [...out];
  }

  function sameStateSignal(a,b){
    const x=parseStateSignal(a);
    const y=parseStateSignal(b);
    return !!x && !!y &&
      x.checkpoint===y.checkpoint &&
      x.pick===y.pick;
  }

  function decorate(match,row,mapping,matchedKey){
    const a=match?.autolearn_v84||{};
    return {
      ...row,
      status:a.status,
      weights:a.weights,
      weight_policy:a.weight_policy||null,
      signal_mapping:{
        version:VERSION,
        mode:mapping,
        matched_key:matchedKey||String(row?.key||''),
      },
    };
  }

  function resolveFromMatch(match,signal){
    const a=match?.autolearn_v84;
    if(!a)return null;

    const raw=String(signal?.key||signal?.signal_key||'');

    if(raw && a?.by_key?.[raw]){
      return decorate(match,a.by_key[raw],'exact',raw);
    }

    for(const alias of aliasesFor(signal)){
      const row=a?.by_key?.[alias];
      if(row)return decorate(match,row,'state_alias',alias);
    }

    if(parseStateSignal(signal)){
      const row=(a?.signals||[]).find(x=>sameStateSignal(signal,x));
      if(row){
        return decorate(
          match,
          row,
          'state_semantic',
          String(row?.key||row?.signal_key||'')
        );
      }
    }

    return null;
  }

  const api={
    version:VERSION,
    parseStateSignal,
    aliasesFor,
    sameStateSignal,
    resolveFromMatch,
  };

  ROOT.TENIS_AI_SIGNAL_MAPPING_V84D4=api;

  const auto=ROOT.TENIS_AI_AUTOLEARN_V84;
  if(auto?.scoreFor && !auto.__v84d4_mapping_bridge){
    const original=auto.scoreFor.bind(auto);

    auto.scoreFor=function(match,signal){
      const direct=original(match,signal);
      if(direct)return {
        ...direct,
        signal_mapping:direct.signal_mapping||{
          version:VERSION,
          mode:'existing_scoreFor',
          matched_key:String(direct?.key||signal?.key||signal?.signal_key||''),
        },
      };

      return resolveFromMatch(match,signal);
    };

    auto.__v84d4_mapping_bridge=true;
    auto.signalMappingVersion=VERSION;
  }

  if(typeof module!=='undefined' && module.exports){
    module.exports=api;
  }
})();
