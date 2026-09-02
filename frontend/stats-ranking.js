/* Tenis AI · honest model ranking + PLAYABLE stats */
(()=>{
'use strict';

const VERSION='v8.8.16';
const DASHBOARD_READY_EVENT='tenis-ai:stats-dashboard-ready';

function text(node){return String(node?.textContent||'').trim()}

function loadSuperbetPlayableStats(){
  if(!document.querySelector('link[data-superbet-playable-stats]')){
    const link=document.createElement('link');
    link.rel='stylesheet';
    link.href='superbet-playable-stats.css';
    link.dataset.superbetPlayableStats='1';
    document.head.append(link);
  }
  if(!document.querySelector('script[data-superbet-playable-stats]')&&!window.TENIS_AI_SUPERBET_PLAYABLE_V912){
    const script=document.createElement('script');
    script.src='superbet-playable-stats.js';
    script.defer=true;
    script.dataset.superbetPlayableStats='1';
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
  if(sub)sub.textContent='RAW / diagnostyka historyczna; realnie grywalną próbkę pokazuje panel Superbet PLAYABLE';

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

function patchTrendSampleContext(card){
  card=card||document.querySelector('#pc77 .pc12-main-trend');
  const chart=card?.querySelector('.pc77-chart');
  const titles=chart?[...chart.querySelectorAll('circle title')]:[];
  const raw=text(titles.at(-1));
  if(!card||!raw)return false;

  const match=raw.match(/^(.*?)\s*·\s*(.*?)\s*·\s*n=(\d+)\s*$/i);
  if(!match)return false;
  const [,date,accuracy,nRaw]=match;
  const n=Number(nRaw);
  if(!Number.isFinite(n))return false;

  let note=card.querySelector('[data-v886-trend-sample]');
  if(!note){
    note=document.createElement('p');
    note.className='pc882-note';
    note.dataset.v886TrendSample='1';
    chart.insertAdjacentElement('afterend',note);
  }
  const strength=n<5?'BARDZO MAŁA PRÓBA':n<10?'MAŁA PRÓBA':n<20?'PRÓBA DO OSTROŻNEJ OCENY':'PRÓBA OK';
  note.innerHTML=`<b>Ostatni punkt: ${date} · ${accuracy} · n=${n}</b><br><span>${strength}${n<10?' — pojedynczy skok nie oznacza jeszcze trwałej poprawy modelu.':''}</span>`;
  return true;
}

function promoteMainTrend(){
  const host=document.querySelector('#pc77');
  const summary=host?.querySelector('.pc12-summary');
  const proBody=host?.querySelector('.pc12-pro .pc12-pro-body');
  if(!host||!summary||!proBody)return false;

  const trendCard=[...proBody.children].find(section=>
    section.matches?.('section.pc77-card')&&/Trend skuteczności/i.test(text(section.querySelector('.pc77-card-head b')))
  )||host.querySelector('.pc12-main-trend');
  if(!trendCard)return false;

  trendCard.dataset.v8812MainTrend='1';
  trendCard.classList.add('pc12-main-trend');
  summary.insertAdjacentElement('afterend',trendCard);
  patchTrendSampleContext(trendCard);
  return true;
}

function patch(){
  promoteMainTrend();
  patchModelRanking();
}

function boot(){
  loadSuperbetPlayableStats();
  patch();

  document.addEventListener('tenis-ai:stats-ready',()=>queueMicrotask(promoteMainTrend));
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
  patchTrendSampleContext,
  loadSuperbetPlayableStats
});
})();