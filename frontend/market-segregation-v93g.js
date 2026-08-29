/* Tenis AI v9.3G — mobile market segregation for MODEL/RAW and SUPERBET UI.
   Presentation only: no model math, probabilities, prices, training or settlement changes. */
(()=>{
'use strict';
if(window.TENIS_AI_MARKET_SEGREGATION_V93G)return;

const VERSION='v9.3G';
const FILTERS=[
  ['all','Wszystkie','▦'],
  ['result','Wynik','🏆'],
  ['games','Gemy','🎾'],
  ['checkpoints','Po 2/4/6','⏱'],
  ['handicap','Handicap','±'],
  ['special','Specjalne','✨']
];
const state={raw:'all',book:'all'};
let timer=null;

const norm=value=>String(value??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[_-]+/g,' ').replace(/\s+/g,' ').trim();

function marketGroup(market,label=''){
  const text=norm(`${market} ${label}`);
  if(/game state|state ?[246]\b|po ?[246] ?gem|checkpoint/.test(text))return'checkpoints';
  if(/handicap/.test(text))return'handicap';
  if(/total|gemy|games|over|under|parity|liczba gem/.test(text))return'games';
  if(/winner|wygr|match score|exact .*score|dokladny wynik|wynik meczu|wynik set|exact sets|exactly [1-5] set|wins a set/.test(text))return'result';
  return'special';
}

function style(){
  if(document.getElementById('rp93g-style'))return;
  const s=document.createElement('style');
  s.id='rp93g-style';
  s.textContent=`
    .rp93g-wrap{margin-top:.42rem}
    .rp93g-tabs{display:flex;flex-wrap:wrap;gap:.3rem;margin:.38rem 0 .55rem}
    .rp93g-tab{appearance:none;border:1px solid rgba(109,213,242,.18);border-radius:999px;background:rgba(255,255,255,.025);color:#8faab5;padding:.3rem .48rem;font:inherit;font-size:.56rem;font-weight:800;line-height:1.15;min-height:30px}
    .rp93g-tab b{font-size:.52rem;color:#6f8d99;margin-left:.18rem}
    .rp93g-tab.active{border-color:rgba(186,255,97,.42);background:rgba(186,255,97,.08);color:#efffdc}
    .rp93g-tab.active b{color:#baff76}
    .rp93g-groups{display:grid;gap:.55rem}
    .rp93g-group{display:grid;gap:.27rem}
    .rp93g-group-head{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.15rem .12rem;color:#9bb2bc;font-size:.57rem;font-weight:850;text-transform:uppercase;letter-spacing:.035em}
    .rp93g-group-head b{color:#6f8d99;font-size:.53rem}
    .rp93g-groups[data-active="result"] .rp93g-group:not([data-rp93g-group="result"]),
    .rp93g-groups[data-active="games"] .rp93g-group:not([data-rp93g-group="games"]),
    .rp93g-groups[data-active="checkpoints"] .rp93g-group:not([data-rp93g-group="checkpoints"]),
    .rp93g-groups[data-active="handicap"] .rp93g-group:not([data-rp93g-group="handicap"]),
    .rp93g-groups[data-active="special"] .rp93g-group:not([data-rp93g-group="special"]){display:none}
    .rp93g-group .rp921-lines{margin-top:0}
    @media(max-width:720px){
      .rp93g-tabs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.32rem}
      .rp93g-tab{width:100%;padding:.38rem .34rem;font-size:.57rem}
      .rp93g-group-head{padding-top:.08rem}
    }
  `;
  document.head.appendChild(s);
}

function layerOf(details){
  const text=norm(details?.querySelector('summary')?.textContent||'');
  return text.includes('superbet')?'book':'raw';
}

function countsFor(rows){
  const counts=Object.fromEntries(FILTERS.map(([id])=>[id,0]));
  counts.all=rows.length;
  rows.forEach(row=>{
    const market=row.querySelector('small')?.textContent||'';
    const label=row.querySelector('b')?.textContent||'';
    counts[marketGroup(market,label)]++;
  });
  return counts;
}

function setActive(wrapper,layer,group){
  const allowed=new Set(FILTERS.map(([id])=>id));
  const active=allowed.has(group)?group:'all';
  state[layer]=active;
  const groups=wrapper.querySelector('.rp93g-groups');
  if(groups)groups.dataset.active=active;
  wrapper.querySelectorAll('[data-rp93g-filter]').forEach(btn=>{
    const on=btn.dataset.rp93gFilter===active;
    btn.classList.toggle('active',on);
    btn.setAttribute('aria-pressed',String(on));
  });
}

function organize(details){
  if(!details||details.dataset.rp93gReady==='1')return;
  const source=details.querySelector(':scope > .rp921-lines');
  if(!source)return;
  const rows=[...source.children].filter(el=>el.classList?.contains('rp921-line'));
  if(!rows.length)return;

  const layer=layerOf(details);
  const counts=countsFor(rows);
  const wrap=document.createElement('div');
  wrap.className='rp93g-wrap';
  wrap.dataset.rp93gLayer=layer;

  const tabs=document.createElement('div');
  tabs.className='rp93g-tabs';
  tabs.setAttribute('role','group');
  tabs.setAttribute('aria-label',layer==='book'?'Filtr rynków Superbet':'Filtr sygnałów modelowych');
  FILTERS.forEach(([id,label,icon])=>{
    const button=document.createElement('button');
    button.type='button';
    button.className='rp93g-tab';
    button.dataset.rp93gFilter=id;
    button.dataset.rp93gLayer=layer;
    button.innerHTML=`${icon} ${label} <b>${counts[id]||0}</b>`;
    tabs.appendChild(button);
  });
  wrap.appendChild(tabs);

  const groups=document.createElement('div');
  groups.className='rp93g-groups';
  const byGroup=new Map(FILTERS.filter(([id])=>id!=='all').map(([id])=>[id,[]]));
  rows.forEach(row=>{
    const market=row.querySelector('small')?.textContent||'';
    const label=row.querySelector('b')?.textContent||'';
    byGroup.get(marketGroup(market,label))?.push(row);
  });

  FILTERS.filter(([id])=>id!=='all').forEach(([id,label,icon])=>{
    const items=byGroup.get(id)||[];
    if(!items.length)return;
    const group=document.createElement('section');
    group.className='rp93g-group';
    group.dataset.rp93gGroup=id;
    const head=document.createElement('div');
    head.className='rp93g-group-head';
    head.innerHTML=`<span>${icon} ${label}</span><b>${items.length}</b>`;
    const list=document.createElement('div');
    list.className='rp921-lines';
    items.forEach(row=>list.appendChild(row));
    group.append(head,list);
    groups.appendChild(group);
  });
  wrap.appendChild(groups);
  source.replaceWith(wrap);
  details.dataset.rp93gReady='1';
  setActive(wrap,layer,state[layer]);
}

function patch(){
  style();
  document.querySelectorAll('#p751-match-overlay:not([hidden]) [data-rp921-match] details').forEach(organize);
}

function schedule(ms=25){
  clearTimeout(timer);
  timer=setTimeout(patch,ms);
}

document.addEventListener('click',event=>{
  const button=event.target?.closest?.('[data-rp93g-filter][data-rp93g-layer]');
  if(button){
    const layer=button.dataset.rp93gLayer==='book'?'book':'raw';
    const wrapper=button.closest('.rp93g-wrap');
    if(wrapper)setActive(wrapper,layer,button.dataset.rp93gFilter||'all');
    return;
  }
  if(event.target?.closest?.('[data-p751-open]')){
    setTimeout(()=>schedule(0),60);
    setTimeout(()=>schedule(0),260);
  }
},true);

const observer=new MutationObserver(()=>schedule(20));
function boot(){
  style();
  observer.observe(document.body,{childList:true,subtree:true});
  schedule(0);
}

window.TENIS_AI_MARKET_SEGREGATION_V93G=Object.freeze({version:VERSION,patch,marketGroup,state});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
