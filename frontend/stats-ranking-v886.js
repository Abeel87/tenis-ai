/* Tenis AI v8.8.14 — honest model ranking + visible stats trend */
(()=>{
'use strict';

const VERSION='v8.8.14';
const DASHBOARD_READY_EVENT='tenis-ai:stats-dashboard-ready';

function text(node){return String(node?.textContent||'').trim()}

function loadSymphonyStats(){
  if(!document.querySelector('link[data-symphony-stats-v90d]')){
    const link=document.createElement('link');
    link.rel='stylesheet';
    link.href='symphony-stats-v90d.css?v=90d';
    link.dataset.symphonyStatsV90d='1';
    document.head.append(link);
  }
  if(!document.querySelector('script[data-symphony-stats-v90d]')&&!window.TENIS_AI_SYMPHONY_STATS_V90D){
    const script=document.createElement('script');
    script.src='symphony-stats-v90d.js?v=90d';
    script.defer=true;
    script.dataset.symphonyStatsV90d='1';
    document.head.append(script);
  }
}

function patchModelRanking(){
  const pane=document.querySelector('[data-pc882-pane="models"]');
  const card=pane?.querySelector('.pc882-card');
  const list=card?.querySelector('.pc882-models');
  if(!card||!list)return false;
  if(card.dataset.v886Ranking==='1')return true;

  const head=card.querySelector('header');
  const title=head?.querySelector('b');
  const sub=head?.querySelector('small');
  if(title)title.textContent='Porównanie modeli i komponentów';
  if(sub)sub.textContent='kolejność wg trafności; Brier i n są pokazane jako kontekst';

  const rows=[...list.children].filter(row=>row.matches?.('div')&&!row.classList.contains('pc882-empty'));
  const proxy=rows.find(row=>/selector\s+proxy/i.test(text(row.querySelector('b'))));

  if(proxy){
    const proxyLabel=text(proxy.querySelector('b'))||'Ensemble selector proxy';
    const proxyMeta=text(proxy.querySelector('small'));
    const proxyAccuracy=text(proxy.querySelector('strong'));
    proxy.remove();

    const note=document.createElement('p');
    note.className='pc882-note';
    note.dataset.v886ProxyNote='1';
    const strong=document.createElement('b');
    strong.textContent='Proxy selektora — diagnostyka: ';
    note.append(strong,document.createTextNode(`${proxyLabel} · ${proxyAccuracy}${proxyMeta?` · ${proxyMeta}`:''}. To nie jest osobny model ani skuteczność zapisanych par, dlatego nie bierze udziału w rankingu.`));
    card.append(note);
  }

  const ranked=[...list.children].filter(row=>row.matches?.('div')&&!row.classList.contains('pc882-empty'));
  ranked.forEach((row,index)=>{
    row.classList.toggle('leader',index===0);
    const rank=row.querySelector('em');
    if(rank)rank.textContent=`#${index+1}`;
  });

  card.dataset.v886Ranking='1';
  return true;
}

function promoteMainTrend(){
  const host=document.querySelector('#pc77');
  const summary=host?.querySelector('.pc12-summary');
  const proBody=host?.querySelector('.pc12-pro .pc12-pro-body');
  if(!host||!summary||!proBody)return false;

  const trendCard=[...proBody.children].find(section=>
    section.matches?.('section.pc77-card')&&/Trend skuteczności/i.test(text(section.querySelector('.pc77-card-head b')))
  );
  if(!trendCard)return false;

  trendCard.dataset.v8812MainTrend='1';
  trendCard.classList.add('pc12-main-trend');
  summary.insertAdjacentElement('afterend',trendCard);
  return true;
}

function patch(){
  promoteMainTrend();
  patchModelRanking();
}

function boot(){
  loadSymphonyStats();
  patch();

  // Performance Center creates the basic page first.
  document.addEventListener('tenis-ai:stats-ready',()=>queueMicrotask(promoteMainTrend));

  // v8.8.13 emits this only after the async model dashboard is actually in DOM.
  // No subtree MutationObserver is needed anymore.
  document.addEventListener(DASHBOARD_READY_EVENT,()=>queueMicrotask(patch));

  document.addEventListener('click',event=>{
    if(event.target?.closest?.('[data-view="stats"],[data-pc77-period],[data-pc77]'))queueMicrotask(promoteMainTrend);
  },true);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_STATS_RANKING_V886=Object.freeze({
  version:VERSION,
  dashboardReadyEvent:DASHBOARD_READY_EVENT,
  patch:patchModelRanking,
  promoteTrend:promoteMainTrend,
  loadSymphonyStats
});
})();
