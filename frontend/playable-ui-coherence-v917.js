/* Tenis AI v9.1.7 — one Superbet PLAYABLE gate for actionable UI.
   Match visibility and RAW analytics stay independent. This layer only prevents
   unverified/stale RAW selections from being presented as Top/FINAL/Symphony bets. */
(()=>{
'use strict';
if(window.TENIS_AI_PLAYABLE_UI_V917)return;

const VERSION='v9.1.7';
const WRAP='__tenisAiPlayableUiV917';
const LINE_MARKETS=new Set([
  'match_total','set1_total','set2_total','set3_total','total_sets',
  'match_game_handicap','set1_game_handicap','set2_game_handicap',
  'player_total_games','match_total_aces','player_aces','player_double_faults'
]);
const PLAYER_MARKETS=new Set(['player_total_games','player_aces','player_double_faults']);
const WINNER_MARKETS=new Set([
  'match_winner','set1_winner','set2_winner','set3_winner',
  'most_aces','most_double_faults','most_aces_plus_df'
]);
const ALIASES={
  match_win:'match_winner',
  first_set_win:'set1_winner',set1_win:'set1_winner',
  second_set_win:'set2_winner',set2_win:'set2_winner',
  third_set_win:'set3_winner',set3_win:'set3_winner',
  exact_set1:'set1_exact_score',exact_first_set:'set1_exact_score',
  exact_match:'exact_match_score',
  state2:'game_state',state4:'game_state',state6:'game_state'
};

const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const num=v=>finite(v)?Number(v):null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9:.+\-]+/g,' ').replace(/\s+/g,' ').trim();
const nameKey=v=>norm(v).replace(/[^a-z0-9]+/g,' ').split(' ').filter(Boolean).sort().join(' ');

