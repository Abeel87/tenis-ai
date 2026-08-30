/* Tenis AI v9.2.4 — Symphony SUPERBET PLAYABLE hard gate + saved history.
   Presentation/persistence only: no model probabilities, training, weights or prices. */
(() => {
  'use strict';
  if (window.TENIS_AI_SYMPHONY_SUPERBET_SAVE_V924) return;

  const VERSION='v9.2.4';
  const REPORT_URL='./data/symphony_v90.json';
  const LOCAL_KEY='tenis-ai-v82a-scenarios-local';
  let reportPromise=null;
  let timer=null;

  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const num=v=>finite(v)?Number(v):null;
  const nowIso=()=>new Date().toISOString();
  const todayKey=()=>new Date().toLocaleDateString('en-CA');
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));

  function gate(){ return window.TENIS_AI_PLAYABLE_UI_V917 || null; }
  function detailGuard(){ return window.TENIS_AI_SYMPHONY_PLAYABLE_DETAIL_GUARD_V915 || null; }

  async function loadReport(force=false){
    if(force) reportPromise=null;
    if(!reportPromise){
      reportPromise=fetch(`${REPORT_URL}?superbet_save=924&ts=${Date.now()}`,{cache:'no-store'})
        .then(r=>r.ok?r.json():Promise.reject(new Error(`HTTP ${r.status}`)))
        .catch(()=>({matches:[]}));
    }
    return reportPromise;
  }

  function reportMap(report){
    const map=new Map();
    for(const row of report?.matches||[]){
      if(!row||typeof row!=='object')continue;
      if(row.id!=null)map.set(String(row.id),row);
      if(row.match_id!=null)map.set(String(row.match_id),row);
      const key=String(row.match_key||'');
      if(key){map.set(key,row);if(key.startsWith('id:'))map.set(key.slice(3),row)}
      const fallback=[row.p1,row.p2,row.scheduled_time].map(x=>String(x||'')).join('|');
      if(fallback!=='||')map.set(fallback,row);
    }
    return map;
  }

  function coherent(comp){
    const api=detailGuard();
    try{return typeof api?.compositionCoherent==='function'?api.compositionCoherent(comp):true}catch{return false}
  }

  function variantComp(root,variant){
    if(!root||!Array.isArray(root.selection)||!root.selection.length)return null;
    if(!variant)return root;
    const alt=root.alternatives?.[variant-1];
    return alt&&Array.isArray(alt.selection)&&alt.selection.length?alt:null;
  }

  function playableCandidate(row,current,n,variant){
    const api=gate();
    if(!api||!current)return null;
    const comp=variantComp(row?.compositions?.[String(n)],variant);
    if(!comp)return null;
    return api.compositionPlayable?.(current,comp)===true&&coherent(comp)?comp:null;
  }

  function preferredLegs(row){
    const n=Number(row?.leg_count_intelligence?.recommended||row?.recommended_leg_count||0);
    return Number.isInteger(n)&&n>=2&&n<=6?n:2;
  }

  function chosenFor(row,current,legsValue,variant){
    const api=gate();
    if(!api||!current||api.active?.(current)!==true)return null;
    if(legsValue!=='auto'){
      const n=Number(legsValue);
      const comp=playableCandidate(row,current,n,variant);
      return comp?{n,comp,fallback:false}:null;
    }
    const preferred=preferredLegs(row);
    const first=playableCandidate(row,current,preferred,variant);
    if(first)return {n:preferred,comp:first,fallback:false};

    const options=[];
    for(const n of [2,3,4,5,6]){
      if(n===preferred)continue;
      const comp=playableCandidate(row,current,n,variant);
      if(!comp)continue;
      const intel=(row?.leg_count_intelligence?.options||[]).find(x=>Number(x?.legs)===n)||{};
      const utility=num(intel.auto_utility)??num(comp.symphony_score)??0;
      options.push({n,comp,utility});
    }
    options.sort((a,b)=>b.utility-a.utility||Number(b.comp?.symphony_score||0)-Number(a.comp?.symphony_score||0));
    return options.length?{...options[0],fallback:true}:null;
  }

  function currentControls(){
    const root=document.querySelector('#tennis-symphony-v90');
    return {
      legs:String(root?.querySelector('#symphony-leg-count')?.value||'auto'),
      variant:Number(root?.querySelector('#symphony-variant')?.value||0)
    };
  }

  function currentMatchFor(key){
    const api=gate();
    try{return api?.findMatch?.(String(key||''))||null}catch{return null}
  }

  function operatorBadge(leg){
    const line=finite(leg?.line)?` · linia ${Number(leg.line).toFixed(1).replace('.0','')}`:'';
    return `<span class="v924-playable-badge">✓ SUPERBET PLAYABLE${line}</span>`;
  }

  function ensureStyle(){
    if(document.getElementById('symphony-v924-style'))return;
    const style=document.createElement('style');
    style.id='symphony-v924-style';
    style.textContent=`
      .v924-playable-badge{display:inline-flex;margin-top:5px;padding:3px 7px;border:1px solid rgba(111,227,255,.28);border-radius:999px;color:#9feaff;font-size:.58rem;font-weight:800;letter-spacing:.02em}
      .v924-save-row{display:flex;gap:8px;align-items:center;justify-content:space-between;margin-top:12px;padding-top:10px;border-top:1px solid rgba(130,210,230,.13)}
      .v924-save-row small{color:#8ea7b2;font-size:.62rem;line-height:1.35}
      .v924-save{border:1px solid rgba(101,225,255,.38);background:rgba(11,48,63,.8);color:#d8f8ff;border-radius:12px;padding:10px 13px;font:inherit;font-weight:800;white-space:nowrap}
      .v924-save[disabled]{opacity:.65}
      .v924-superbet-fallback{margin:8px 0;padding:8px 10px;border-radius:10px;background:rgba(255,196,74,.08);color:#ffd77a;font-size:.65rem}
      .v924-blocked{margin:12px 0;padding:14px;border:1px solid rgba(255,130,110,.2);border-radius:12px;color:#ffc5b9;background:rgba(72,22,18,.18)}
    `;
    document.head.append(style);
  }

  function addCardControls(card,row,current,chosen){
    card.querySelectorAll('.v924-playable-badge').forEach(x=>x.remove());
    const renderedLegs=[...card.querySelectorAll('.symphony-leg')];
    const chosenLegs=chosen?.comp?.selection||[];
    renderedLegs.forEach((node,i)=>{
      const meta=node.querySelector('.symphony-leg__main span')||node.querySelector('.symphony-leg__main');
      if(meta&&chosenLegs[i])meta.insertAdjacentHTML('beforeend',operatorBadge(chosenLegs[i]));
    });

    let rowEl=card.querySelector('.v924-save-row');
    if(!rowEl){
      rowEl=document.createElement('div');
      rowEl.className='v924-save-row';
      rowEl.innerHTML='<small>Dokładny rynek i linia są ponownie sprawdzane w Superbet w chwili zapisu.</small><button type="button" class="v924-save">💾 Zapisz wybór</button>';
      card.append(rowEl);
    }
    rowEl.dataset.v924Match=String(row?.match_key||row?.id||'');
    rowEl.dataset.v924Legs=String(chosen?.n||'');
    if(chosen?.fallback){
      let note=card.querySelector('.v924-superbet-fallback');
      if(!note){note=document.createElement('div');note.className='v924-superbet-fallback';card.querySelector('.symphony-card__head')?.insertAdjacentElement('afterend',note)}
      note.textContent=`AUTO: modelowa liczba nóg nie była już grywalna. Wybrano ${chosen.n} zdarzenia z aktualnej oferty Superbet.`;
    }else card.querySelector('.v924-superbet-fallback')?.remove();
    card.dataset.v924Verified='1';
  }

  async function hardenVisible(force=false){
    ensureStyle();
    const root=document.querySelector('#tennis-symphony-v90');
    if(!root)return 0;
    const api=gate();
    if(!api)return 0;
    const report=await loadReport(force);
    const map=reportMap(report);
    const controls=currentControls();
    let kept=0;
    for(const card of [...root.querySelectorAll('.symphony-card[data-symphony-match]')]){
      const key=String(card.dataset.symphonyMatch||'');
      const row=map.get(key)||map.get(key.replace(/^id:/,''));
      const current=currentMatchFor(key);
      const chosen=row?chosenFor(row,current,controls.legs,controls.variant):null;
      if(!row||!current||!chosen){card.remove();continue}

      // The base Symphony renderer may still show its precomputed AUTO count. If
      // the current operator gate had to choose another count, do not relabel an
      // old card as playable. Fail closed and let the next generation render it.
      const displayedCount=card.querySelectorAll('.symphony-leg').length;
      if(displayedCount!==chosen.n){card.remove();continue}
      addCardControls(card,row,current,chosen);kept++;
    }
    const grid=root.querySelector('#symphony-results');
    if(grid&&!grid.querySelector('.symphony-card')&&!grid.querySelector('.v924-blocked')){
      grid.innerHTML='<div class="v924-blocked"><b>Brak aktualnej kompozycji SUPERBET PLAYABLE.</b><br>Symfonia RAW może mieć analizę, ale nie pokazuję jej tutaj jako wyboru do zagrania.</div>';
    }
    return kept;
  }

  function settlementMarket(market){
    const raw=String(market||'').toLowerCase();
    if(raw==='exact_match_score')return'exact_match';
    if(raw==='set1_exact_score')return'exact_set1';
    return raw;
  }

  function itemFromLeg(row,leg){
    const line=num(leg?.line);
    const value=num(leg?.evidence_score)??num(leg?.prod_score)??num(leg?.score)??0;
    const market=settlementMarket(leg?.market);
    return {
      match_key:String(row?.match_key||row?.id||''),
      match_id:row?.id??row?.match_id??null,
      p1:row?.p1||'',p2:row?.p2||'',scheduled_time:row?.scheduled_time||null,
      tournament:row?.tournament||row?.tour||'',surface:row?.surface||'',
      signal_key:String(leg?.key||`${market}|${line??''}|${leg?.pick??''}`),
      label:String(leg?.label||leg?.key||'Sygnał Symfonii'),
      market,pick:leg?.pick??null,checkpoint:leg?.checkpoint??null,player:leg?.player??null,
      line,selected_line:line,suggested_line:line,
      value:Number(value),composer_score:Number(value),
      result:'pending',
      operator:'superbet.pl',operator_available:true,operator_line_verified:true,
      symphony_raw_market:String(leg?.market||''),
      symphony_market_source:leg?.market_source||null
    };
  }

  function currentClient(){
    const candidates=[window.tenisSupabase,window.supabaseClient,window.sb,window.supabase];
    return candidates.find(x=>x&&typeof x.from==='function'&&x.auth&&typeof x.auth.getUser==='function')||null;
  }

  function saveLocal(payload,remote=false){
    try{
      const rows=JSON.parse(localStorage.getItem(LOCAL_KEY)||'[]');
      const list=Array.isArray(rows)?rows:[];
      list.unshift({...payload,id:`${remote?'remote':'local'}-${Date.now()}`,remote,created_at:payload.created_at||nowIso()});
      localStorage.setItem(LOCAL_KEY,JSON.stringify(list.slice(0,100)));
      return true;
    }catch{return false}
  }

  async function saveChoice(button){
    const card=button.closest('.symphony-card[data-symphony-match]');
    if(!card)return;
    button.disabled=true;button.textContent='Sprawdzam Superbet…';
    try{
      const report=await loadReport(true);
      const map=reportMap(report);
      const key=String(card.dataset.symphonyMatch||'');
      const row=map.get(key)||map.get(key.replace(/^id:/,''));
      const current=currentMatchFor(key);
      const controls=currentControls();
      const chosen=row?chosenFor(row,current,controls.legs,controls.variant):null;
      if(!row||!current||!chosen||gate()?.compositionPlayable?.(current,chosen.comp)!==true||!coherent(chosen.comp)){
        button.textContent='⛔ Linia już nieaktualna';
        setTimeout(()=>hardenVisible(true),80);
        return;
      }

      const items=(chosen.comp.selection||[]).map(leg=>itemFromLeg(row,leg));
      const createdAt=nowIso();
      const payload={
        scenario_date:todayKey(),
        title:`Symfonia · ${row.p1||''} vs ${row.p2||''} · ${chosen.n} zd.`,
        match_count:1,signal_count:items.length,
        composer_score:Number((num(chosen.comp.symphony_score)??0).toFixed(2)),
        calibrated_probability:null,items,
        metadata:{
          saved_from:'symphony_superbet',app_feature:VERSION,mode:'symphony',profile:controls.legs,
          operator:'superbet.pl',operator_playable_only:true,operator_revalidated_at:createdAt,
          operator_projection_version:chosen.comp.operator_projection_version||row?.operator_reprojection?.version||null,
          story_type:chosen.comp.story_type||null,variant:controls.variant,
          joint_probability:chosen.comp.joint_probability??null,path_coverage:chosen.comp.path_coverage??null,
          symphony_score:chosen.comp.symphony_score??null,leg_count:chosen.n
        },
        composer_version:VERSION
      };

      const client=currentClient();
      if(client){
        try{
          const {data:{user}}=await client.auth.getUser();
          if(user?.id){
            const {error}=await client.from('ai_scenarios').insert({...payload,user_id:user.id});
            if(!error){
              saveLocal({...payload,created_at:createdAt},true);
              button.textContent='✓ Zapisano na profilu';
              return;
            }
          }
        }catch(e){console.warn('[Symphony save]',e)}
      }
      if(saveLocal({...payload,created_at:createdAt},false))button.textContent='✓ Zapisano lokalnie';
      else button.textContent='⚠ Nie udało się zapisać';
    }finally{
      setTimeout(()=>{button.disabled=false;if(button.textContent.startsWith('✓'))button.textContent='💾 Zapisz ponownie'},1800);
    }
  }

  function schedule(ms=40,force=false){clearTimeout(timer);timer=setTimeout(()=>hardenVisible(force),ms)}

  function boot(){
    ensureStyle();
    document.addEventListener('click',e=>{
      const save=e.target?.closest?.('.v924-save');
      if(save){e.preventDefault();e.stopPropagation();saveChoice(save);return}
      if(e.target?.closest?.('#symphony-generate,[data-sc-go="generator"]'))schedule(80,true);
    },true);
    if('MutationObserver'in window){
      const observer=new MutationObserver(records=>{
        if(records.some(r=>[...r.addedNodes].some(n=>n?.nodeType===1&&(n.matches?.('#tennis-symphony-v90,.symphony-card')||n.querySelector?.('#tennis-symphony-v90,.symphony-card')))))schedule(30,false);
      });
      observer.observe(document.body,{childList:true,subtree:true});
    }
    schedule(150,true);
  }

  window.TENIS_AI_SYMPHONY_SUPERBET_SAVE_V924=Object.freeze({
    version:VERSION,hardenVisible,loadReport,chosenFor,saveChoice
  });
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
