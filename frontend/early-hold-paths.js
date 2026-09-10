/* Tenis AI v8.8.16 — Hold Paths + event-driven player/match scope */
(() => {
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
  const pc=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
  const safeAll=()=>{try{return Array.isArray(all)?all:[]}catch{return []}};

  function findMatch(p1,p2){
    const a=norm(p1),b=norm(p2);
    return safeAll().find(m=>
      (norm(m.p1)===a&&norm(m.p2)===b) ||
      (norm(m.p1)===b&&norm(m.p2)===a)
    )||null;
  }

  function fallbackBreakdown(m,games){
    const e=m?.early_hold_v7||{};
    const total=num(m?.game_states?.[String(games)]?.[`${games/2}:${games/2}`]);
    const a=(e.p1_service_holds||[]).map(x=>num(x)/100);
    const b=(e.p2_service_holds||[]).map(x=>num(x)/100);
    const k=games/2;
    if(total==null||a.length<k||b.length<k||[...a.slice(0,k),...b.slice(0,k)].some(x=>!Number.isFinite(x)))return null;
    const clean=[...a.slice(0,k),...b.slice(0,k)].reduce((z,x)=>z*x,1)*100;
    const withBreaks=Math.max(0,total-clean);
    return {
      games,
      state:`${k}:${k}`,
      total:Math.round(total*10)/10,
      clean_holds:Math.round(clean*10)/10,
      with_breaks:Math.round(withBreaks*10)/10,
      break_break:games===2?Math.round(withBreaks*10)/10:null
    };
  }

  function breakdown(m,games){
    const x=m?.early_hold_v7?.checkpoint_breakdown?.[String(games)];
    if(x){
      return {
        games,
        state:x.state||`${games/2}:${games/2}`,
        total:num(x.total),
        clean_holds:num(x.clean_holds),
        with_breaks:num(x.with_breaks),
        break_break:num(x.break_break)
      };
    }
    return fallbackBreakdown(m,games);
  }

window.TENIS_AI_HOLD_PATHS={breakdown,fallbackBreakdown};
})();