function canonicalMarket(value){
  const raw=norm(value).replace(/ /g,'_');
  return ALIASES[raw]||raw;
}
function context(match){
  const x=match?.superbet_market_v91;
  return x&&typeof x==='object'?x:{};
}
function active(match){
  const x=context(match);
  return x.operator_verified===true&&x.status==='VERIFIED'&&x.suspended!==true&&Array.isArray(x.canonical_selections);
}
function keyParts(row){return String(row?.key||row?.signal_key||'').split('|')}
function rowLine(row,market=canonicalMarket(row?.market)){
  const direct=num(row?.line??row?.selected_line??row?.suggested_line);
  if(direct!=null)return direct;
  const pick=String(row?.pick||row?.displayPick||'');
  if(market==='total_sets'){
    const m=pick.match(/(-?\d+(?:\.\d+)?)/);
    if(m)return Number(m[1]);
  }
  const p=keyParts(row);
  if(p[0]==='superbet'&&num(p[4])!=null)return Number(p[4]);
  if(LINE_MARKETS.has(market)&&num(p[1])!=null)return Number(p[1]);
  return null;
}
function rowCheckpoint(row,market=canonicalMarket(row?.market)){
  const direct=num(row?.checkpoint);
  if(direct!=null)return Math.trunc(direct);
  const raw=norm(row?.market).replace(/ /g,'_');
  const state=raw.match(/^state([246])$/);
  if(state)return Number(state[1]);
  const p=keyParts(row);
  if(p[0]==='superbet'&&num(p[2])!=null)return Math.trunc(Number(p[2]));
  if(market==='game_state'&&num(p[1])!=null)return Math.trunc(Number(p[1]));
  return 0;
}
function rowPlayer(row,market=canonicalMarket(row?.market)){
  if(!PLAYER_MARKETS.has(market))return'';
  const direct=row?.player??row?.extra;
  if(direct)return nameKey(direct);
  const p=keyParts(row);
  return p[0]==='superbet'?nameKey(p[3]):'';
}
function pickKey(value,market){
  const raw=norm(value);
  if(WINNER_MARKETS.has(market))return nameKey(value);
  if(['set1_exact_score','exact_match_score','game_state'].includes(market)){
    const m=String(value??'').match(/(\d+)\s*[:\-]\s*(\d+)/);
    return m?`${Number(m[1])}:${Number(m[2])}`:raw;
  }
  if(raw==='o'||raw==='over'||raw.startsWith('over ')||raw==='powyzej')return'over';
  if(raw==='u'||raw==='under'||raw.startsWith('under ')||raw==='ponizej')return'under';
  if(raw==='tak'||raw==='yes')return'yes';
  if(raw==='nie'||raw==='no')return'no';
  return raw;
}
function rowPick(row,market=canonicalMarket(row?.market)){
  let value=row?.pick??'';
  const p=keyParts(row);
  if(!value&&p[0]==='superbet')value=p[5]||'';
  return pickKey(value,market);
}
function signature(row){
  const market=canonicalMarket(row?.market);
  const line=LINE_MARKETS.has(market)?rowLine(row,market):null;
  const checkpoint=market==='game_state'?rowCheckpoint(row,market):0;
  const player=rowPlayer(row,market);
  return [market,rowPick(row,market),line==null?'':Number(line).toFixed(6),checkpoint||0,player].join('¦');
}
function availability(match){
  const out=new Map();
  if(!active(match))return out;
  for(const row of context(match).canonical_selections||[]){
    if(!row||typeof row!=='object'||row.operator_available===false)continue;
    out.set(signature(row),row);
  }
  return out;
}
function isPlayable(match,row){
  if(!active(match)||!row||typeof row!=='object')return false;
  return availability(match).has(signature(row));
}
function valueOf(row){return num(row?.v??row?.final_score??row?.adaptive_prod_score??row?.score??row?.current)}
function playableSignals(match,limit=100){
  if(!active(match))return[];
  const api=window.TENIS_AI_MODEL_API;
  let rows=[];
  try{
    if(typeof api?.signals==='function')rows=api.signals(match,Math.max(100,Number(limit)||100))||[];
    else if(typeof api?.allSignals==='function')rows=api.allSignals(match)||[];
  }catch{return[]}
  return rows.filter(row=>isPlayable(match,row)&&valueOf(row)!=null)
    .sort((a,b)=>(valueOf(b)||0)-(valueOf(a)||0))
    .slice(0,Math.max(1,Number(limit)||100));
}
function scoreText(v){return finite(v)?`${Math.round(Number(v))}/100`:'N/D'}
function setText(el,text){if(el&&el.textContent!==text)el.textContent=text}
function setBars(root,v){
  const n=num(v);
  root?.querySelectorAll?.('.p751-bars i').forEach((bar,index)=>{
    const on=n!=null&&n>=(index+1)*18;
    if(bar.classList.contains('on')!==on)bar.classList.toggle('on',on);
  });
}
function decode(value){try{return decodeURIComponent(String(value||''))}catch{return String(value||'')}}
function findMatch(raw){
  const key=decode(raw);
  try{return window.TENIS_AI_PROJECT_UI?.findMatch?.(key)||null}catch{return null}
}
function matchFor(el){
  const holder=el?.closest?.('[data-p751-open]')||el;
  return findMatch(holder?.getAttribute?.('data-p751-open')||'');
}
function sameSelection(a,b){return !!a&&!!b&&signature(a)===signature(b)}

