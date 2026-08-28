/* Tenis AI v8.4E1.1 — Global Match Time Status
   One formatter + one lightweight clock for Matches, History and Scenario AI.
   No API calls. No MutationObserver. A passed scheduled time never implies LIVE.
*/
(function(root,factory){
  const api=factory(root);
  if(typeof module!=='undefined' && module.exports){
    module.exports=api;
  }else{
    root.TENIS_AI_MATCH_TIME=api;
    api.mount();
  }
})(typeof window!=='undefined'?window:globalThis,function(root){
  'use strict';

  const VERSION='v8.4E1.1';
  const TICK_MS=15000;
  const LOCAL_KEY='tenis-ai-v82a-scenarios-local';

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[c]);

  function rawStatus(m){
    const result=m?.result;
    const resultStatus=result && typeof result==='object' ? result.status : '';
    const resultText=typeof result==='string' ? result : '';
    return [m?.event_status,m?.feed_status,m?.status,resultStatus,resultText]
      .filter(Boolean).join(' ').toLowerCase();
  }

  function statusKind(m){
    const s=rawStatus(m);
    if(/cancelled|canceled/.test(s))return 'cancelled';
    if(/postponed/.test(s))return 'postponed';
    if(/abandoned/.test(s))return 'abandoned';
    if(/walk\s*over|walkover/.test(s))return 'walkover';
    if(/retired|retirement/.test(s))return 'retired';
    if(/\b(settled|completed|complete|finished|ended|hit|miss)\b/.test(s))return 'finished';
    if(/\bvoid\b/.test(s))return 'void';
    if(/suspend/.test(s))return 'suspended';
    if(/interrupt/.test(s))return 'interrupted';
    // Terminal states take precedence over an old LIVE field. "Not started"
    // is a scheduled status, not evidence that play has begun.
    const active=s.replace(/not[\s_-]*started/g,'');
    if(/\blive\b|in[\s_-]?progress|playing|\bstarted\b/.test(active))return 'live';
    return 'scheduled';
  }

  function isCurrent(m,nowValue=Date.now(),graceMinutes=30){
    if(!m||!['scheduled','live','suspended','interrupted'].includes(statusKind(m)))return false;
    const scheduled=parseTime(m.scheduled_time);
    // Keep fixtures with missing time visible as N/D; never invent a start.
    return !scheduled||scheduled.getTime()>=Number(nowValue)-graceMinutes*60000;
  }

  function cardStatus(m,nowValue=Date.now()){
    const kind=statusKind(m);
    const labels={live:'LIVE',suspended:'ZAWIESZONY',interrupted:'PRZERWANY',
      cancelled:'ANULOWANY',postponed:'PRZEŁOŻONY',abandoned:'PRZERWANY',
      walkover:'WALKOVER',retired:'RETIRED',finished:'ZAKOŃCZONY',void:'ZAKOŃCZONY · VOID'};
    if(labels[kind])return {txt:labels[kind],cls:kind};
    const scheduled=parseTime(m?.scheduled_time);
    if(!scheduled)return {txt:'CZAS N/D',cls:'unknown'};
    if(scheduled.getTime()<=Number(nowValue))return {txt:'OCZEKUJE NA STATUS',cls:'waiting'};
    return {txt:'PRZED MECZEM',cls:'upcoming'};
  }

  function badgeHtml(m){
    const s=cardStatus(m);
    return `<span class="p751-status ${esc(s.cls)}" data-tai-match-status="1" data-scheduled-time="${esc(m?.scheduled_time||'')}" data-match-status="${esc(rawStatus(m))}">${esc(s.txt)}</span>`;
  }

  function parseTime(value){
    const d=new Date(value||'');
    return Number.isFinite(d.getTime())?d:null;
  }

  function sameDay(a,b){
    return a.getFullYear()===b.getFullYear()
      && a.getMonth()===b.getMonth()
      && a.getDate()===b.getDate();
  }

  function dayLabel(d,now){
    if(sameDay(d,now))return 'Dziś';
    const tomorrow=new Date(now);
    tomorrow.setDate(tomorrow.getDate()+1);
    if(sameDay(d,tomorrow))return 'Jutro';
    return d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'});
  }

  function clock(d){
    return d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'});
  }

  function historicalStamp(d){
    return `${d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})} · ${clock(d)}`;
  }

  function futureDistance(ms){
    const total=Math.max(0,Math.ceil(ms/1000));
    const days=Math.floor(total/86400);
    const hours=Math.floor((total%86400)/3600);
    const mins=Math.floor((total%3600)/60);
    const secs=total%60;
    if(days>0)return `${days} d ${hours} h`;
    if(hours>0)return `${hours} h ${mins} min`;
    if(mins>=10)return `${mins} min`;
    if(mins>0)return `${mins} min ${secs} s`;
    return `${Math.max(1,secs)} s`;
  }

  function pastDistance(ms){
    const total=Math.max(0,Math.floor(ms/1000));
    const hours=Math.floor(total/3600);
    const mins=Math.floor((total%3600)/60);
    if(hours>0)return `${hours} h ${mins} min`;
    if(mins>0)return `${mins} min`;
    return 'chwilę';
  }

  function compute(m,nowValue=Date.now(),mode='full'){
    const now=new Date(nowValue);
    const scheduled=parseTime(m?.scheduled_time);
    const kind=statusKind(m);

    const scheduledLong=scheduled ? `${dayLabel(scheduled,now)} ${clock(scheduled)}` : 'czas nieznany';
    const historical=scheduled ? historicalStamp(scheduled) : 'czas nieznany';

    let stateText='';
    if(kind==='cancelled')stateText='⚫ ANULOWANY';
    else if(kind==='postponed')stateText='🟠 PRZEŁOŻONY';
    else if(kind==='abandoned')stateText='⚪ PRZERWANY';
    else if(kind==='walkover')stateText='⚪ WALKOVER';
    else if(kind==='retired')stateText='⚪ RETIRED';
    else if(kind==='suspended')stateText='🟠 ZAWIESZONY';
    else if(kind==='interrupted')stateText='🟠 PRZERWANY';
    else if(kind==='live')stateText='🔴 TRWA';
    else if(kind==='finished')stateText='✅ ZAKOŃCZONY';
    else if(kind==='void')stateText='⚪ ZAKOŃCZONY · VOID';
    else if(!scheduled)stateText='🕒 START —';
    else {
      const diff=scheduled.getTime()-now.getTime();
      if(diff>0){
        stateText=`🕒 za ${futureDistance(diff)}`;
      }else{
        stateText=`⏱ start planowany ${pastDistance(-diff)} temu · oczekiwanie na status`;
      }
    }

    let text;
    if(mode==='compact'){
      text=stateText;
    }else if(mode==='history' && ['finished','void','retired','walkover','abandoned','cancelled'].includes(kind)){
      text=`🕒 Start: ${historical} · ${stateText}`;
    }else if(['cancelled','postponed','abandoned','walkover','retired','suspended','interrupted'].includes(kind)){
      text=scheduled ? `${stateText} · planowano ${scheduledLong}` : stateText;
    }else if(kind==='live'){
      text=scheduled ? `${stateText} · planowano ${scheduledLong}` : stateText;
    }else if(kind==='finished' || kind==='void'){
      text=scheduled ? `🕒 Start: ${historical} · ${stateText}` : stateText;
    }else{
      text=scheduled ? `${scheduledLong} · ${stateText}` : stateText;
    }

    return {
      version:VERSION,
      kind,
      text,
      scheduled_time:scheduled?scheduled.toISOString():null,
      raw_status:rawStatus(m),
      mode
    };
  }

  function html(m,mode='full'){
    const x=compute(m,Date.now(),mode);
    const sid=m?.id??m?.match_id??'';
    return `<span class="tai-match-time tai-time-${esc(x.kind)}" data-tai-match-time="1" data-scheduled-time="${esc(m?.scheduled_time||'')}" data-match-status="${esc(x.raw_status)}" data-time-mode="${esc(mode)}" data-match-id="${esc(sid)}">${esc(x.text)}</span>`;
  }

  function markerModel(el){
    return {
      scheduled_time:el.dataset.scheduledTime||null,
      status:el.dataset.matchStatus||''
    };
  }

  function refreshMarker(el,now=Date.now()){
    const x=compute(markerModel(el),now,el.dataset.timeMode||'full');
    const cls=`tai-match-time tai-time-${x.kind}`;
    if(el.className!==cls)el.className=cls;
    if(el.textContent!==x.text)el.textContent=x.text;
  }

  function refreshAllMarkersOnly(){
    if(typeof document==='undefined')return;
    document.querySelectorAll('[data-tai-match-time="1"]').forEach(el=>refreshMarker(el));
    document.querySelectorAll('[data-tai-match-status="1"]').forEach(el=>{
      const s=cardStatus(markerModel(el));
      const cls=`p751-status ${s.cls}`;
      if(el.className!==cls)el.className=cls;
      if(el.textContent!==s.txt)el.textContent=s.txt;
    });
  }

  function currentHistoryRows(){
    try{
      if(typeof historyRows!=='undefined' && Array.isArray(historyRows)){
        return historyRows.filter(e=>{
          if(!(e.signals||[]).length)return false;
          if(e.status==='settled'||e.status==='void')return true;
          const t=new Date(e.scheduled_time||'').getTime();
          return Number.isFinite(t)&&t<=Date.now()+5*60*1000;
        }).slice(0,150);
      }
    }catch{}
    return [];
  }

  function decorateHistory(){
    if(typeof document==='undefined')return;
    const cards=[...document.querySelectorAll('#app .history-card')];
    const rows=currentHistoryRows();
    cards.forEach((card,i)=>{
      if(card.querySelector('[data-tai-match-time="1"]'))return;
      const row=rows[i];
      const anchor=card.querySelector('.history-match');
      if(!row||!anchor)return;
      anchor.insertAdjacentHTML('afterend',html(row,'history'));
    });
  }

  function scenarioDraftGroups(){
    try{
      const d=root.TENIS_AI_SCENARIOS?.draft?.();
      const map=new Map();
      for(const item of d?.items||[]){
        const key=String(item?.match_key||item?.match_id||`${item?.p1}|${item?.p2}|${item?.scheduled_time}`);
        if(!map.has(key))map.set(key,item);
      }
      return [...map.values()];
    }catch{return []}
  }

  function savedRows(){
    try{
      const rows=JSON.parse(localStorage.getItem(LOCAL_KEY)||'[]');
      return Array.isArray(rows)?rows:[];
    }catch{return []}
  }

  function decorateDraft(){
    if(typeof document==='undefined')return;
    const articles=[...document.querySelectorAll('#scenario-v82a-panel .sc82-draft-list > article')];
    const groups=scenarioDraftGroups();
    articles.forEach((article,i)=>{
      const header=article.querySelector('header');
      if(!header||header.querySelector('[data-tai-match-time="1"]'))return;
      const item=groups[i];
      if(!item)return;
      header.insertAdjacentHTML('beforeend',html(item,'scenario'));
    });
  }

  function findSavedByTitle(title){
    const rows=savedRows().filter(x=>String(x?.title||'')===String(title||''));
    return rows[0]||null;
  }

  function decorateSaved(){
    if(typeof document==='undefined')return;
    const articles=[...document.querySelectorAll('#scenario-v82a-panel .sc82-saved > article')];
    articles.forEach(article=>{
      const title=article.querySelector('header b')?.textContent?.trim()||'';
      const scenario=findSavedByTitle(title);
      if(!scenario)return;
      const domItems=[...article.querySelectorAll('.sc82-saved-item')];
      const items=Array.isArray(scenario.items)?scenario.items:[];
      const seen=new Set();
      domItems.forEach((row,i)=>{
        if(row.querySelector('[data-tai-match-time="1"]'))return;
        const item=items[i];
        if(!item)return;
        const key=String(item?.match_key||item?.match_id||`${item?.p1}|${item?.p2}|${item?.scheduled_time}`);
        if(seen.has(key))return;
        seen.add(key);
        const anchor=row.querySelector('span');
        if(anchor)anchor.insertAdjacentHTML('afterend',html(item,'history'));
      });
    });
  }

  function decorateScenario(){
    decorateDraft();
    decorateSaved();
  }

  function installMainWrappers(){
    if(typeof root.renderMatchCard==='function' && !root.renderMatchCard.__tai_time_e11){
      const base=root.renderMatchCard;
      const wrapped=function(m){
        let out=base.apply(this,arguments);
        if(typeof out==='string' && !out.includes('data-tai-match-time="1"')){
          out=out.replace('<div class="match-main">',`<div class="match-main">${html(m,'compact')}`);
        }
        return out;
      };
      wrapped.__tai_time_e11=true;
      try{root.renderMatchCard=wrapped}catch{}
      try{renderMatchCard=wrapped}catch{}
    }

    if(typeof root.renderHistory==='function' && !root.renderHistory.__tai_time_e11){
      const base=root.renderHistory;
      const wrapped=function(){
        const value=base.apply(this,arguments);
        setTimeout(decorateHistory,0);
        return value;
      };
      wrapped.__tai_time_e11=true;
      try{root.renderHistory=wrapped}catch{}
      try{renderHistory=wrapped}catch{}
    }
  }

  function scheduleDecorate(){
    [0,60,220,600].forEach(ms=>setTimeout(()=>{
      decorateHistory();
      decorateScenario();
      refreshAllMarkersOnly();
    },ms));
  }

  function refreshAll(){
    if(typeof document==='undefined'||document.hidden)return;
    decorateScenario();
    refreshAllMarkersOnly();
    root.TENIS_AI_MATCH_VISIBILITY_V916?.refreshClock?.();
  }

  let timer=null;
  function mount(){
    if(typeof document==='undefined')return;
    installMainWrappers();
    scheduleDecorate();
    document.addEventListener('click',scheduleDecorate,true);
    document.addEventListener('tenis-ai-scenario-settlement',scheduleDecorate);
    document.addEventListener('visibilitychange',refreshAll);
    root.addEventListener?.('pageshow',refreshAll);
    if(!timer)timer=setInterval(refreshAll,TICK_MS);
  }

  return Object.freeze({
    version:VERSION,
    compute,
    html,
    refreshAll,
    mount,
    statusKind,
    isCurrent,
    cardStatus,
    badgeHtml,
    rawStatus,
    futureDistance,
    pastDistance
  });
});
