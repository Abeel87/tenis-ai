/* Existing settlement helper retained verbatim; presentation removed. */
(()=>{
const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');
  function marketOutcome(e,s){
    const existing=String(s?.result||'').toLowerCase();
    if(['hit','miss','void','unverifiable'].includes(existing))return existing;
    if(e?.status!=='settled'||!e?.result)return existing||'pending';
    const r=e.result, market=String(s?.market||''), pick=String(s?.pick||''), line=num(s?.line);
    const p1=norm(e.p1), p2=norm(e.p2), wanted=norm(pick);
    const winnerForSet=i=>{
      const z=r.sets?.[i]; if(!Array.isArray(z)||z.length<2||z[0]===z[1])return null;
      return z[0]>z[1]?p1:p2;
    };
    if(market==='match_winner'&&r.winner)return norm(r.winner)===wanted?'hit':'miss';
    if(market==='set1_winner'){const w=winnerForSet(0);return w?w===wanted?'hit':'miss':'unverifiable'}
    if(market==='set2_winner'){const w=winnerForSet(1);return w?w===wanted?'hit':'miss':'void'}
    if(market==='set3_winner'){const w=winnerForSet(2);return w?w===wanted?'hit':'miss':'void'}
    if(market==='set1_total'&&line!=null&&Array.isArray(r.sets?.[0])){
      const total=Number(r.sets[0][0])+Number(r.sets[0][1]);
      if(wanted.startsWith('over'))return total>line?'hit':'miss';
      if(wanted.startsWith('under'))return total<line?'hit':'miss';
      return 'unverifiable';
    }
    if(market==='match_total'&&line!=null){
      const total=num(r.total_games) ?? (Array.isArray(r.sets)?r.sets.reduce((a,z)=>a+Number(z?.[0]||0)+Number(z?.[1]||0),0):null);
      if(total==null)return 'unverifiable';
      if(wanted.startsWith('over'))return total>line?'hit':'miss';
      if(wanted.startsWith('under'))return total<line?'hit':'miss';
      return 'unverifiable';
    }
    if(market==='total_sets'){
      const expected=parseInt(pick,10), actual=num(r.number_of_sets)??r.sets?.length;
      return Number.isFinite(expected)&&actual!=null?(Number(actual)===expected?'hit':'miss'):'unverifiable';
    }
    return existing||'unverifiable';
  }

window.TENIS_AI_SETTLEMENT_REFERENCE={marketOutcome};
})();