function patchMatchTotalPreview(card,match,signals,top){
  let preview=card.querySelector('.p753-match-total-preview');
  const candidate=signals.find(s=>canonicalMarket(s?.market)==='match_total')||null;
  if(!candidate||sameSelection(candidate,top)){
    preview?.remove();
    return;
  }
  const line=rowLine(candidate,'match_total');
  if(line==null){preview?.remove();return}
  if(!preview){
    preview=document.createElement('div');
    preview.className='p753-match-total-preview';
    const foot=card.querySelector('footer');
    if(foot)foot.before(preview);else card.append(preview);
  }
  const pick=rowPick(candidate,'match_total');
  const side=pick==='over'?'OVER':pick==='under'?'UNDER':String(candidate.pick||'').toUpperCase();
  const html=`<span>📊 Gemy · cały mecz · SUPERBET PLAYABLE</span><b>${esc(side)} ${esc(Number(line).toFixed(1).replace('.0',''))}</b><strong>${scoreText(valueOf(candidate))}</strong><em>linia Superbet ✓</em>`;
  if(preview.innerHTML!==html)preview.innerHTML=html;
}
function patchCard(card){
  const match=matchFor(card);
  if(!match)return;
  const signals=playableSignals(match,60);
  const top=signals[0]||null;
  const value=valueOf(top);
  const pick=card.querySelector('.p751-top-pick');
  setText(pick?.querySelector('span'),'◎ Top typ · SUPERBET');
  setText(pick?.querySelector('b'),top?String(top.label||top.pick||top.key||'Sygnał PLAYABLE'):'Brak Superbet PLAYABLE');
  setText(pick?.querySelector('em'),scoreText(value));
  const strength=card.querySelector('.p751-strength');
  setText(strength?.querySelector('span'),'Siła sygnału PLAYABLE');
  setText(strength?.querySelector('b'),scoreText(value));
  const green=signals.filter(s=>(valueOf(s)||0)>=72).length;
  setText(strength?.querySelector('small'),top?`${green} zielonych PLAYABLE`:'N/D · brak PLAYABLE');
  setBars(card,value);
  patchMatchTotalPreview(card,match,signals,top);
  card.dataset.playableUiV917=active(match)?'verified':'nd';
}
function topBarHtml(picks){
  return `<section class="p751-top" data-playable-top-v917="1"><header><b>⚡ Top sygnały · SUPERBET</b><span>${picks.length} najmocniejsze PLAYABLE</span></header><div>${picks.map(({match,signal,raw})=>`<button data-v917-top="1" data-p751-open="${esc(raw)}"><small>${esc(match.p1)} vs ${esc(match.p2)}</small><b>${esc(signal.label||signal.pick||signal.key||'Sygnał PLAYABLE')}</b><strong>${scoreText(valueOf(signal))}</strong><span class="p751-bars">${[1,2,3,4,5].map(i=>`<i class="${(valueOf(signal)||0)>=i*18?'on':''}"></i>`).join('')}</span><small class="pc882-top-meta">SUPERBET PLAYABLE · linia zweryfikowana ✓</small></button>`).join('')}</div></section>`;
}
function patchTopStrip(){
  const cards=[...document.querySelectorAll('#app .p751-match-card[data-p751-open]')];
  const picks=cards.map(card=>{
    const raw=card.getAttribute('data-p751-open')||'';
    const match=findMatch(raw);
    const signal=match?playableSignals(match,1)[0]:null;
    return match&&signal&&valueOf(signal)>=72?{match,signal,raw}:null;
  }).filter(Boolean).sort((a,b)=>valueOf(b.signal)-valueOf(a.signal)).slice(0,3);
  const old=document.querySelector('#app .p751-top');
  if(!picks.length){old?.remove();return}
  const hash=picks.map(x=>`${x.raw}:${signature(x.signal)}:${valueOf(x.signal)}`).join('|');
  if(old?.dataset?.v917Hash===hash)return;
  const wrap=document.createElement('div');
  wrap.innerHTML=topBarHtml(picks);
  const fresh=wrap.firstElementChild;
  fresh.dataset.v917Hash=hash;
  if(old)old.replaceWith(fresh);
  else{
    const focus=document.querySelector('#app .p751-focus');
    if(focus)focus.insertAdjacentElement('afterend',fresh);
    else document.querySelector('#app')?.prepend(fresh);
  }
}
function patchSignalPage(){
  const page=document.querySelector('#app .p751-signals-page');
  if(!page)return;
  for(const button of [...page.querySelectorAll('button[data-p751-open]')]){
    const match=matchFor(button);
    const label=norm(button.querySelector('span')?.textContent||button.querySelector('b')?.textContent||'');
    const signal=match?playableSignals(match,100).find(s=>norm(s.label||s.pick||s.key)===label):null;
    if(!signal){button.remove();continue}
    setText(button.querySelector('strong'),scoreText(valueOf(signal)));
  }
  if(!page.querySelector('button[data-p751-open]')){
    const body=page.querySelector('header')?.nextElementSibling;
    if(body&&!body.querySelector('[data-v917-empty]'))body.innerHTML='<div class="p751-empty" data-v917-empty="1"><b>Brak sygnałów Superbet PLAYABLE.</b><span>RAW pozostaje w analizie, ale nie jest tutaj prezentowany jako typ do zagrania.</span></div>';
  }
}
function patchHome(){
  document.querySelectorAll('#app .p751-match-card[data-p751-open]').forEach(patchCard);
  patchTopStrip();
  patchSignalPage();
}

