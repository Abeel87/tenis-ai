/* Tenis AI v8.8.6 — honest model ranking presentation */
(()=>{
'use strict';

const VERSION='v8.8.6';

function text(node){return String(node?.textContent||'').trim()}

function patchModelRanking(){
  const pane=document.querySelector('[data-pc882-pane="models"]');
  const card=pane?.querySelector('.pc882-card');
  const list=card?.querySelector('.pc882-models');
  if(!card||!list||card.dataset.v886Ranking==='1')return false;

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

function patch(){
  patchModelRanking();
}

function boot(){
  patch();
  const observer=new MutationObserver(()=>patch());
  observer.observe(document.body,{childList:true,subtree:true});
  document.addEventListener('tenis-ai:stats-ready',()=>queueMicrotask(patch));
  document.addEventListener('click',()=>queueMicrotask(patch),true);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_STATS_RANKING_V886=Object.freeze({version:VERSION,patch:patchModelRanking});
})();
