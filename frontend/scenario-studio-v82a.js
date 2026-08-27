/* Tenis AI v8.2A — Scenariusze AI Core
   One controller, one renderer, zero MutationObserver / setInterval.
   Uses existing match/model data; does not change model calculations.
*/
(() => {
  'use strict';

  const VERSION='v8.2A-core';
  const DRAFT_KEY='tenis-ai-v82a-scenario-draft';
  const LOCAL_KEY='tenis-ai-v82a-scenarios-local';
  const MAX_MATCHES=8, MAX_PER_MATCH=4;
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const clamp=(x,a=0,b=100)=>Math.max(a,Math.min(b,Number(x)||0));
  const matchKey=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));
  const todayKey=()=>new Date().toLocaleDateString('en-CA');
  const nowIso=()=>new Date().toISOString();

  let draft=loadDraft();
  let panel=null, dock=null, navButton=null;
  let currentTab='home';
  let manualCategory='all';
  let manualMatchFilter=null;
  let lineEditorKey=null;

  function loadDraft(){
    try{
      const x=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');
      if(x&&Array.isArray(x.items))return x;
    }catch{}
    return {id:null,created_at:nowIso(),mode:'manual',profile:'manual',items:[]};
  }
  function persistDraft(){
    try{localStorage.setItem(DRAFT_KEY,JSON.stringify(draft))}catch{}
    updateDock();
  }
  function clearDraft(){
    draft={id:null,created_at:nowIso(),mode:'manual',profile:'manual',items:[]};
    persistDraft();
  }
  function allMatches(){
    try{
      // v8.2A.2: to samo źródło meczów co ekran główny.
      // Globalne `let all` nie musi istnieć jako window.all.
      if(typeof filteredReady==='function'){
        const rows=filteredReady();
        if(Array.isArray(rows))return rows.filter(Boolean);
      }
      if(typeof all!=='undefined'&&Array.isArray(all))return all.filter(Boolean);
      if(Array.isArray(window.all))return window.all.filter(Boolean);
      return [];
    }catch{return []}
  }
  function isToday(m){
    const d=new Date(m?.scheduled_time||'');
    return Number.isFinite(d.getTime())&&d.toLocaleDateString('en-CA')===todayKey();
  }
  function isFinished(m){
    const s=String(m?.event_status||m?.feed_status||m?.status||'').toLowerCase();
    return /finish|complete|ended|retired|walkover/.test(s);
  }
  function todaysMatches(){
    return allMatches().filter(m=>isToday(m)&&!isFinished(m))
      .sort((a,b)=>new Date(a.scheduled_time||0)-new Date(b.scheduled_time||0));
  }
  function modelApi(){return window.TENIS_AI_MODEL_API||null}
  function activeModelName(){
    try{return modelApi()?.activeName?.()||'Model AI'}catch{return 'Model AI'}
  }
  function signalRows(m){
    let rows=[];
    try{rows=modelApi()?.allSignals?.(m)||[]}catch{}
    if(!rows.length){
      const pushObj=(market,label,obj)=>{
        const e=Object.entries(obj||{}).filter(([,v])=>num(v)!=null).sort((a,b)=>Number(b[1])-Number(a[1]))[0];
        if(e)rows.push({market,key:`${market}|${e[0]}`,label:`${label}: ${e[0]}`,pick:e[0],v:Number(e[1])});
      };
      pushObj('match_win','Mecz',m.match_win);
      pushObj('set1_win','1. set',m.first_set_win);
      Object.entries(m.over_under||{}).forEach(([line,v])=>{
        const o=num(v?.over),u=num(v?.under);if(o==null||u==null)return;
        const pick=o>=u?'over':'under';
        rows.push({market:'set1_total',key:`set1_total|${line}|${pick}`,label:`1S ${pick==='over'?'O':'U'}${line}`,pick,v:Math.max(o,u)});
      });
      Object.entries(m.match_over_under||{}).forEach(([line,v])=>{
        const o=num(v?.over),u=num(v?.under);if(o==null||u==null)return;
        const pick=o>=u?'over':'under';
        rows.push({market:'match_total',key:`match_total|${line}|${pick}`,label:`Mecz ${pick==='over'?'O':'U'}${line}`,pick,v:Math.max(o,u)});
      });
    }
    const seen=new Set();
    return rows.map(x=>({
      key:String(x.key||`${x.market}|${x.pick}|${x.label}`),
      label:String(x.label||x.key||'Sygnał'),
      value:clamp(num(x.v)??num(x.value)??0),
      market:String(x.market||'other'),
      pick:x.pick??null
    })).filter(x=>x.value>=50&&!seen.has(x.key)&&seen.add(x.key))
      .sort((a,b)=>b.value-a.value);
  }
  function normalizePct(v){
    const n=num(v);
    if(n==null)return null;
    return n>=0&&n<=1?n*100:n;
  }
  function rawTotalSignals(m){
    const rows=[];
    const add=(obj,market,prefix)=>{
      Object.entries(obj||{}).forEach(([line,v])=>{
        const ln=Number(line);if(!Number.isFinite(ln))return;
        const over=normalizePct(v?.over),under=normalizePct(v?.under);
        if(over!=null)rows.push({market,key:`${market}|${line}|over`,label:`${prefix}O${line}`,pick:'over',v:over,value:over});
        if(under!=null)rows.push({market,key:`${market}|${line}|under`,label:`${prefix}U${line}`,pick:'under',v:under,value:under});
      });
    };
    add(m?.match_over_under,'match_total','M ');
    add(m?.over_under,'set1_total','1S ');
    return rows;
  }
  function scenarioSignals(m){
    const merged=new Map();
    rawTotalSignals(m).forEach(x=>merged.set(x.key,x));
    signalRows(m).forEach(x=>merged.set(x.key,x));
    return [...merged.values()].map(x=>({
      ...x,
      value:clamp(num(x.value)??num(x.v)??0)
    })).sort((a,b)=>Number(b.value||0)-Number(a.value||0));
  }
  function marketAnchorLine(m,family){
    const obj=family==='match_total'?m?.match_over_under:m?.over_under;
    let best=null;
    Object.entries(obj||{}).forEach(([line,v])=>{
      const ln=Number(line),over=normalizePct(v?.over),under=normalizePct(v?.under);
      if(!Number.isFinite(ln)||over==null||under==null)return;
      const gap=Math.abs(over-under);
      if(!best||gap<best.gap||(gap===best.gap&&ln>best.line))best={line:ln,gap};
    });
    return best?.line??null;
  }
  function totalLine(s){
    const market=String(s?.market||'').toLowerCase();
    if(market!=='match_total'&&market!=='set1_total')return null;
    const parts=String(s?.key||s?.signal_key||'').split('|');
    const line=parts.length>1?Number(parts[1]):NaN;
    return Number.isFinite(line)?line:null;
  }
  function isTotalSignal(s){
    const m=String(s?.market||'').toLowerCase();
    return m==='match_total'||m==='set1_total';
  }
  function findMatchByKey(k){
    return allMatches().find(m=>matchKey(m)===String(k))||null;
  }
  function lineAlternatives(item){
    if(!isTotalSignal(item))return [];
    const m=findMatchByKey(item.match_key);if(!m)return [];
    const side=String(item.pick||'').toLowerCase();
    return scenarioSignals(m)
      .filter(x=>String(x.market||'').toLowerCase()===String(item.market||'').toLowerCase())
      .filter(x=>String(x.pick||'').toLowerCase()===side)
      .filter(x=>totalLine(x)!=null)
      .map(x=>({...x,composer_score:composerSignalScore(m,x,draft.profile||'balanced'),line:totalLine(x)}))
      .sort((a,b)=>a.line-b.line);
  }
  function changeDraftLine(match_key,old_signal_key,new_signal_key){
    const pos=draft.items.findIndex(x=>x.match_key===match_key&&x.signal_key===old_signal_key);
    if(pos<0)return;
    const item=draft.items[pos],m=findMatchByKey(match_key);if(!m)return;
    const next=scenarioSignals(m).find(x=>x.key===new_signal_key);
    if(!next||!isTotalSignal(next))return;
    const original=Number.isFinite(Number(item.suggested_line))?Number(item.suggested_line):totalLine(item);
    const selected=totalLine(next);
    draft.items[pos]={
      ...item,
      signal_key:next.key,
      label:next.label,
      market:next.market,
      pick:next.pick,
      value:Number(next.value),
      composer_score:composerSignalScore(m,next,draft.profile||'balanced'),
      suggested_line:original,
      selected_line:selected,
      line_adjusted:selected!==original,
      line_adjusted_at:nowIso()
    };
    lineEditorKey=null;
    persistDraft();
    renderCurrent();
    toast(`Linia zmieniona na ${selected}. Ocena scenariusza przeliczona.`);
  }
  function categoryOf(s){
    const m=s.market.toLowerCase(),l=s.label.toLowerCase();
    if(m.includes('state')||/po [246]|1:1|2:2|3:3/.test(l))return 'start';
    if(m.includes('total')||/over|under|\bo\d|\bu\d|gemy/.test(l))return 'games';
    if(m.includes('win')||/wygra|1\. set|mecz:/.test(l))return 'winner';
    if(/ace|double|fault|serw/.test(l))return 'serve';
    return 'other';
  }
  function qualityBonus(m){
    const q=String(m?.quality||'').toLowerCase();
    let b=q.includes('moc')||q.includes('high')||q.includes('good')?4:q.includes('śred')||q.includes('med')?2:0;
    if(m?.early_hold_v7?.ready)b+=3;
    if(m?.joint_builder_v78b?.status==='READY')b+=2;
    return b;
  }
  function autoLearnSnapshot(m,s){
    try{
      const x=window.TENIS_AI_AUTOLEARN_V84?.scoreFor?.(m,s);
      return x&&Number.isFinite(Number(x.ensemble))?x:null;
    }catch{return null}
  }
  function generatorProfilePolicy(profile='balanced'){
    return ({
      stable:{strong:78,floor:74,minAverage:74,mlWeight:.72,mlFloor:56,legacyRescue:75},
      balanced:{strong:76,floor:72,minAverage:72,mlWeight:.76,mlFloor:55,legacyRescue:74},
      strong:{strong:84,floor:80,minAverage:80,mlWeight:.82,mlFloor:60,legacyRescue:80},
      experimental:{strong:68,floor:62,minAverage:62,mlWeight:.68,mlFloor:52,legacyRescue:70}
    })[profile]||{strong:76,floor:72,minAverage:72,mlWeight:.76,mlFloor:55,legacyRescue:74};
  }
  function autoLearnSourceLabel(ml){
    if(!ml)return activeModelName();
    const parts=[];
    const c=num(ml.catboost),t=num(ml.tabpfn),e=num(ml.current);
    if(c!=null)parts.push(`C${Math.round(c)}`);
    if(t!=null)parts.push(`T${Math.round(t)}`);
    if(e!=null)parts.push(`E${Math.round(e)}`);
    return parts.length?`Ensemble ${parts.join('/')}`:'Ensemble';
  }

  // PLAYER_INTELLIGENCE_V85_SHADOW_ONLY — telemetry/display only; never changes a score.
  function playerAssist(m,s){
    try{return window.TENIS_AI_PLAYER_V85?.supportFor?.(m,s)||null}catch{return null}
  }
  function playerBadge(m,s){
    const p=playerAssist(m,s);
    return p?' · 🧬 SHADOW':'';
  }

  function composerSignalScore(m,s,profile='balanced'){
    let v=s.value+qualityBonus(m);
    if(profile==='stable'){
      if(['start','games'].includes(categoryOf(s)))v+=2;
      if(s.value<74)v-=8;
    }else if(profile==='strong'){
      if(s.value>=82)v+=4;
      else v-=4;
    }else if(profile==='experimental'){
      if(categoryOf(s)==='other')v+=3;
    }
    const legacy=clamp(v);
    if(profile==='manual')return legacy;
    const ml=autoLearnSnapshot(m,s);
    if(!ml||String(ml.status||'ACTIVE').toUpperCase()!=='ACTIVE')return legacy;
    const ensemble=num(ml.adaptive_prod_score??ml.final_score??ml.ensemble);
    if(ensemble==null)return legacy;
    const p=generatorProfilePolicy(profile);
    const votes=[num(ml.current),num(ml.catboost),num(ml.tabpfn)].filter(x=>x!=null);
    const hi=votes.length?Math.max(...votes):ensemble;
    const lo=votes.length?Math.min(...votes):ensemble;
    const agree=votes.filter(x=>x>=65).length;
    let score=ensemble*p.mlWeight+legacy*(1-p.mlWeight);
    if(agree>=2)score+=1.2;
    if(votes.length>=3&&hi-lo<=8)score+=.8;
    if(hi-lo>=18)score-=2.0;
    if(profile==='stable'&&['start','games'].includes(categoryOf(s)))score+=1;
    if(ensemble<p.mlFloor&&legacy<p.legacyRescue)score=Math.min(score,p.floor-.5);
    // Player Intelligence remains strictly SHADOW. Its payload is available for
    // diagnostics and badges, but it cannot alter the Generator or Ensemble score.
    return clamp(score);
  }
  function generatorFamily(s){
    const market=String(s?.market||'other').toLowerCase();
    if(market==='game_state'||market.startsWith('state')){
      const parts=String(s?.key||s?.signal_key||'').split('|');
      const cp=parts.find(x=>['2','4','6'].includes(String(x)))||market;
      return `state:${cp}`;
    }
    return market;
  }
  function generatorTotalMarketable(m,s){
    if(!isTotalSignal(s))return true;
    const line=totalLine(s);
    if(line==null)return false;
    const market=String(s.market||'').toLowerCase();
    const minimum=market==='match_total'?19.5:8.5;
    if(line<minimum)return false;
    const anchor=marketAnchorLine(m,market);
    if(anchor==null)return true;
    const lines=[...new Set(
      scenarioSignals(m)
        .filter(x=>String(x.market||'').toLowerCase()===market)
        .map(totalLine).filter(x=>x!=null&&x>=minimum)
    )].sort((a,b)=>a-b);
    if(!lines.length)return false;
    const idx=lines.findIndex(x=>Math.abs(x-line)<.001);
    let center=0,best=Infinity;
    lines.forEach((x,i)=>{const d=Math.abs(x-anchor);if(d<best){best=d;center=i}});
    return idx>=0&&Math.abs(idx-center)<=1;
  }
  function repairGeneratorCandidate(x,spm,profile){
    if(
      x?.pair_type &&
      Array.isArray(x?.picked) &&
      x.picked.length===spm &&
      Number(x?.selectionScore)>0
    ){
      const cfg=selectorPolicy(profile);
      const floor=Number(x?.pair_floor_used??cfg.softPairFloor??cfg.pairFloor??60);
      if(Number(x.selectionScore)>=floor){
        return {
          ...x,
          avg:Number(x.selectionScore),
          avgScore:Number(x.selectionScore),
          score:Number(x.selectionScore),
          composer_score:Number(x.selectionScore),
          pair_preserved:true
        };
      }
    }

    const m=x?.m||x?.match||x?.fixture||x?.row||findMatchByKey(x?.match_key);
    if(!m)return x;
    const policy=generatorProfilePolicy(profile);
    const unwrap=v=>v?.s||v?.signal||v;
    const score=s=>composerSignalScore(m,s,profile);
    const preference=s=>{
      const c=categoryOf(s);
      if(profile==='stable')return ['games','start'].includes(c)?2:0;
      if(profile==='experimental')return c==='other'?1:0;
      return 0;
    };
    const pool=scenarioSignals(m)
      .filter(generatorTotalMarketable.bind(null,m))
      .map(s=>({s,score:score(s),pref:preference(s)}))
      .filter(x=>x.score>=policy.floor)
      .sort((a,b)=>(Number(b.score>=policy.strong)-Number(a.score>=policy.strong))||b.pref-a.pref||b.score-a.score);

    const chosen=[],families=new Set(),keys=new Set();
    const push=s=>{
      if(!s||keys.has(String(s.key)))return false;
      if(!generatorTotalMarketable(m,s))return false;
      const sc=score(s);
      if(sc<policy.floor)return false;
      const fam=generatorFamily(s);
      if(families.has(fam))return false;
      chosen.push({s,score:sc});
      keys.add(String(s.key));
      families.add(fam);
      return true;
    };

    (Array.isArray(x?.picked)?x.picked:[])
      .map(unwrap).sort((a,b)=>score(b)-score(a))
      .forEach(s=>{if(chosen.length<spm)push(s)});
    for(const row of pool){
      if(chosen.length>=spm)break;
      push(row.s);
    }

    if(chosen.length!==spm)return {...x,picked:[]};
    const avg=chosen.reduce((a,z)=>a+z.score,0)/chosen.length;
    if(avg<policy.minAverage)return {...x,picked:[]};
    return {
      ...x,
      picked:chosen.map(z=>z.s),
      avg,avgScore:avg,score:avg,composer_score:avg,
      soft_filled:Math.max(0,chosen.length-(Array.isArray(x?.picked)?x.picked.length:0))
    };
  }
  function draftMatches(){
    const map=new Map();
    draft.items.forEach(i=>{
      if(!map.has(i.match_key))map.set(i.match_key,{match_key:i.match_key,p1:i.p1,p2:i.p2,signals:[]});
      map.get(i.match_key).signals.push(i);
    });
    return [...map.values()];
  }
  function scoreDraft(){
    if(!draft.items.length)return 0;
    const avg=draft.items.reduce((s,x)=>s+Number(x.composer_score||x.value||0),0)/draft.items.length;
    let penalty=0;
    for(const g of draftMatches()){
      const marketCounts={};
      g.signals.forEach(x=>marketCounts[x.market]=(marketCounts[x.market]||0)+1);
      penalty+=Object.values(marketCounts).reduce((s,n)=>s+Math.max(0,n-1)*1.5,0);
    }
    penalty+=Math.max(0,draft.items.length-draftMatches().length)*.35;
    return clamp(avg-penalty);
  }
  function ratingLabel(v){return v>=84?'BARDZO MOCNY':v>=76?'MOCNY':v>=68?'UMIARKOWANY':'RYZYKOWNY'}
  function selected(match_key,signal_key){
    return draft.items.some(x=>x.match_key===match_key&&x.signal_key===signal_key);
  }
  function addSignal(m,s,source='manual',profile='manual'){
    const mk=matchKey(m);
    if(selected(mk,s.key)){removeSignal(mk,s.key);return}
    const groups=draftMatches();
    const g=groups.find(x=>x.match_key===mk);
    if(!g&&groups.length>=MAX_MATCHES){toast(`Maksymalnie ${MAX_MATCHES} spotkań.`);return}
    if(g&&g.signals.length>=MAX_PER_MATCH){toast(`Maksymalnie ${MAX_PER_MATCH} sygnały na spotkanie.`);return}
    draft.mode=source==='generator'?'generator':'manual';
    draft.profile=profile||draft.profile||'manual';
    draft.items.push({
      match_key:mk,
      match_id:m?.id??m?.match_id??null,
      p1:m?.p1||'',
      p2:m?.p2||'',
      scheduled_time:m?.scheduled_time||null,
      tournament:m?.tournament||null,
      surface:m?.surface||null,
      signal_key:s.key,
      suggested_line:totalLine(s),
      selected_line:totalLine(s),
      market_anchor_line:s.market_anchor_line??marketAnchorLine(m,s.market),
      marketability_guard:!!s.marketability_guard,
      label:s.label,
      market:s.market,
      pick:s.pick,
      value:Number(s.value),
      composer_score:composerSignalScore(m,s,profile),
      source_model:(modelApi()?.active||'adaptive'),
      source,
      quality:m?.quality||null,
      pbp_ready:!!m?.early_hold_v7?.ready,
      joint_ready:m?.joint_builder_v78b?.status==='READY',
      added_at:nowIso()
    });
    persistDraft();renderCurrent();
  }
  function removeSignal(mk,sk){
    draft.items=draft.items.filter(x=>!(x.match_key===mk&&x.signal_key===sk));
    persistDraft();renderCurrent();
  }
  function currentUserClient(){
    const candidates=[window.tenisSupabase,window.supabaseClient,window.sb,window.supabase];
    return candidates.find(x=>x&&typeof x.from==='function'&&x.auth&&typeof x.auth.getUser==='function')||null;
  }
  async function saveScenario(){
    if(!draft.items.length){toast('Najpierw dodaj sygnały.');return}
    const groups=draftMatches();
    const payload={
      scenario_date:todayKey(),
      title:`Scenariusz ${new Date().toLocaleString('pl-PL',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}`,
      mode:draft.mode||'manual',
      profile:draft.profile||'manual',
      status:'active',
      match_count:groups.length,
      signal_count:draft.items.length,
      composer_score:Number(scoreDraft().toFixed(2)),
      calibrated_probability:null,
      items:draft.items,
      metadata:{active_model:activeModelName(),saved_from:'web',app_feature:VERSION},
      composer_version:VERSION
    };
    const client=currentUserClient();
    if(client){
      try{
        const {data:{user}}=await client.auth.getUser();
        if(user?.id){
          const {error}=await client.from('ai_scenarios').insert({...payload,user_id:user.id});
          if(!error){saveLocal({...payload,id:`remote-${Date.now()}`,remote:true});clearDraft();currentTab='saved';render();toast('Scenariusz zapisany na profilu.');return}
          console.warn('Scenario Supabase insert:',error);
        }
      }catch(e){console.warn(e)}
    }
    saveLocal({...payload,id:`local-${Date.now()}`,remote:false});
    clearDraft();currentTab='saved';render();
    toast('Zapisano lokalnie. Po zalogowaniu synchronizacja trafi na profil.');
  }
  function saveLocal(x){
    try{
      const a=JSON.parse(localStorage.getItem(LOCAL_KEY)||'[]');
      a.unshift(x);localStorage.setItem(LOCAL_KEY,JSON.stringify(a.slice(0,100)));
    }catch{}
  }
  function localSaved(){try{return JSON.parse(localStorage.getItem(LOCAL_KEY)||'[]')}catch{return []}}
  async function remoteSaved(){
    const client=currentUserClient();if(!client)return [];
    try{
      const {data:{user}}=await client.auth.getUser();if(!user?.id)return [];
      const {data,error}=await client.from('ai_scenarios').select('*').eq('user_id',user.id).order('created_at',{ascending:false}).limit(50);
      return error?[]:(data||[]);
    }catch{return []}
  }

  function ensureShell(){
    if(panel)return;
    panel=document.createElement('section');
    panel.id='scenario-v82a-panel';
    panel.className='scenario-v82a-panel';
    panel.hidden=true;
    panel.innerHTML='<div class="sc82-shell"><header class="sc82-head"><div><b>🧩 Scenariusze AI</b><span>analiza · wybór · zapis · nauka</span></div><button data-sc-close aria-label="Zamknij">✕</button></header><div class="sc82-body"></div></div>';
    document.body.appendChild(panel);
    panel.addEventListener('click',handlePanelClick);
    dock=document.createElement('button');
    dock.id='scenario-v82a-dock';dock.className='scenario-v82a-dock';dock.hidden=true;
    dock.addEventListener('click',()=>{open('draft')});
    document.body.appendChild(dock);
    updateDock();
  }
  function mountNav(){
    ensureShell();
    if(navButton?.isConnected)return true;
    // v8.2A.1: canonical visible navigation is rendered by ui-v751.js.
    // Never inject Scenarios into the legacy hidden .main-tabs.
    navButton=$('#p751-bottom-nav [data-p751-nav="scenarios"]');
    return !!navButton;
  }
  function mountRetries(){
    if(mountNav())return;
    [250,700,1500,3000].forEach(ms=>setTimeout(mountNav,ms));
  }
  function open(tab='home',matchFilter=null){
    ensureShell();mountNav();
    currentTab=tab;manualMatchFilter=matchFilter||null;
    panel.hidden=false;document.documentElement.classList.add('sc82-open');
    render();
  }
  function close(){
    if(!panel)return;panel.hidden=true;document.documentElement.classList.remove('sc82-open');
  }
  function render(){
    if(!panel)return;
    const body=$('.sc82-body',panel);
    if(currentTab==='manual')body.innerHTML=manualHtml();
    else if(currentTab==='generator')body.innerHTML=generatorHtml();
    else if(currentTab==='draft')body.innerHTML=draftHtml();
    else if(currentTab==='saved'){body.innerHTML='<div class="sc82-loading">Ładowanie…</div>';renderSavedAsync(body)}
    else body.innerHTML=homeHtml();
  }
  function renderCurrent(){if(panel&&!panel.hidden)render()}
  function homeHtml(){
    const count=draft.items.length,score=scoreDraft();
    return `<div class="sc82-hero"><span>SCENARIO COMPOSER</span><h2>Zbuduj analizę dzisiejszych spotkań</h2><p>Generator albo własny wybór. Bez stawek i bez „kuponów” — tylko sygnały modeli, jakość danych i późniejsze rozliczenie.</p></div>
    <div class="sc82-home-grid">
      <button data-sc-go="generator"><b>⚡ Generator AI</b><span>1–8 spotkań · 1–4 sygnały na mecz</span></button>
      <button data-sc-go="manual"><b>✍️ Własny scenariusz</b><span>Wybieraj sygnały jak z listy rynków</span></button>
      <button data-sc-go="saved"><b>📚 Moje scenariusze</b><span>Zapisane analizy i historia</span></button>
      ${count?`<button data-sc-go="draft"><b>🧩 Otwarty scenariusz</b><span>${draftMatches().length} spotk. · ${count} sygnałów · ${Math.round(score)}/100</span></button>`:''}
    </div>
    <div class="sc82-note"><b>v8.2A CORE</b><span>Ocena /100 jest wynikiem Composera, nie gwarancją ani skalibrowanym prawdopodobieństwem.</span></div>`;
  }
  function generatorHtml(){
    return `${topBack('Generator AI')}
    <div class="sc82-builder">
      <label><span>Ile spotkań?</span><div class="sc82-choice" data-sc-choice="matches">${[1,2,3,4,5,6,7,8].map(n=>`<button class="${n===7?'active':''}" data-sc-n="${n}">${n}</button>`).join('')}</div></label>
      <label><span>Sygnałów na spotkanie?</span><div class="sc82-choice" data-sc-choice="signals">${[1,2,3,4].map(n=>`<button class="${n===2?'active':''}" data-sc-n="${n}">${n}</button>`).join('')}</div></label>
      <label><span>Styl scenariusza</span><div class="sc82-profiles">
        <button class="active" data-sc-profile="balanced">🎯 Bet Builder CORE</button>
        <button data-sc-profile="stable">🛡️ Stabilny CORE</button>
        <button data-sc-profile="strong">🔥 Najmocniejsze pary</button>
        <button data-sc-profile="experimental">🧪 Model Test / SHADOW</button>
      </div></label>
      <button class="sc82-primary" data-sc-generate>🧩 GENERUJ SCENARIUSZ</button>
      <p class="sc82-small"><b>Pair Selector:</b> najpierw wybiera 2 pasujace do siebie zdarzenia w meczu, dopiero potem porownuje spotkania. CORE preferuje spojny Bet Builder; Model Test sprawdza alternatywne modele i SHADOW.</p>
    </div>`;
  }

  // ==========================================================
  // v8.8.1 BET BUILDER PAIR SELECTOR
  // v8.8.2 GENERATOR RELATIVE RANKING
  // Najpierw dobra PARA zdarzen -> potem ranking meczu.
  // ==========================================================

  function selectorNorm(v){
    return String(v??'')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g,'')
      .toLowerCase()
      .replace(/\s+/g,' ')
      .trim();
  }

  function selectorSide(m,s){
    const p=selectorNorm(s?.pick);

    if(
      p==='p1' ||
      p==='player1' ||
      p===selectorNorm(m?.p1)
    )return 'p1';

    if(
      p==='p2' ||
      p==='player2' ||
      p===selectorNorm(m?.p2)
    )return 'p2';

    return null;
  }

  function selectorPolicy(profile='balanced'){
    return ({
      stable:{
        pairFloor:80,
        softPairFloor:64,
        signalFloor:58,
        setTarget:8.5,
        matchTarget:21.0,
        shadow:false
      },

      balanced:{
        pairFloor:76,
        softPairFloor:60,
        signalFloor:54,
        setTarget:8.5,
        matchTarget:21.0,
        shadow:false
      },

      strong:{
        pairFloor:84,
        softPairFloor:68,
        signalFloor:60,
        setTarget:8.5,
        matchTarget:21.0,
        shadow:false
      },

      experimental:{
        pairFloor:69,
        softPairFloor:55,
        signalFloor:50,
        setTarget:9.5,
        matchTarget:21.0,
        shadow:true
      }
    })[profile]||{
      pairFloor:76,
      softPairFloor:60,
      signalFloor:54,
      setTarget:8.5,
      matchTarget:21.0,
      shadow:false
    };
  }

  function selectorModelEvidence(m,s,profile){
    const ml=autoLearnSnapshot(m,s);

    let performancePrior=null;
    try{
      performancePrior=window.TENIS_AI_PERFORMANCE_V882?.priorFor?.(m,s)||null;
    }catch{}

    if(!ml)return {
      bonus:Number(performancePrior?.adjustment||0),
      spread:null,
      strongVotes:0,
      severe:false,
      shadow:false,
      performancePrior
    };

    const current=num(ml.current);
    const cat=num(ml.catboost);
    const tab=num(ml.tabpfn);
    const ensemble=num(
      ml.adaptive_prod_score ??
      ml.final_score ??
      ml.ensemble
    );

    const votes=[current,cat,tab].filter(x=>x!=null);
    const hi=votes.length?Math.max(...votes):null;
    const lo=votes.length?Math.min(...votes):null;
    const spread=hi!=null&&lo!=null?hi-lo:null;

    const strongVotes=votes.filter(x=>x>=65).length;

    let bonus=0;

    // Produkcyjny CORE: zgoda Current / Cat / TabPFN.
    if(profile!=='experimental'){
      if(strongVotes===3)bonus+=3.2;
      else if(strongVotes===2)bonus+=2.2;
      else if(strongVotes===1)bonus+=0.4;

      if(votes.length>=3&&spread<=8)bonus+=1.5;
      else if(votes.length>=3&&spread<=12)bonus+=0.7;

      if(spread!=null&&spread>=18)bonus-=2.5;
      if(spread!=null&&spread>=25)bonus-=3.5;

      if(ensemble!=null&&ensemble>=80)bonus+=1.8;
      else if(ensemble!=null&&ensemble>=72)bonus+=0.8;
    }

    // MODEL TEST:
    // alternatywna selekcja oparta mocniej o CatBoost + TabPFN.
    // Player Intelligence jest uzywany TYLKO tutaj jako SHADOW evidence.
    if(profile==='experimental'){
      if(cat!=null&&tab!=null){
        if(cat>=65&&tab>=65)bonus+=3.5;
        else if(cat>=60&&tab>=60)bonus+=2.0;

        if(Math.abs(cat-tab)<=8)bonus+=1.5;
        else if(Math.abs(cat-tab)>=18)bonus-=1.5;
      }

      const pi=playerAssist(m,s);
      const shadow=num(
        pi?.shadow_score ??
        pi?.support_score ??
        pi?.probability
      );

      if(shadow!=null){
        if(shadow>=75)bonus+=2.2;
        else if(shadow>=65)bonus+=1.2;
        else if(shadow<50)bonus-=1.2;
      }

      if(m?.market_lab_v741)bonus+=0.4;
    }

    const prod=ml?.adaptive_prod_v79||{};

    const hist=num(
      prod?.historical_accuracy ??
      ml?.historical_accuracy
    );

    const similar=num(
      prod?.similar_n ??
      ml?.similar_n
    );

    if(hist!=null&&similar!=null&&similar>=10){
      if(hist>=70)bonus+=1.5;
      else if(hist>=62)bonus+=0.7;
      else if(hist<50)bonus-=1.5;
    }

    if(performancePrior?.n>=10){
      bonus+=Number(performancePrior.adjustment||0);
    }

    return {
      bonus,
      spread,
      strongVotes,
      severe:spread!=null&&spread>=25,
      shadow:profile==='experimental',
      performancePrior
    };
  }

  function selectorPreferredTotalRows(m,rows,profile,min){
    const policy=selectorPolicy(profile);
    const out=[];

    for(const family of ['set1_total','match_total']){
      const target=family==='set1_total'
        ?policy.setTarget
        :policy.matchTarget;

      // TYLKO istniejace linie.
      // Nie tworzymy 20.5 / 21.5 / 8.5 z powietrza.
      const candidates=rows
        .filter(x=>String(x?.market||'').toLowerCase()===family)
        .filter(x=>String(x?.pick||'').toLowerCase()==='over')
        .filter(x=>totalLine(x)!=null)
        .filter(x=>x.cs>=min)
        .filter(x=>Math.abs(totalLine(x)-target)<=2.01)
        .sort((a,b)=>{
          const da=Math.abs(totalLine(a)-target);
          const db=Math.abs(totalLine(b)-target);

          return da-db||b.cs-a.cs;
        });

      if(candidates.length){
        out.push({
          ...candidates[0],
          selector_preferred_line:true,
          selector_target_line:target
        });
      }
    }

    return out;
  }

  function selectorPairKind(m,a,b,profile){
    const am=String(a?.market||'').toLowerCase();
    const bm=String(b?.market||'').toLowerCase();

    const ac=categoryOf(a);
    const bc=categoryOf(b);

    const pair=(x,y)=>
      (am===x&&bm===y)||(am===y&&bm===x);

    const get=(market)=>
      am===market?a:
      bm===market?b:
      null;

    // Najczestszy schemat z naszego kuponu:
    // zwyciezca 1 seta + OVER gemow 1 seta.
    if(pair('set1_win','set1_total')){
      const total=get('set1_total');

      if(String(total?.pick||'').toLowerCase()==='over'){
        return {
          type:'SET1_WIN_OVER',
          bonus:profile==='experimental'?5.0:8.0,
          reason:'1S winner + 1S over'
        };
      }

      return {
        type:'SET1_WIN_TOTAL',
        bonus:2.0,
        reason:'1S winner + 1S total'
      };
    }

    // Early Hold / Joint:
    // kierunek 1 seta + prowadzenie / checkpoint.
    if(
      (am==='set1_win'&&bc==='start') ||
      (bm==='set1_win'&&ac==='start')
    ){
      return {
        type:'EARLY_HOLD_JOINT',
        bonus:m?.joint_builder_v78b?.status==='READY'?11.0:7.0,
        reason:'1S winner + early checkpoint'
      };
    }

    // Zwyciezca meczu + zwyciezca 1 seta.
    if(pair('match_win','set1_win')){
      const mw=get('match_win');
      const sw=get('set1_win');

      const s1=selectorSide(m,mw);
      const s2=selectorSide(m,sw);

      if(s1&&s2&&s1!==s2){
        return {
          type:'WINNER_CONFLICT',
          bonus:-20,
          reason:'sprzeczni zwyciezcy'
        };
      }

      return {
        type:'MATCH_AND_SET_WIN',
        bonus:6.0,
        reason:'match winner + 1S winner'
      };
    }

    // Schemat z drugiego rodzaju kuponu:
    // OVER 1 seta + OVER calego meczu.
    if(pair('set1_total','match_total')){
      const st=get('set1_total');
      const mt=get('match_total');

      if(
        String(st?.pick||'').toLowerCase()==='over' &&
        String(mt?.pick||'').toLowerCase()==='over'
      ){
        return {
          type:'DOUBLE_TOTAL_OVER',
          bonus:profile==='experimental'?7.0:4.5,
          reason:'1S over + match over'
        };
      }
    }

    if(pair('match_win','match_total')){
      return {
        type:'MATCH_DIRECTION_TOTAL',
        bonus:2.5,
        reason:'match direction + total'
      };
    }

    if(ac!==bc){
      return {
        type:'DIVERSE_PAIR',
        bonus:1.0,
        reason:'rozne kategorie'
      };
    }

    return {
      type:'NEUTRAL_PAIR',
      bonus:0,
      reason:'neutralna para'
    };
  }

  function selectorLineBonus(s,profile){
    if(String(s?.pick||'').toLowerCase()!=='over')return 0;

    const family=String(s?.market||'').toLowerCase();
    if(family!=='set1_total'&&family!=='match_total')return 0;

    const line=totalLine(s);
    if(line==null)return 0;

    const policy=selectorPolicy(profile);

    const target=family==='set1_total'
      ?policy.setTarget
      :policy.matchTarget;

    const d=Math.abs(line-target);

    if(d<=.01)return 2.0;
    if(d<=1.01)return 1.0;

    return 0;
  }

  function selectorPairScore(m,a,b,profile){
    const policy=selectorPolicy(profile);

    const ea=selectorModelEvidence(m,a,profile);
    const eb=selectorModelEvidence(m,b,profile);
    const kind=selectorPairKind(m,a,b,profile);

    if(kind.type==='WINNER_CONFLICT'){
      return {
        score:0,
        type:kind.type,
        reason:kind.reason,
        reject:true
      };
    }

    const base=(Number(a.cs||0)+Number(b.cs||0))/2;

    let bonus=
      (ea.bonus+eb.bonus)/2 +
      kind.bonus +
      selectorLineBonus(a,profile) +
      selectorLineBonus(b,profile);

    // Jakosc danych.
    if(m?.early_hold_v7?.ready){
      if(
        kind.type==='SET1_WIN_OVER' ||
        kind.type==='EARLY_HOLD_JOINT'
      )bonus+=1.8;
      else bonus+=0.5;
    }

    if(
      m?.joint_builder_v78b?.status==='READY' &&
      kind.type==='EARLY_HOLD_JOINT'
    )bonus+=2.5;

    const quality=String(m?.quality||'').toLowerCase();
    if(
      quality.includes('high') ||
      quality.includes('good') ||
      quality.includes('moc')
    )bonus+=1.0;

    // Przy duzym konflikcie modeli nie bierzemy spotkania tylko dlatego,
    // ze jeden model pokazal bardzo wysoki procent.
    if(profile!=='experimental'){
      if(ea.severe)bonus-=4;
      if(eb.severe)bonus-=4;
    }

    const score=clamp(base+bonus);

    return {
      score,
      type:kind.type,
      reason:kind.reason,
      reject:false,
      evidenceA:ea,
      evidenceB:eb
    };
  }

  function selectorBestPair(m,sig,profile,marketFamily,runFloor=null){
    const policy=selectorPolicy(profile);
    const floor=Number.isFinite(Number(runFloor))
      ?Number(runFloor)
      :Number(policy.softPairFloor||policy.pairFloor||60);

    let best=null;

    for(let i=0;i<sig.length;i++){
      for(let j=i+1;j<sig.length;j++){
        const a=sig[i],b=sig[j];

        if(marketFamily(a)===marketFamily(b))continue;

        const result=selectorPairScore(m,a,b,profile);

        if(result.reject||result.score<floor)continue;

        if(!best||result.score>best.score){
          best={
            ...result,
            signals:[a,b]
          };
        }
      }
    }

    return best&&best.score>=floor
      ?{...best,floor_used:floor}
      :null;
  }

  function selectorMatchScore(m,picked,profile,bestPair){
    if(!picked.length)return 0;

    const avg=picked.reduce(
      (sum,x)=>sum+Number(x.cs||composerSignalScore(m,x,profile)||0),
      0
    )/picked.length;

    if(picked.length===2&&bestPair){
      return clamp(bestPair.score);
    }

    if(bestPair){
      return clamp(bestPair.score*.72+avg*.28);
    }

    return clamp(avg);
  }

  function generateFromUi(){
    const mc=Number($('.sc82-choice[data-sc-choice="matches"] .active',panel)?.dataset.scN||7);
    const spm=Number($('.sc82-choice[data-sc-choice="signals"] .active',panel)?.dataset.scN||2);
    const profile=$('.sc82-profiles .active',panel)?.dataset.scProfile||'balanced';
    const selectorCfg=selectorPolicy(profile);

    // 7/8 spotkan = ranking wzgledny. Nie wymagamy 7 par z identycznym,
    // bardzo wysokim progiem, ale nadal odrzucamy konflikty i slabe pary.
    const min=Math.max(
      50,
      Number(selectorCfg.signalFloor||54) - (mc>=7?2:mc>=5?1:0)
    );
    const runPairFloor=Math.max(
      50,
      Number(selectorCfg.softPairFloor||60) - (mc>=7?4:mc>=5?2:0)
    );

    // v8.2A.4 Distinct Markets:
    // jedna rodzina rynku = maksymalnie jeden sygnał, niezależnie od linii.
    // Przykład: M O18.5 i M O19.5 to TA SAMA rodzina i nie mogą wejść razem.
    const marketFamily=x=>{
      const m=String(x?.market||'').toLowerCase();
      const k=String(x?.key||'').toLowerCase();
      const l=String(x?.label||'').toLowerCase();

      if(m==='match_total'||k.startsWith('match_total|'))return 'match_total';
      if(m==='set1_total'||k.startsWith('set1_total|'))return 'set1_total';
      if(m==='total_sets'||k.startsWith('total_sets|'))return 'total_sets';
      if(m==='match_win'||k.startsWith('match_win|'))return 'match_win';
      if(m==='set1_win'||k.startsWith('set1_win|'))return 'set1_win';
      if(m==='set2_win'||k.startsWith('set2_win|'))return 'set2_win';
      if(m==='set3_win'||k.startsWith('set3_win|'))return 'set3_win';

      // Wszystkie checkpointy 1:1 / 2:2 / 3:3 traktujemy jako jedną rodzinę
      // "początek seta", żeby generator nie układał sekwencji prawie tego samego typu.
      if(m.startsWith('state')||k.startsWith('state|'))return 'early_state';

      if(m.includes('ace')||l.includes('asy'))return 'aces';
      if(m.includes('double')||m.includes('fault')||l.includes('podwój'))return 'double_faults';

      return m||categoryOf(x)||k.split('|')[0]||'other';
    };

    // v8.2A.6 Marketability Guard:
    // Używamy pełnej drabinki z surowych prognoz, a nie tylko linii widocznych
    // w sygnale Consensus. Preferujemy linię blisko "centrum" modelu.
    const marketLineGuard=(m,rows)=>{
      const normal=rows.filter(x=>!isTotalSignal(x));
      const guarded=[];
      const targetScore={stable:78,balanced:72,strong:82,experimental:66}[profile]||72;

      for(const family of ['match_total','set1_total']){
        const practicalFloor=family==='match_total'?19.5:8.5;
        const anchor=marketAnchorLine(m,family);
        const familyRows=rows
          .filter(x=>String(x.market||'').toLowerCase()===family&&totalLine(x)!=null)
          .filter(x=>totalLine(x)>=practicalFloor);

        if(!familyRows.length)continue;

        const sideChoices=[];
        for(const side of ['over','under']){
          let sideRows=familyRows
            .filter(x=>String(x.pick||'').toLowerCase()===side)
            .filter(x=>x.cs>=min);

          if(anchor!=null){
            // Główna linia / jeden krok obok. Nie uciekamy np. z 21.5 do easy O18.5.
            sideRows=sideRows.filter(x=>Math.abs(totalLine(x)-anchor)<=1.01);
            sideRows.sort((a,b)=>{
              const da=Math.abs(totalLine(a)-anchor),db=Math.abs(totalLine(b)-anchor);
              return da-db||b.cs-a.cs;
            });
          }else{
            // Gdy brak pary over/under do wyznaczenia centrum, szukamy score
            // zbliżonego do rynkowego pasma zamiast największego procentu.
            sideRows.sort((a,b)=>Math.abs(a.cs-targetScore)-Math.abs(b.cs-targetScore)||b.cs-a.cs);
          }

          if(!sideRows.length)continue;
          const chosen=sideRows[0];
          sideChoices.push({
            ...chosen,
            marketability_guard:true,
            market_anchor_line:anchor,
            practical_floor:practicalFloor
          });
        }

        if(sideChoices.length){
          sideChoices.sort((a,b)=>{
            const da=Math.abs(a.cs-targetScore),db=Math.abs(b.cs-targetScore);
            return da-db||b.cs-a.cs;
          });
          guarded.push(sideChoices[0]);
        }
      }

      const preferred=selectorPreferredTotalRows(
        m,
        rows,
        profile,
        min
      );

      const merged=new Map();

      [...normal,...guarded,...preferred].forEach(x=>{
        const key=String(x?.key||[
          x?.market,
          totalLine(x),
          x?.pick
        ].join('|'));

        const old=merged.get(key);

        if(!old||Number(x.cs||0)>Number(old.cs||0)){
          merged.set(key,x);
        }
      });

      return [...merged.values()].sort((a,b)=>b.cs-a.cs);
    };

    const candidates=todaysMatches().map(m=>{
      const sig=marketLineGuard(
        m,
        scenarioSignals(m)
          .map(s=>({...s,cs:composerSignalScore(m,s,profile)}))
          .filter(s=>s.cs>=min)
          .sort((a,b)=>b.cs-a.cs)
      );

      const picked=[];
      const families=new Set();
      const categories=new Set();

      // PAIR-FIRST:
      // jezeli user chce >=2 zdarzenia, najpierw szukamy najlepszej
      // spojnej pary Bet Builder dla calego spotkania.
      const bestPair=spm>=2
        ?selectorBestPair(m,sig,profile,marketFamily,runPairFloor)
        :null;

      if(bestPair){
        for(const x of bestPair.signals){
          if(picked.length>=spm)break;

          const fam=marketFamily(x);
          if(families.has(fam))continue;

          const decorated={
            ...x,
            selector_pair:bestPair.type,
            selector_match_score:Number(bestPair.score.toFixed(2)),
            selector_reason:bestPair.reason,
            selector_mode:profile==='experimental'
              ?'MODEL_TEST_SHADOW'
              :'CORE_PAIR'
          };

          picked.push(decorated);
          families.add(fam);
          categories.add(categoryOf(x));
        }
      }

      // Przebieg 1: maksymalna roznorodnosc kategorii.
      // Dziala jako fill dla 3/4 zdarzen albo fallback,
      // gdy para nie wypelnila calego zestawu.
      for(const x of sig){
        if(picked.length>=spm)break;
        const fam=marketFamily(x);
        const cat=categoryOf(x);
        if(families.has(fam)||categories.has(cat))continue;
        picked.push(x);
        families.add(fam);
        categories.add(cat);
      }

      // Przebieg 2: jeśli nadal brakuje, wolno powtorzyc kategorie,
      // ale NIGDY rodzine rynku.
      for(const x of sig){
        if(picked.length>=spm)break;
        const fam=marketFamily(x);
        if(families.has(fam))continue;
        picked.push(x);
        families.add(fam);
      }

      const ms=picked.length===spm
        ? picked.reduce((a,b)=>a+b.cs,0)/picked.length
        : 0;

      const selectionScore=picked.length===spm
        ?selectorMatchScore(m,picked,profile,bestPair)
        :0;

      return {
        m,
        picked,
        ms,
        selectionScore,
        pair_type:bestPair?.type||null,
        pair_reason:bestPair?.reason||null,
        pair_floor_used:bestPair?.floor_used??runPairFloor
      };
    })
      .map(x=>repairGeneratorCandidate(x,spm,profile)).filter(x=>x.picked.length===spm)
      .sort((a,b)=>
        (b.selectionScore??b.avgScore??b.ms)-
        (a.selectionScore??a.avgScore??a.ms)
      );

    if(!candidates.length){
      toast(`AI nie znalazło dziś spotkań spełniających próg jakości dla ${spm} różnych sygnałów.`);
      return;
    }

    const ranked=candidates.slice(0,mc);
    const selectedMatches=ranked.length;

    clearDraft();
    draft.mode='generator';
    draft.profile=profile;

    for(const x of ranked){
      for(const sig of x.picked)addSignalSilent(x.m,sig,'generator',profile);
    }

    const expected=selectedMatches*spm;
    const actual=draft.items.length;
    const actualMatches=draftMatches().length;

    if(actual!==expected || actualMatches!==selectedMatches){
      clearDraft();
      toast(`Generator przerwał: oczekiwano ${selectedMatches} wybranych spotkań i ${expected} sygnałów, otrzymano ${actualMatches} spotkań i ${actual} sygnałów.`);
      return;
    }

    persistDraft();
    currentTab='draft';
    render();
    toast(selectedMatches<mc?`AI znalazło ${selectedMatches}/${mc} spotkań spełniających próg. Nie dokładam słabszych na siłę.`:`Gotowe: ${selectedMatches} × ${spm} = ${expected} różnych sygnałów.`);
  }

  function addSignalSilent(m,s,source,profile){
    const mk=matchKey(m);const ml=autoLearnSnapshot(m,s);const pi=playerAssist(m,s);const finalScore=composerSignalScore(m,s,profile);const g=draft.items.filter(x=>x.match_key===mk);if(g.length>=MAX_PER_MATCH)return;
    draft.items.push({
      match_key:mk,match_id:m?.id??m?.match_id??null,p1:m?.p1||'',p2:m?.p2||'',scheduled_time:m?.scheduled_time||null,
      tournament:m?.tournament||null,surface:m?.surface||null,signal_key:s.key,suggested_line:totalLine(s),selected_line:totalLine(s),market_anchor_line:s.market_anchor_line??marketAnchorLine(m,s.market),marketability_guard:!!s.marketability_guard,label:s.label,market:s.market,pick:s.pick,
      value:Number(s.value),composer_score:finalScore,source_model:ml?autoLearnSourceLabel(ml):(modelApi()?.active||'adaptive'),
      base_source_model:(modelApi()?.active||'adaptive'),
      ai_final_score:ml?num(ml.adaptive_prod_score??ml.final_score):null,
      raw_ensemble_score:ml?num(ml.raw_ensemble??ml.raw_ensemble_score??ml.ensemble):null,
      adaptive_prod_score:ml?num(ml.adaptive_prod_score??ml.final_score):null,
      selector_mode:s.selector_mode??(profile==='experimental'?'MODEL_TEST_SHADOW':'CORE_PAIR'),
      selector_pair:s.selector_pair??null,
      selector_match_score:s.selector_match_score??null,
      selector_reason:s.selector_reason??null,
      autolearn_v84:ml?{current:ml.current??null,catboost:ml.catboost??null,tabpfn:ml.tabpfn??null,ensemble:ml.ensemble??null,weights:ml.weights||null}:null,
      player_intelligence_v85:pi?{probability:pi.probability??null,shadow_score:pi.shadow_score??null,support_score:pi.support_score??null,quality:pi.quality??null}:null,
      source,quality:m?.quality||null,pbp_ready:!!m?.early_hold_v7?.ready,joint_ready:m?.joint_builder_v78b?.status==='READY',added_at:nowIso()
    });
  }
  function categoryTabs(){
    const tabs=[['all','Wszystko'],['start','Start seta'],['games','Gemy'],['winner','Kierunek'],['serve','Serwis'],['top','AI Top']];
    return `<div class="sc82-cats">${tabs.map(([k,l])=>`<button class="${manualCategory===k?'active':''}" data-sc-cat="${k}">${l}</button>`).join('')}</div>`;
  }
  function manualHtml(){
    let rows=todaysMatches();
    if(manualMatchFilter)rows=rows.filter(m=>matchKey(m)===manualMatchFilter);
    return `${topBack('Własny scenariusz')}<div class="sc82-manual-head"><p>Klikasz <b>＋</b>, a wybrane sygnały wpadają do paska na dole. Przy gemach wybierasz konkretną linię (np. O18.5 / O19.5). Maks. 8 spotkań i 4 sygnały na mecz.</p>${categoryTabs()}</div>
    <div class="sc82-matches">${rows.length?rows.map(manualMatchHtml).join(''):'<div class="sc82-empty">Brak dzisiejszych spotkań.</div>'}</div>`;
  }
  function manualMatchHtml(m){
    const mk=matchKey(m);let sig=scenarioSignals(m);
    if(manualCategory==='top')sig=sig.slice(0,6);
    else if(manualCategory!=='all')sig=sig.filter(s=>categoryOf(s)===manualCategory);
    const time=(()=>{const d=new Date(m?.scheduled_time||'');return Number.isFinite(d.getTime())?d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—'})();
    return `<details class="sc82-match" ${manualMatchFilter?'open':''}>
      <summary><div><b>${esc(m.p1)} <span>vs</span> ${esc(m.p2)}</b><small>${esc(m.tournament||'Turniej')} · ${esc(m.surface||'—')} · ${time}</small></div><em>${sig.length} sygnałów</em></summary>
      <div class="sc82-signals">${sig.length?sig.map(s=>{
        const on=selected(mk,s.key),cs=composerSignalScore(m,s,'manual');
        return `<button class="sc82-signal ${on?'selected':''}" data-sc-add="${encodeURIComponent(mk)}" data-sc-sig="${encodeURIComponent(s.key)}">
          <span><b>${esc(s.label)}</b><small>${esc(activeModelName())} · ${esc(categoryOf(s))}${playerBadge(m,s)}</small></span>
          <em>${Math.round(cs)}/100</em><strong>${on?'✓':'＋'}</strong>
        </button>`;
      }).join(''):'<div class="sc82-empty">Brak sygnałów w tej kategorii.</div>'}</div>
    </details>`;
  }
  function draftHtml(){
    const groups=draftMatches(),score=scoreDraft();
    return `${topBack('Mój scenariusz')}
      <section class="sc82-score"><span>Ocena realizacji</span><b>${Math.round(score)}/100</b><strong>${ratingLabel(score)}</strong><small>${groups.length} spotk. · ${draft.items.length} sygnałów</small></section>
      <div class="sc82-draft-list">${groups.length?groups.map(g=>`<article><header><b>${esc(g.p1)} <span>vs</span> ${esc(g.p2)}</b><small>${g.signals.length} sygnały</small></header>
        ${g.signals.map(s=>{
          const line=totalLine(s);
          const rowKey=`${s.match_key}::${s.signal_key}`;
          const alternatives=lineAlternatives(s);
          const showLines=line!=null&&alternatives.length>1&&lineEditorKey===rowKey;
          const original=Number.isFinite(Number(s.suggested_line))?Number(s.suggested_line):line;
          const adjusted=line!=null&&Number.isFinite(original)&&Number(line)!==Number(original);
          return `<div class="sc82-draft-entry">
            <div class="sc82-draft-row">
              <span>
                <b>${esc(s.label)}</b>
                <small>${esc(s.source_model)} · Ranking ${Math.round(Number(s.composer_score||s.value))}/100${s.adaptive_prod_score!=null?` · FINAL ${Number(s.adaptive_prod_score).toFixed(1)}/100`:''}${s.pbp_ready?' · PBP ✓':''}${adjusted?` · zmieniono z ${original}`:''}</small>
                ${line!=null&&alternatives.length>1?`<span class="sc82-line-tools"><button class="sc82-line-toggle" data-sc-line-open="${encodeURIComponent(rowKey)}">Linia ${line} · zmień</button></span>`:''}
              </span>
              <button data-sc-remove="${encodeURIComponent(s.match_key)}" data-sc-sig="${encodeURIComponent(s.signal_key)}">✕</button>
            </div>
            ${showLines?`<div class="sc82-line-options">
              ${alternatives.map(a=>`<button class="sc82-line-option ${a.key===s.signal_key?'active':''}" data-sc-line-pick="${encodeURIComponent(s.match_key)}" data-sc-old-sig="${encodeURIComponent(s.signal_key)}" data-sc-new-sig="${encodeURIComponent(a.key)}">${String(a.pick||'').toUpperCase().startsWith('O')?'O':'U'}${a.line} · ${Math.round(a.composer_score)}/100</button>`).join('')}
            </div>`:''}
          </div>`;
        }).join('')}</article>`).join(''):'<div class="sc82-empty">Jeszcze nic nie wybrano.</div>'}</div>
      ${groups.length?`<div class="sc82-actions"><button data-sc-go="manual">＋ Dodaj kolejne</button><button data-sc-clear>Wyczyść</button><button class="sc82-primary" data-sc-save>💾 ZAPISZ SCENARIUSZ</button></div>`:''}
      <div class="sc82-note"><b>Market Line Guard</b><span>Generator wybiera bardziej rynkową linię, ale nie zna oferty konkretnego operatora. Jeśli widzisz inną dostępną linię, użyj „Zmień linię” — wynik /100 przeliczy się automatycznie.</span></div>`;
  }
  async function renderSavedAsync(body){
    try{await window.TENIS_AI_SCENARIO_SETTLEMENT?.refresh?.({force:true})}catch{}
    const remote=await remoteSaved(),local=localSaved();
    const rows=[...remote,...local.filter(x=>!x.remote)].sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0));
    if(currentTab!=='saved')return;
    const pairs=window.TENIS_AI_SCENARIO_SETTLEMENT?.summarizePairs?.(rows);
    const pairSummary=pairs?`<div class="sc82-note"><b>Trafność zapisanych par: ${pairs.accuracy==null?'N/D':pairs.accuracy+'%'}</b><span>${pairs.hits} HIT · ${pairs.misses} MISS · n=${pairs.n} · ${pairs.pending} oczekujących · ${pairs.voids} VOID. Tylko dwa zdarzenia jednego meczu; HIT wymaga 2/2. Powtórzone pary liczymy raz. Dane z wczytanych zapisów, bez wersji roboczej.</span></div>`:'';
    body.innerHTML=`${topBack('Moje scenariusze')}${pairSummary}<div class="sc82-saved">${rows.length?rows.map(s=>{
      const items=Array.isArray(s.items)?s.items:[],mc=s.match_count??new Set(items.map(x=>x.match_key)).size,sc=s.signal_count??items.length,sm=s?.metadata?.settlement_v83c||{};
      const statusLabel=s.status==='settled'?'ROZLICZONY':s.status==='partial'?'CZĘŚCIOWO':s.status==='archived'?'ARCHIWUM':'AKTYWNY';
      const settleSummary=Number.isFinite(Number(sm.resolved))?` · ✅ ${Number(sm.hits||0)} · ❌ ${Number(sm.misses||0)}${Number(sm.voids||0)?` · ⚪ ${Number(sm.voids||0)}`:''}`:'';
      return `<article><header><div><b>${esc(s.title||'Scenariusz AI')}</b><small>${new Date(s.created_at||Date.now()).toLocaleString('pl-PL')}</small></div><span class="sc82-status">${esc(statusLabel)}</span></header>
      <div class="sc82-saved-score"><b>${Math.round(Number(s.composer_score||0))}/100</b><span>${mc} spotk. · ${sc} sygnałów${settleSummary}</span></div>
      <details><summary>Pokaż analizę</summary>${items.map(i=>`<div class="sc82-saved-item"><span>${esc(i.p1)} vs ${esc(i.p2)}</span><b>${esc(i.label)}</b><small>${i.result==='hit'?'✅ TRAFIONY':i.result==='miss'?'❌ NIETRAFIONY':i.result==='void'?'⚪ VOID':'⏳ OCZEKUJE'} · ${Math.round(Number(i.composer_score||i.value||0))}/100${i.actual!=null?` · wynik: ${esc(typeof i.actual==='object'?JSON.stringify(i.actual):i.actual)}`:''}</small></div>`).join('')}</details>
      <footer>${s.remote!==false?'☁️ profil':'📱 lokalnie'} · ${esc(s.mode||'manual')} · ${esc(s.profile||'manual')}</footer></article>`;
    }).join(''):'<div class="sc82-empty">Nie masz jeszcze zapisanych scenariuszy.</div>'}</div>
    <div class="sc82-note"><b>Rozliczanie wyników · v8.3C</b><span>Scenariusze rozliczają się automatycznie z danych Post‑Match: ✅/❌/VOID. Działa dla zapisów lokalnych i profilu; brak pełnego PBP jest rozliczany neutralnie zamiast zgadywania.</span></div>`;
  }
  function topBack(title){return `<div class="sc82-topbar"><button data-sc-go="home">‹</button><b>${esc(title)}</b><button data-sc-close>✕</button></div>`}
  function updateDock(){
    if(!dock)return;
    const n=draft.items.length,m=draftMatches().length;
    dock.hidden=!n||(!panel?.hidden&&currentTab==='draft');
    dock.innerHTML=n?`<span>🧩 <b>${m}</b> spotk. · <b>${n}</b> sygnałów</span><strong>${Math.round(scoreDraft())}/100 · Otwórz ›</strong>`:'';
  }
  function toast(msg){
    let t=$('#sc82-toast');if(!t){t=document.createElement('div');t.id='sc82-toast';t.className='sc82-toast';document.body.appendChild(t)}
    t.textContent=msg;t.classList.add('show');clearTimeout(t._tm);t._tm=setTimeout(()=>t.classList.remove('show'),2400);
  }
  function handlePanelClick(e){
    const go=e.target.closest('[data-sc-go]');if(go){currentTab=go.dataset.scGo;manualMatchFilter=null;lineEditorKey=null;render();return}
    if(e.target.closest('[data-sc-close]')){close();return}
    const cat=e.target.closest('[data-sc-cat]');if(cat){manualCategory=cat.dataset.scCat;render();return}
    const choice=e.target.closest('[data-sc-choice] button');if(choice){$$('button',choice.parentElement).forEach(x=>x.classList.toggle('active',x===choice));return}
    const prof=e.target.closest('[data-sc-profile]');if(prof){$$('[data-sc-profile]',prof.parentElement).forEach(x=>x.classList.toggle('active',x===prof));return}
    if(e.target.closest('[data-sc-generate]')){generateFromUi();return}
    const add=e.target.closest('[data-sc-add]');if(add){
      const mk=decodeURIComponent(add.dataset.scAdd),sk=decodeURIComponent(add.dataset.scSig);
      const m=todaysMatches().find(x=>matchKey(x)===mk),s=m&&scenarioSignals(m).find(x=>x.key===sk);if(m&&s)addSignal(m,s);return;
    }
    const lineOpen=e.target.closest('[data-sc-line-open]');if(lineOpen){
      const key=decodeURIComponent(lineOpen.dataset.scLineOpen);
      lineEditorKey=lineEditorKey===key?null:key;render();return;
    }
    const linePick=e.target.closest('[data-sc-line-pick]');if(linePick){
      changeDraftLine(
        decodeURIComponent(linePick.dataset.scLinePick),
        decodeURIComponent(linePick.dataset.scOldSig),
        decodeURIComponent(linePick.dataset.scNewSig)
      );return;
    }
    const rem=e.target.closest('[data-sc-remove]');if(rem){removeSignal(decodeURIComponent(rem.dataset.scRemove),decodeURIComponent(rem.dataset.scSig));return}
    if(e.target.closest('[data-sc-clear]')){lineEditorKey=null;clearDraft();render();return}
    if(e.target.closest('[data-sc-save]')){saveScenario();return}
  }

  window.TENIS_AI_SCENARIOS={
    version:VERSION,
    open,
    close,
    openManualForMatch:(m)=>open('manual',typeof m==='string'?m:matchKey(m)),
    add:(m,s)=>addSignal(m,s),
    generate:()=>open('generator'),
    draft:()=>JSON.parse(JSON.stringify(draft))
  };

  document.addEventListener('DOMContentLoaded',()=>{ensureShell();mountRetries()},{once:true});
  if(document.readyState!=='loading'){ensureShell();mountRetries()}
})();