function patchDecisionHeader(root,match,rows){
  if(!root)return;
  root.dataset.playableUiV917=active(match)?'verified':'nd';
  setText(root.querySelector('.dc87-kicker'),'Centrum Decyzji Meczu · SUPERBET PLAYABLE');
  setText(root.querySelector('#dc87-title'),'Realne rynki i linie Superbet');
  const p=root.querySelector('.dc87-head p');
  setText(p,active(match)
    ?'Pokazujemy wyłącznie rynki i dokładne linie zweryfikowane w Superbet. FINAL to wynik modelu dla tej selekcji, nie gwarancja ani kurs.'
    :'Brak świeżo zweryfikowanej oferty Superbet dla tego meczu. RAW może istnieć w analizie, ale Centrum Decyzji nie pokazuje go jako typu.');
  const health=root.querySelector('.dc87-health');
  if(health){
    let badge=health.querySelector('[data-v917-book]');
    if(!badge){badge=document.createElement('span');badge.dataset.v917Book='1';health.prepend(badge)}
    badge.className=active(match)?'prod':'shadow';
    setText(badge,active(match)?'Superbet ✓ PLAYABLE':'Superbet N/D');
  }
  const empty=root.querySelector('.dc87-empty');
  if(empty&&rows.length===0)empty.innerHTML=active(match)
    ?'<b>Brak PLAYABLE z wynikiem modelowym</b>Dla aktualnej oferty Superbet nie ma tu jeszcze pasującej selekcji z danymi.'
    :'<b>Brak świeżego Superbet PLAYABLE</b>Mecz i RAW analiza zostają dostępne, ale nie pokazujemy niezweryfikowanych linii jako FINAL.';
}
function wrapDecisionCenter(){
  const api=window.TENIS_AI_DECISION_CENTER_V87;
  if(!api||api[WRAP]||typeof api.tidy!=='function'||typeof api.buildRows!=='function'||typeof api.install!=='function')return false;
  const base=api.tidy.bind(api);
  api.tidy=function(match){
    const screen=document.querySelector('.p751-detail-screen');
    if(screen?.querySelector('.dc87[data-playable-ui-v917]'))return true;
    base(match);
    const old=screen?.querySelector('.dc87');
    if(!old)return false;
    const rows=active(match)?api.buildRows(match).filter(row=>isPlayable(match,row)):[];
    const shell=api.decisionCenter(match)?.html;
    if(!shell)return false;
    const mount=document.createElement('div');mount.innerHTML=shell;
    const fresh=mount.firstElementChild;
    old.replaceWith(fresh);
    api.install(fresh,match,rows);
    patchDecisionHeader(fresh,match,rows);
    return true;
  };
  api[WRAP]=true;
  return true;
}
function patchOpenDecision(){
  const overlay=document.querySelector('#p751-match-overlay:not([hidden])');
  if(!overlay)return;
  const match=findMatch(overlay.dataset.matchKey||'');
  if(!match)return;
  wrapDecisionCenter();
  window.TENIS_AI_DECISION_CENTER_V87?.tidy?.(match);
}

