/* Tenis AI v9.4.8 — one Superbet PLAYABLE gate for actionable UI.
   MODEL/RAW analytics stay independent. This bridge only verifies actionable
   Superbet surfaces against the current fixture offer. It contains no Symphony
   v9.x card/feed/bootstrap logic; Symphony 2.0 owns all Symphony UI. */
(()=>{
'use strict';
if(window.TENIS_AI_PLAYABLE_UI_V917)return;

const VERSION='v9.4.8';
const WRAP='__tenisAiPlayableUiV923';
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
function freshContext(x,now=Date.now()){
  const generated=Date.parse(x?.source_generated_at||'');
  const maxHours=x?.source_max_age_hours??1.8;
  const age=Number(now)-generated;
  return finite(maxHours)&&Number(maxHours)>0&&Number.isFinite(age)&&age>=0&&age<=Number(maxHours)*3600000;
}
function active(match,now=Date.now()){
  const x=context(match);
  return x.operator_verified===true&&x.status==='VERIFIED'&&x.suspended!==true&&Array.isArray(x.canonical_selections)
    &&freshContext(x,now)&&window.TENIS_AI_MATCH_TIME?.isCurrent?.(match,now)===true;
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
function modelSignals(match,limit=100){
  const api=window.TENIS_AI_MODEL_API;
  let rows=[];
  try{
    if(typeof api?.signals==='function')rows=api.signals(match,Math.max(100,Number(limit)||100))||[];
    else if(typeof api?.allSignals==='function')rows=api.allSignals(match)||[];
  }catch{return[]}
  return rows.filter(row=>valueOf(row)!=null)
    .sort((a,b)=>(valueOf(b)||0)-(valueOf(a)||0))
    .slice(0,Math.max(1,Number(limit)||100));
}
function projectionSignals(match){
  const layer=match?.superbet_playable_v912;
  if(!layer||typeof layer!=='object'||!Array.isArray(layer.signals))return null;
  return layer.signals
    .filter(row=>row&&typeof row==='object'&&row.operator_playable===true&&valueOf(row)!=null)
    .sort((a,b)=>(valueOf(b)||0)-(valueOf(a)||0));
}
function playableSignals(match,limit=100){
  if(!active(match))return[];
  const max=Math.max(1,Number(limit)||100);
  const projected=projectionSignals(match);
  if(projected!==null)return projected.slice(0,max);
  // Backward-compatible fallback only for datasets produced before the additive
  // backend projection existed. New results use superbet_playable_v912.signals.
  return modelSignals(match,Math.max(100,max))
    .filter(row=>isPlayable(match,row))
    .slice(0,max);
}
function scoreText(v){return finite(v)?`${Math.round(Number(v))}/100`:'N/D'}
function decode(value){try{return decodeURIComponent(String(value||''))}catch{return String(value||'')}}
function findMatch(raw){
  const key=decode(raw).replace(/^id:/,'');
  try{return window.TENIS_AI_PROJECT_UI?.findMatch?.(key)||null}catch{return null}
}
function matchFor(el){
  const holder=el?.closest?.('[data-p751-open]')||el;
  return findMatch(holder?.getAttribute?.('data-p751-open')||'');
}
function sameSelection(a,b){return !!a&&!!b&&signature(a)===signature(b)}
function compositionPlayable(match,comp){
  const legs=comp?.selection;
  return active(match)&&Array.isArray(legs)&&legs.length>=2&&legs.every(leg=>isPlayable(match,leg));
}

function playableCardHtml(match,signals,top){
  const value=valueOf(top);
  const green=signals.filter(s=>(valueOf(s)||0)>=72).length;
  const name=top?String(top.label||top.pick||top.key||'Sygnał PLAYABLE'):(active(match)?'Brak pojedynczego typu':'Brak Superbet PLAYABLE');
  return `<span>🎯 SUPERBET PLAYABLE</span><b>${esc(name)}</b><strong>${scoreText(value)}</strong><em>${top?`${green} zielonych PLAYABLE · linia zweryfikowana ✓`:'N/D · brak PLAYABLE · MODEL / RAW bez zmian'}</em>`;
}
function patchMatchTotalPreview(card,match,signals,top){
  let preview=card.querySelector('[data-v917-match-total-preview]');
  const candidate=signals.find(s=>canonicalMarket(s?.market)==='match_total')||null;
  if(!candidate||sameSelection(candidate,top)){
    preview?.remove();
    return;
  }
  const line=rowLine(candidate,'match_total');
  if(line==null){preview?.remove();return}
  if(!preview){
    preview=document.createElement('div');
    preview.className='p753-match-total-preview v917-playable-total';
    preview.dataset.v917MatchTotalPreview='1';
    const own=card.querySelector('[data-v917-playable-card]');
    const foot=card.querySelector('footer');
    if(own)own.after(preview);else if(foot)foot.before(preview);else card.append(preview);
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
  let box=card.querySelector('[data-v917-playable-card]');
  if(!box){
    box=document.createElement('div');
    box.className='p753-match-total-preview v917-playable-card';
    box.dataset.v917PlayableCard='1';
    const foot=card.querySelector('footer');
    if(foot)foot.before(box);else card.append(box);
  }
  const html=playableCardHtml(match,signals,top);
  if(box.innerHTML!==html)box.innerHTML=html;
  patchMatchTotalPreview(card,match,signals,top);
  card.dataset.playableUiV917=active(match)?'verified':'nd';
}
function topBarHtml(picks){
  return `<section class="p751-top" data-playable-top-v917="1"><header><b>⚡ Top sygnały · SUPERBET</b><span>${picks.length} najmocniejsze PLAYABLE</span></header><div>${picks.map(({match,signal,raw})=>`<button data-v917-top="1" data-p751-open="${esc(raw)}"><small>${esc(match.p1)} vs ${esc(match.p2)}</small><b>${esc(signal.label||signal.pick||signal.key||'Sygnał PLAYABLE')}</b><strong>${scoreText(valueOf(signal))}</strong><span class="p751-bars">${[1,2,3,4,5].map(i=>`<i class="${(valueOf(signal)||0)>=i*18?'on':''}"></i>`).join('')}</span><small class="pc882-top-meta">SUPERBET PLAYABLE · linia zweryfikowana ✓</small></button>`).join('')}</div></section>`;
}
function patchTopStrip(){
  // Top SUPERBET must be derived from the exact set that Match Browser leaves
  // visible after its mode / data / surface filters, never from hidden cards.
  const cards=[...document.querySelectorAll('#app .p751-group:not([hidden]) .p751-match-card[data-p751-open]:not([hidden])')];
  const picks=cards.map(card=>{
    const raw=card.getAttribute('data-p751-open')||'';
    const match=findMatch(raw);
    const signal=match?playableSignals(match,1)[0]:null;
    return match&&signal&&valueOf(signal)>=72?{match,signal,raw}:null;
  }).filter(Boolean).sort((a,b)=>valueOf(b.signal)-valueOf(a.signal)).slice(0,3);
  const old=document.querySelector('#app [data-playable-top-v917="1"]');
  if(!picks.length){old?.remove();return}
  const hash=picks.map(x=>`${x.raw}:${signature(x.signal)}:${valueOf(x.signal)}`).join('|');
  if(old?.dataset?.v917Hash===hash)return;
  const wrap=document.createElement('div');
  wrap.innerHTML=topBarHtml(picks);
  const fresh=wrap.firstElementChild;
  fresh.dataset.v917Hash=hash;
  if(old)old.replaceWith(fresh);
  else{
    const rawTop=document.querySelector('#app .p751-top:not([data-playable-top-v917])');
    const focus=document.querySelector('#app .p751-focus');
    if(rawTop)rawTop.insertAdjacentElement('afterend',fresh);
    else if(focus)focus.insertAdjacentElement('afterend',fresh);
    else document.querySelector('#app')?.prepend(fresh);
  }
}
function patchSignalPage(){
  const page=document.querySelector('#app .p751-signals-page');
  if(!page)return;
  page.dataset.playableUiV917='raw-preserved';
}
function patchHome(){
  document.querySelectorAll('#app .p751-match-card[data-p751-open]').forEach(patchCard);
  patchTopStrip();
  patchSignalPage();
}

function patchDecisionHeader(root,match,rows){
  if(!root)return;
  root.dataset.playableUiV917=active(match)?'verified':'nd';
  const playable=playableSignals(match,100);
  const kicker=root.querySelector('.dc87-kicker');
  if(kicker)kicker.textContent='MODEL / RAW + SUPERBET';
  const title=root.querySelector('#dc87-title');
  if(title)title.textContent='Sygnały modelowe i realna oferta';
  const p=root.querySelector('.dc87-head p');
  if(p)p.textContent=active(match)
    ?'MODEL / RAW pozostaje pełny. Sygnały dostępne na dokładnej linii bieżącej oferty są dodatkowo oznaczane jako SUPERBET PLAYABLE.'
    :'Brak świeżej oferty Superbet. MODEL / RAW pozostaje widoczny bez zmian; nic nie jest oznaczane jako FINAL ani PLAYABLE.';
  const health=root.querySelector('.dc87-health');
  if(health){
    let badge=health.querySelector('[data-v917-book]');
    if(!badge){badge=document.createElement('span');badge.dataset.v917Book='1';health.prepend(badge)}
    badge.className=active(match)?'prod':'shadow';
    badge.textContent=active(match)?`Superbet ✓ ${playable.length} PLAYABLE`:'Superbet N/D · RAW dostępny';
  }
  const empty=root.querySelector('.dc87-empty');
  if(empty&&rows.length===0)empty.innerHTML='<b>Brak sygnałów modelowych</b>Dla tego meczu MODEL / RAW nie ma jeszcze policzonych selekcji.';
}
function decisionRows(match,api){
  let built=[];
  try{built=api.buildRows(match)||[]}catch{built=[]}
  built=built.filter(row=>row&&typeof row==='object');
  const projected=active(match)?playableSignals(match,100):[];
  const projectedBySignature=new Map(projected.map(row=>[signature(row),row]));
  const rows=built.map(row=>{
    const operatorRow=projectedBySignature.get(signature(row));
    if(!operatorRow)return {...row,operator_playable:false};
    return {
      ...row,
      operator_playable:true,
      operator_verified:true,
      operator:'Superbet',
      operator_market_id:operatorRow.operator_market_id??row.operator_market_id,
      operator_selection_id:operatorRow.operator_selection_id??row.operator_selection_id,
      selected_line:operatorRow.selected_line??operatorRow.line??row.selected_line,
      superbet_playable_projection:operatorRow
    };
  });
  const seen=new Set(rows.map(signature));
  for(const operatorRow of projected){
    const sig=signature(operatorRow);
    if(seen.has(sig))continue;
    const market=canonicalMarket(operatorRow.market);
    const category=(WINNER_MARKETS.has(market)||['total_sets','exact_match_score'].includes(market))?'result'
      :(market==='game_state'?'checkpoints'
      :(LINE_MARKETS.has(market)||['set1_tiebreak','set1_exact_score'].includes(market)?'games':'special'));
    rows.push({...operatorRow,category,operator_playable:true,operator_verified:true,operator:'Superbet'});
    seen.add(sig);
  }
  return rows;
}
function wrapDecisionCenter(){
  const api=window.TENIS_AI_DECISION_CENTER_V87;
  if(!api||api[WRAP]||typeof api.tidy!=='function'||typeof api.buildRows!=='function'||typeof api.install!=='function')return false;
  const base=api.tidy.bind(api);
  api.tidy=function(match){
    const screen=document.querySelector('.p751-detail-screen');
    const modelId=window.TENIS_AI_MODEL_API?.active||'';
    const gateKey=JSON.stringify([active(match),context(match).source_generated_at,match?.scheduled_time,modelId,context(match).canonical_selections]);
    if(screen?.querySelector('.dc87[data-playable-ui-v917]')?.dataset.playableGateKey===gateKey)return true;
    base(match);
    const old=screen?.querySelector('.dc87');
    if(!old)return false;
    const rows=decisionRows(match,api);
    const shell=api.decisionCenter(match)?.html;
    if(!shell)return false;
    const mount=document.createElement('div');mount.innerHTML=shell;
    const fresh=mount.firstElementChild;
    old.replaceWith(fresh);
    api.install(fresh,match,rows);
    patchDecisionHeader(fresh,match,rows);
    fresh.dataset.playableGateKey=gateKey;
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

function wrapRenderMatches(){
  const current=window.renderMatches;
  if(typeof current!=='function'||current[WRAP])return false;
  const wrapped=function(...args){
    const result=current.apply(this,args);
    queueMicrotask(patchHome);
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
    if(event.target?.closest?.('[data-p751-open],[data-p751-focus],[data-filter],[data-view="matches"],[data-p751-nav="matches"],[data-p751-nav="signals"],[data-v945-mode],[data-v945-ready],[data-v945-sort]'))schedule(80);
  },true);
  document.addEventListener('change',event=>{
    if(event.target?.matches?.('[data-v945-surface]'))schedule(80);
  },true);
  if('MutationObserver'in window){
    const observer=new MutationObserver(()=>schedule(50));
    observer.observe(document.body,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['hidden']});
  }
}

window.TENIS_AI_PLAYABLE_UI_V917=Object.freeze({
  version:VERSION,
  active,
  freshContext,
  findMatch,
  compositionPlayable,
  canonicalMarket,
  signature,
  isPlayable,
  playableSignals,
  patchHome,
  patchOpenDecision
});

if(typeof document!=='undefined'){
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
}
})();