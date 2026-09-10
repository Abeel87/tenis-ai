/* Existing descriptive profile calculations, unchanged. */
(()=>{
  const STORE='tenis-ai-v76-player-pro-ui';
  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
  const same=(a,b)=>norm(a)===norm(b);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
  const clamp=(x,a=0,b=100)=>Math.max(a,Math.min(b,Number(x)));
  const scoreRange=(x,lo,hi)=>num(x)==null?null:clamp((Number(x)-lo)/(hi-lo)*100);
  const weighted=(pairs)=>{
    const ok=pairs.filter(([v,w])=>num(v)!=null&&w>0);
    if(!ok.length)return null;
    const z=ok.reduce((s,[,w])=>s+w,0);
    return ok.reduce((s,[v,w])=>s+Number(v)*w,0)/z;
  };
  const fmt=x=>num(x)==null?'N/D':`${Math.round(Number(x))}`;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const pp=x=>num(x)==null?'—':`${Number(x)>=0?'+':''}${Number(x).toFixed(1)} pp`;
  const safeAll=()=>{try{return Array.isArray(all)?all:[]}catch{return []}};

  function state(){
    try{return {...{window:'10',scope:'all'},...(JSON.parse(localStorage.getItem(STORE))||{})}}catch{return {window:'10',scope:'all'}}
  }
  function save(x){try{localStorage.setItem(STORE,JSON.stringify(x))}catch{}}

  function dataFor(name){
    const rows=safeAll().filter(m=>same(m.p1,name)||same(m.p2,name));
    const m=rows.find(x=>x.tendencies_v71||x.early_hold_v7||x.serve_props_v72)||rows[0];
    if(!m)return null;
    const side=same(m.p1,name)?'p1':'p2';
    return {
      m,side,
      stats:m[`${side}_stats`]||null,
      trends:m.tendencies_v71?.[side]||null,
      early:m.early_hold_v7?.[side]||null,
      serve:m.serve_props_v72?.[side]||null,
      surface:String(m.surface||'').toLowerCase()
    };
  }

  const metric=(block,key)=>block?.metrics?.[key]?.pct ?? null;
  const av=(block,key)=>block?.averages?.[key] ?? null;

  function indexes(d,ui){
    const g=d?.trends?.[ui.scope]?.[ui.window]||null;
    const surf=d?.trends?.surface?.[ui.window]||null;
    const p=d?.early?.pbp_tendencies?.[ui.scope]?.[ui.window]||null;
    const ps=d?.early?.pbp_tendencies?.surface?.[ui.window]||null;

    const serve=weighted([
      [scoreRange(av(g,'hold_rate'),60,90),.38],
      [scoreRange(av(g,'serve_points_won'),50,72),.25],
      [scoreRange(av(g,'first_serve_won'),55,85),.20],
      [scoreRange(av(g,'second_serve_won'),35,65),.17]
    ]);
    const ret=weighted([
      [scoreRange(av(g,'break_rate'),10,45),.46],
      [scoreRange(av(g,'return_points_won'),28,52),.54]
    ]);
    const form=weighted([
      [metric(g,'match_win'),.45],
      [metric(g,'set1_win'),.32],
      [metric(g,'set2_win'),.23]
    ]);
    const early=Number(p?.sample_matches||0)>=3?weighted([
      [metric(p,'hold1'),.42],
      [metric(p,'hold2'),.32],
      [metric(p,'hold3'),.18],
      [metric(p,'sequence_11_22_33'),.08]
    ]):null;
    const mental=weighted([
      [metric(g,'closeout_after_set1_win'),.32],
      [metric(g,'comeback_set2_after_set1_loss'),.32],
      [metric(g,'deciding_set_win'),.26],
      [metric(g,'set2_win'),.10]
    ]);
    const surface=Number(surf?.sample_matches||0)>=3?weighted([
      [metric(surf,'match_win'),.40],
      [scoreRange(av(surf,'hold_rate'),60,90),.25],
      [scoreRange(av(surf,'return_points_won'),28,52),.20],
      [metric(surf,'set1_win'),.15]
    ]):null;

    return {serve,ret,form,early,mental,surface,g,p,surf,ps};
  }

window.TENIS_AI_PLAYER_ANALYTICS={indexes,dataFor};
})();