let compactPromise=null;
function loadCompact(){
  if(compactPromise)return compactPromise;
  compactPromise=fetch('./data/symphony_match_cards_v90.json?playable=917',{cache:'no-cache'})
    .then(r=>r.ok?r.json():null).catch(()=>null);
  return compactPromise;
}
function compactMap(report){
  const map=new Map();
  for(const row of report?.matches||[]){
    if(!row||typeof row!=='object')continue;
    if(row.id!=null)map.set(String(row.id),row);
    const key=String(row.match_key||'');
    if(key){map.set(key,row);if(key.startsWith('id:'))map.set(key.slice(3),row)}
    const fallback=[row.p1,row.p2,row.scheduled_time].map(x=>String(x||'')).join('|');
    if(fallback!=='||')map.set(fallback,row);
  }
  return map;
}
function compactRow(map,raw,match){
  const decoded=decode(raw);
  return map.get(decoded)||map.get(`id:${decoded}`)||map.get(String(match?.id??match?.match_id??''))||null;
}
async function patchSymphonyMinis(){
  const report=await loadCompact();
  if(!report)return;
  const map=compactMap(report);
  for(const mini of [...document.querySelectorAll('#app [data-symphony-match-mini]')]){
    const card=mini.closest('.p751-match-card[data-p751-open]');
    const raw=card?.getAttribute('data-p751-open')||'';
    const match=card?findMatch(raw):null;
    const row=compactRow(map,raw,match);
    const comp=row?.composition;
    const legs=Array.isArray(comp?.selection)?comp.selection:[];
    const ok=!!match&&active(match)&&legs.length>=2&&legs.every(leg=>isPlayable(match,leg));
    if(!ok){mini.remove();continue}
    setText(mini.querySelector('.symmatch-mini__head span'),'🎼 SYMFONIA · SUPERBET');
    const b=mini.querySelector('.symmatch-mini__head b');
    if(b&&!/^PLAYABLE ·/.test(b.textContent||''))setText(b,`PLAYABLE · ${b.textContent}`);
    const small=mini.querySelector('small');
    if(small&&!/Superbet ✓/.test(small.textContent||''))setText(small,`${small.textContent} · Superbet ✓`);
    mini.dataset.playableUiV917='verified';
  }
}

function wrapRenderMatches(){
  const current=window.renderMatches;
  if(typeof current!=='function'||current[WRAP])return false;
  const wrapped=function(...args){
    const result=current.apply(this,args);
    queueMicrotask(()=>{patchHome();patchSymphonyMinis()});
    return result;
  };
  Object.defineProperty(wrapped,WRAP,{value:true});
  window.renderMatches=wrapped;
  return true;
}

let timer=null;
function schedule(ms=40){
  clearTimeout(timer);
  timer=setTimeout(()=>{
    wrapRenderMatches();
    wrapDecisionCenter();
    patchHome();
    patchOpenDecision();
    patchSymphonyMinis();
  },ms);
}
function boot(){
  wrapRenderMatches();
  wrapDecisionCenter();
  schedule(0);setTimeout(()=>schedule(0),180);setTimeout(()=>schedule(0),800);
  document.addEventListener('click',event=>{
    const top=event.target?.closest?.('[data-v917-top]');
    if(top){
      event.preventDefault();event.stopPropagation();
      const key=decode(top.getAttribute('data-p751-open')||'');
      window.TENIS_AI_PROJECT_UI?.openMatch?.(key);
      setTimeout(patchOpenDecision,30);
      return;
    }
    if(event.target?.closest?.('[data-p751-open],[data-p751-focus],[data-filter],[data-view="matches"],[data-p751-nav="matches"],[data-p751-nav="signals"]'))schedule(80);
  },true);
  if('MutationObserver'in window){
    const observer=new MutationObserver(()=>schedule(50));
    observer.observe(document.body,{childList:true,subtree:true,characterData:true});
  }
}

window.TENIS_AI_PLAYABLE_UI_V917=Object.freeze({
  version:VERSION,
  active,
  canonicalMarket,
  signature,
  isPlayable,
  playableSignals,
  patchHome,
  patchOpenDecision,
  patchSymphonyMinis,
  reloadCompact:()=>{compactPromise=null;return patchSymphonyMinis()}
});

if(typeof document!=='undefined'){
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
}
})();
