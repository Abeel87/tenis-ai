/* Tenis AI v9.3.3 — mobile grouping for the current Superbet coverage panel.
   Presentation only: no model math, probabilities, prices, training or settlement changes. */
(()=>{
'use strict';
if(window.TENIS_AI_MARKET_SEGREGATION_V93G)return;

const VERSION='v9.3.3';
const FILTERS=[
  ['all','Wszystkie','▦'],
  ['result','Wynik','🏆'],
  ['games','Gemy','🎾'],
  ['checkpoints','Po 2/4/6','⏱'],
  ['handicap','Handicap','±'],
  ['special','Specjalne','✨']
];
let active='all',timer=null;
const norm=value=>String(value??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[_-]+/g,' ').replace(/\s+/g,' ').trim();

function marketGroup(market,label=''){
  const text=norm(`${market} ${label}`);
  if(/game state|state ?[246]\b|po ?[246] ?gem|checkpoint/.test(text))return'checkpoints';
  if(/handicap/.test(text))return'handicap';
  if(/total|gemy|games|over|under|parity|liczba gem/.test(text))return'games';
  if(/winner|wygr|match score|exact .*score|dokladny wynik|wynik meczu|wynik set|exact sets|wins a set/.test(text))return'result';
  return'special';
}
function style(){}
function setActive(wrapper,group){
  const allowed=new Set(FILTERS.map(([id])=>id));active=allowed.has(group)?group:'all';
  const groups=wrapper.querySelector('.rp93g-groups');if(groups)groups.dataset.active=active;
  wrapper.querySelectorAll('[data-rp93g-filter]').forEach(btn=>{const on=btn.dataset.rp93gFilter===active;btn.classList.toggle('active',on);btn.setAttribute('aria-pressed',String(on))});
}
function organize(panel){
  if(!panel||panel.dataset.rp93gReady==='1')return;
  const source=panel.querySelector(':scope > .sbmc922-lines');if(!source)return;
  const rows=[...source.children].filter(el=>el.classList?.contains('sbmc922-line'));if(!rows.length)return;
  const counts=Object.fromEntries(FILTERS.map(([id])=>[id,0]));counts.all=rows.length;
  rows.forEach(row=>counts[marketGroup(row.dataset.sbmc922Market,row.querySelector('b')?.textContent||'')]++);
  const wrap=document.createElement('div');wrap.className='rp93g-wrap';
  const tabs=document.createElement('div');tabs.className='rp93g-tabs';tabs.setAttribute('role','group');tabs.setAttribute('aria-label','Filtr rynków Superbet');
  FILTERS.forEach(([id,label,icon])=>{const button=document.createElement('button');button.type='button';button.className='rp93g-tab';button.dataset.rp93gFilter=id;button.innerHTML=`${icon} ${label} <b>${counts[id]||0}</b>`;tabs.appendChild(button)});wrap.appendChild(tabs);
  const groups=document.createElement('div');groups.className='rp93g-groups';
  const byGroup=new Map(FILTERS.filter(([id])=>id!=='all').map(([id])=>[id,[]]));
  rows.forEach(row=>byGroup.get(marketGroup(row.dataset.sbmc922Market,row.querySelector('b')?.textContent||''))?.push(row));
  FILTERS.filter(([id])=>id!=='all').forEach(([id,label,icon])=>{const items=byGroup.get(id)||[];if(!items.length)return;const group=document.createElement('section');group.className='rp93g-group';group.dataset.rp93gGroup=id;const head=document.createElement('div');head.className='rp93g-group-head';head.innerHTML=`<span>${icon} ${label}</span><b>${items.length}</b>`;const list=document.createElement('div');list.className='sbmc922-lines';items.forEach(row=>list.appendChild(row));group.append(head,list);groups.appendChild(group)});
  wrap.appendChild(groups);source.replaceWith(wrap);panel.dataset.rp93gReady='1';setActive(wrap,active);
}
function patch(){style();document.querySelectorAll('#app[data-match-key] [data-superbet-model-coverage-v922]').forEach(organize)}
function schedule(ms=25){clearTimeout(timer);timer=setTimeout(patch,ms)}
document.addEventListener('click',event=>{const button=event.target?.closest?.('[data-rp93g-filter]');if(button){const wrapper=button.closest('.rp93g-wrap');if(wrapper)setActive(wrapper,button.dataset.rp93gFilter||'all');return}if(event.target?.closest?.('[data-p751-open]')){setTimeout(()=>schedule(0),60);setTimeout(()=>schedule(0),260)}},true);
function boot(){
  style();
  document.addEventListener('tenis-ai:superbet-coverage-ready',()=>schedule(0));
  document.addEventListener('tenis-ai:match-open',()=>schedule(0));
  schedule(0);
}
window.TENIS_AI_MARKET_SEGREGATION_V93G=Object.freeze({version:VERSION,patch,marketGroup,get active(){return active}});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
