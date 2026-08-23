/* Tenis AI v8.3C — Scenario Settlement
   Settles saved Scenario AI items from the compact post-match result feed.
   Works for localStorage scenarios and authenticated Supabase scenarios.
   No polling loop, no MutationObserver, no extra Live Tennis API calls.
*/
(() => {
  'use strict';

  const VERSION='v8.3D';
  const LOCAL_KEY='tenis-ai-v82a-scenarios-local';
  const FEED='data/scenario_results_v83c.json';
  const PBP_GRACE_HOURS=36;
  let feedPromise=null;
  let refreshing=null;

  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const iso=()=>new Date().toISOString();

  function currentClient(){
    const candidates=[window.tenisSupabase,window.supabaseClient,window.sb,window.supabase];
    return candidates.find(x=>x&&typeof x.from==='function'&&x.auth&&typeof x.auth.getUser==='function')||null;
  }

  async function loadFeed(force=false){
    if(force)feedPromise=null;
    if(!feedPromise){
      feedPromise=fetch(`${FEED}?v=83c&ts=${Date.now()}`,{cache:'no-store'})
        .then(r=>{if(!r.ok)throw new Error(`scenario_feed_${r.status}`);return r.json()})
        .then(x=>x&&Array.isArray(x.matches)?x:{matches:[]})
        .catch(()=>({matches:[]}));
    }
    return feedPromise;
  }

  function putUnique(map,key,row){
    if(!key)return;
    if(!map.has(key)){map.set(key,row);return}
    if(map.get(key)!==row)map.set(key,null);
  }

  function outcomeIndex(feed){
    const byId=new Map(),byKey=new Map(),byNamesTour=new Map(),byNames=new Map();
    for(const row of feed?.matches||[]){
      if(row?.match_id!=null)byId.set(String(row.match_id),row);
      if(row?.match_key)byKey.set(String(row.match_key),row);
      const date=String(row?.scheduled_time||'').slice(0,10);
      const p1=norm(row?.p1),p2=norm(row?.p2),tour=norm(row?.tournament);
      const k=`${p1}|${p2}|${date}`;
      const kr=`${p2}|${p1}|${date}`;
      putUnique(byNames,k,row);putUnique(byNames,kr,row);
      if(tour){
        putUnique(byNamesTour,`${k}|${tour}`,row);
        putUnique(byNamesTour,`${kr}|${tour}`,row);
      }
    }
    return {byId,byKey,byNamesTour,byNames};
  }

  function findOutcome(item,idx){
    if(item?.match_id!=null&&idx.byId.has(String(item.match_id)))return idx.byId.get(String(item.match_id));
    if(item?.match_key&&idx.byKey.has(String(item.match_key)))return idx.byKey.get(String(item.match_key));
    if(item?.match_key&&idx.byKey.has(`id:${item.match_key}`))return idx.byKey.get(`id:${item.match_key}`);
    const date=String(item?.scheduled_time||'').slice(0,10);
    const base=`${norm(item?.p1)}|${norm(item?.p2)}|${date}`;
    const tour=norm(item?.tournament);
    if(tour){
      const exact=idx.byNamesTour.get(`${base}|${tour}`);
      if(exact)return exact;
    }
    return idx.byNames.get(base)||null;
  }

  function signalLine(item){
    const selected=num(item?.selected_line);
    if(selected!=null)return selected;
    const suggested=num(item?.suggested_line);
    if(suggested!=null)return suggested;
    const parts=String(item?.signal_key||'').split('|');
    return parts.length>1?num(parts[1]):null;
  }

  function stateAt(outcome,n){return String(outcome?.pbp?.states?.[String(n)]||'')||null}
  function setWinner(outcome,idx){
    const sets=Array.isArray(outcome?.sets)?outcome.sets:[];
    if(idx===0&&outcome?.pbp?.first_set_winner)return outcome.pbp.first_set_winner;
    if(!Array.isArray(sets[idx])||sets[idx].length<2)return null;
    const [a,b]=sets[idx].map(Number);
    if(!Number.isFinite(a)||!Number.isFinite(b)||a===b)return null;
    return a>b?outcome.p1:outcome.p2;
  }

  function resultObj(result,actual,reason=null){return {result,actual,reason,settlement_version:VERSION,settled_at:iso()}}

  function terminalResult(item){
    return ['hit','miss','void'].includes(String(item?.result||'').toLowerCase())&&String(item?.settlement_version||'')===VERSION;
  }

  function pbpUnavailable(item,outcome,reason){
    const when=new Date(outcome?.scheduled_time||outcome?.settled_at||'');
    if(Number.isFinite(when.getTime())){
      const ageHours=(Date.now()-when.getTime())/36e5;
      if(ageHours<PBP_GRACE_HOURS)return {...item,result:'pending',actual:null,reason:'oczekiwanie na pełne PBP'};
    }
    return {...item,...resultObj('void',null,reason)};
  }

  function settleItem(item,outcome){
    if(terminalResult(item))return item;
    if(!outcome)return {...item,result:item?.result||'pending'};
    const status=String(outcome.status||'').toLowerCase();
    if(status==='void'||status==='retired'){
      return {...item,...resultObj('void',outcome.score_text||null,outcome.reason||'mecz nierozliczalny')};
    }

    const market=String(item?.market||'').toLowerCase();
    const pick=String(item?.pick||'');
    const pickN=norm(pick);
    const sets=Array.isArray(outcome?.sets)?outcome.sets:[];
    const line=signalLine(item);
    let hit=null,actual=null,reason=null;

    if(market==='match_win'||market==='match_winner'){
      if(!outcome.winner)return {...item,result:'pending'};
      actual=outcome.winner;hit=pickN===norm(actual);
    }else if(market==='set1_win'||market==='set1_winner'){
      actual=setWinner(outcome,0);if(!actual)return {...item,result:'pending'};hit=pickN===norm(actual);
    }else if(market==='set2_win'||market==='set2_winner'){
      actual=setWinner(outcome,1);if(!actual)return {...item,...resultObj('void',null,'brak 2. seta')};hit=pickN===norm(actual);
    }else if(market==='set3_win'||market==='set3_winner'){
      actual=setWinner(outcome,2);if(!actual)return {...item,...resultObj('void',null,'brak 3. seta')};hit=pickN===norm(actual);
    }else if(market==='set1_total'){
      let total=null;
      if(Array.isArray(sets[0]))total=Number(sets[0][0])+Number(sets[0][1]);
      if(!Number.isFinite(total))total=num(outcome?.pbp?.first_set_games);
      if(total==null||line==null)return {...item,result:'pending'};
      if(total===line)return {...item,...resultObj('void',total,'push na linii')};
      actual=total;hit=pickN==='over'?total>line:pickN==='under'?total<line:null;
    }else if(market==='match_total'){
      const total=num(outcome.total_games);if(total==null||line==null)return {...item,result:'pending'};
      if(total===line)return {...item,...resultObj('void',total,'push na linii')};
      actual=total;hit=pickN==='over'?total>line:pickN==='under'?total<line:null;
    }else if(market==='total_sets'){
      const n=num(outcome.number_of_sets);if(n==null)return {...item,result:'pending'};
      const wanted=/\b3\b/.test(pick)?3:/\b2\b/.test(pick)?2:null;if(wanted==null)return {...item,...resultObj('void',n,'nieznany format typu')};
      actual=n;hit=n===wanted;
    }else if(market==='exact_match'){
      if(!outcome.match_score)return {...item,result:'pending'};actual=outcome.match_score;hit=String(pick)===String(actual);
    }else if(market==='exact_set1'){
      const fs=outcome.first_set_score||outcome?.pbp?.first_set_score;if(!fs)return {...item,result:'pending'};actual=fs;hit=String(pick)===String(actual);
    }else if(/^state[246]$/.test(market)||market==='game_state'){
      let n=/^state[246]$/.test(market)?Number(market.slice(-1)):num(item?.checkpoint);
      if(n==null){
        const parts=String(item?.signal_key||'').split('|');
        const found=parts.find(x=>['2','4','6'].includes(String(x)));
        n=found==null?null:Number(found);
      }
      if(![2,4,6].includes(Number(n)))return {...item,...resultObj('void',null,'nieznany checkpoint PBP')};
      actual=stateAt(outcome,Number(n));
      if(!actual)return pbpUnavailable(item,outcome,`brak pełnego PBP do checkpointu ${n}`);
      hit=String(pick)===String(actual);
    }else if(market==='lead_after6'){
      const st=stateAt(outcome,6);if(!st)return pbpUnavailable(item,outcome,'brak pełnego PBP po 6 gemach');
      const [a,b]=st.split(':').map(Number);actual=a>b?outcome.p1:b>a?outcome.p2:'remis';hit=pickN===norm(actual);
    }else if(market==='balanced_after6'){
      actual=stateAt(outcome,6);if(!actual)return pbpUnavailable(item,outcome,'brak pełnego PBP po 6 gemach');hit=actual==='3:3';
    }else if(market==='joint_builder'){
      const st=stateAt(outcome,6),fsWinner=setWinner(outcome,0),fsGames=num(outcome?.pbp?.first_set_games);
      if(!st||!fsWinner||fsGames==null)return pbpUnavailable(item,outcome,'brak pełnego PBP dla Joint Builder');
      const [a,b]=st.split(':').map(Number),leader=a>b?outcome.p1:b>a?outcome.p2:null;
      actual={leader_after6:leader,first_set_winner:fsWinner,first_set_games:fsGames};
      hit=norm(leader)===pickN&&norm(fsWinner)===pickN&&fsGames>8.5;
    }else{
      reason='rynek nie ma jeszcze bezpiecznego mapowania post-match';
      return {...item,...resultObj('void',null,reason)};
    }

    if(hit==null)return {...item,...resultObj('void',actual,'niejednoznaczny typ')};
    return {...item,...resultObj(hit?'hit':'miss',actual)};
  }

  function summarize(items){
    const counts={hit:0,miss:0,void:0,pending:0};
    for(const i of items||[]){const r=String(i?.result||'pending');counts[r]=(counts[r]||0)+1}
    const decision=counts.hit+counts.miss;
    return {
      hits:counts.hit||0,misses:counts.miss||0,voids:counts.void||0,pending:counts.pending||0,
      resolved:(counts.hit||0)+(counts.miss||0)+(counts.void||0),
      accuracy:decision?Math.round((counts.hit/decision)*1000)/10:null,
      updated_at:iso(),version:VERSION
    };
  }

  function settleScenario(s,idx){
    const items=(Array.isArray(s?.items)?s.items:[]).map(i=>settleItem(i,findOutcome(i,idx)));
    const summary=summarize(items);
    const status=summary.pending>0?(summary.resolved>0?'partial':'active'):'settled';
    const oldMeta=(s&&typeof s.metadata==='object'&&s.metadata)||{};
    return {
      ...s,items,status,points:summary.hits,
      settled_at:status==='settled'?(s.settled_at||iso()):null,
      metadata:{...oldMeta,settlement_v83c:summary},
      updated_at:iso()
    };
  }

  function changed(a,b){
    return JSON.stringify({status:a?.status,items:a?.items,points:a?.points,settled_at:a?.settled_at,settlement:a?.metadata?.settlement_v83c})!==
           JSON.stringify({status:b?.status,items:b?.items,points:b?.points,settled_at:b?.settled_at,settlement:b?.metadata?.settlement_v83c});
  }

  async function settleLocal(idx){
    try{
      const rows=JSON.parse(localStorage.getItem(LOCAL_KEY)||'[]');
      if(!Array.isArray(rows)||!rows.length)return {updated:0,total:0};
      let updated=0;
      const next=rows.map(s=>{
        if(!['active','partial'].includes(String(s?.status||'active')))return s;
        const x=settleScenario(s,idx);if(changed(s,x))updated++;return x;
      });
      if(updated)localStorage.setItem(LOCAL_KEY,JSON.stringify(next));
      return {updated,total:rows.length};
    }catch{return {updated:0,total:0}}
  }

  async function settleRemote(idx){
    const client=currentClient();if(!client)return {updated:0,total:0};
    try{
      const {data:{user}}=await client.auth.getUser();if(!user?.id)return {updated:0,total:0};
      const {data,error}=await client.from('ai_scenarios').select('*').eq('user_id',user.id).in('status',['active','partial']).order('created_at',{ascending:false}).limit(50);
      if(error||!Array.isArray(data))return {updated:0,total:0};
      let updated=0;
      for(const s of data){
        const x=settleScenario(s,idx);if(!changed(s,x))continue;
        const patch={items:x.items,status:x.status,points:x.points,settled_at:x.settled_at,metadata:x.metadata,updated_at:x.updated_at};
        const {error:updateError}=await client.from('ai_scenarios').update(patch).eq('id',s.id).eq('user_id',user.id);
        if(!updateError)updated++;
      }
      return {updated,total:data.length};
    }catch{return {updated:0,total:0}}
  }

  async function refresh(opts={}){
    if(refreshing)return refreshing;
    refreshing=(async()=>{
      const feed=await loadFeed(!!opts.force),idx=outcomeIndex(feed);
      const local=await settleLocal(idx),remote=await settleRemote(idx);
      const detail={version:VERSION,feed_matches:feed?.matches?.length||0,local,remote,at:iso()};
      document.dispatchEvent(new CustomEvent('tenis-ai-scenario-settlement',{detail}));
      return detail;
    })().finally(()=>{refreshing=null});
    return refreshing;
  }

  window.TENIS_AI_SCENARIO_SETTLEMENT={version:VERSION,refresh,settleItem,summarize};
  const boot=()=>setTimeout(()=>refresh().catch(()=>{}),900);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh({force:true}).catch(()=>{})});
})();
