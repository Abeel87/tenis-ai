/* Tenis AI v8.4E1.1 — Global Match Time Status
   One formatter + one lightweight clock for Matches and History.
   No API calls. No MutationObserver. A passed scheduled time never implies LIVE.
*/
(function(root,factory){
  const api=factory(root);
  if(typeof module!=='undefined' && module.exports){
    module.exports=api;
  }else{
    root.TENIS_AI_MATCH_TIME=api;

  }
})(typeof window!=='undefined'?window:globalThis,function(root){
  'use strict';

  const VERSION='v8.4E1.1';
  const TICK_MS=15000;

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

  return Object.freeze({version:VERSION,compute,statusKind,isCurrent,cardStatus,rawStatus,futureDistance,pastDistance});
});
