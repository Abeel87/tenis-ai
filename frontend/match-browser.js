/* Tenis AI v9.4.9.2 — Match Browser behavior for the canonical product shell.
   Presentation/navigation only. Never changes model math, Symphony, Superbet eligibility or PLAYABLE decisions.
   The visible filter controls are owned by index.html (#focus-filters). This module
   must never inject a second filter bar or a second PLAYABLE/top-card presentation. */
(()=>{
'use strict';
const VERSION='v9.4.9.2';
const STORE='tenis-ai-match-browser-v945';
const state={mode:'all',qualityOnly:true,sort:'quality',surface:'all',returnScroll:null,returnPending:false};
try{Object.assign(state,JSON.parse(sessionStorage.getItem(STORE)||'{}'))}catch{}
const save=()=>{try{sessionStorage.setItem(STORE,JSON.stringify(state))}catch{}};
const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
const key=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));
const rowsAll=()=>Array.isArray(window.all)?window.all:(typeof all!=='undefined'&&Array.isArray(all)?all:[]);
const byKey=k=>rowsAll().find(m=>key(m)===k)||null;
const modelSignals=m=>{try{const api=window.TENIS_AI_MODEL_API;const allRows=api?.allSignals?.(m);if(Array.isArray(allRows)&&allRows.length)return allRows;const rows=api?.signals?.(m,100);return Array.isArray(rows)?rows:[]}catch{return []}};
const strength=m=>{const vals=modelSignals(m).map(x=>num(x?.v??x?.final_score??x?.score??x?.current)).filter(x=>x!=null&&x>=55);if(vals.length)return Math.max(...vals);return Math.max(0,num(m?.model_confidence)||0)};
let readyKeys=null;
function refreshReadyKeys(){try{readyKeys=new Set((window.TENIS_AI_MATCH_VISIBILITY_V916?.analysisReadyMatches?.()||[]).map(key))}catch{readyKeys=new Set()}}
const playableSignals=m=>{try{return window.TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,100)||[]}catch{return []}};
function hasAnalysis(m){if(!m)return false;if(!readyKeys)refreshReadyKeys();if(readyKeys.has(key(m)))return true;if(modelSignals(m).some(x=>num(x?.v??x?.final_score??x?.score??x?.current)!=null))return true;if(playableSignals(m).some(x=>num(x?.v??x?.final_score??x?.score??x?.current)!=null))return true;return (num(m?.model_confidence)||0)>0}
const isPlayable=m=>playableSignals(m).length>0;
const pbp=m=>!!m?.early_hold_v7?.ready;
const timeMs=m=>new Date(m?.scheduled_time||'').getTime();
const within2h=m=>{const t=timeMs(m),d=t-Date.now();return Number.isFinite(t)&&d>=0&&d<=7200000&&hasAnalysis(m)};
const surface=m=>String(m?.surface||'').trim()||'—';
function topSignal(m){const s=modelSignals(m).map(x=>({...x,v:num(x?.v??x?.final_score??x?.score??x?.current)})).filter(x=>x.v!=null).sort((a,b)=>Number(b.v)-Number(a.v))[0];return s?{label:String(s.label||s.key||'Sygnał'),value:Number(s.v)}:null}
function qualityScore(m){return (isPlayable(m)?1200:0)+(pbp(m)?180:0)+strength(m)}
function cardMatch(card){let k=card?.dataset?.p751Open||'';try{k=decodeURIComponent(k)}catch{}return byKey(k)}
function groupKey(group){const m=cardMatch(group.querySelector('.p751-match-card'));return m?`${String(m.tour||'')}|${String(m.tournament||'Turniej')}`:(group.querySelector(':scope > header b')?.textContent||'group')}
function topKey(el){return el?.getAttribute?.('data-p751-open')||''}
function visibleCardKeys(){return new Set([...document.querySelectorAll('#app .match-group:not([hidden]) .p751-match-card[data-p751-open]:not([hidden])')].map(topKey).filter(Boolean))}
function syncModelTop(){
  const top=document.querySelector('#app .signal-spotlight:not([data-playable-top-v917])');if(!top)return;
  const visible=visibleCardKeys();let shown=0;
  top.querySelectorAll('[data-p751-open]').forEach(button=>{const show=visible.has(topKey(button));button.hidden=!show;if(show)shown++});
  top.hidden=shown===0;
  const label=top.querySelector('header small');if(label)label.textContent=`${shown} wybrane z aktualnych meczów`;
}
function visibleByState(m){if(!m)return false;if(state.qualityOnly&&!hasAnalysis(m))return false;if(state.surface!=='all'&&surface(m)!==state.surface)return false;if(state.mode==='2h'&&!within2h(m))return false;if(state.mode==='80'&&strength(m)<80)return false;if(state.mode==='playable'&&!isPlayable(m))return false;if(state.mode==='pbp'&&!pbp(m))return false;return true}

const SHELL_TO_MODE={all:'all',soon:'2h',strong:'80',playable:'playable',pbp:'pbp'};
const MODE_TO_SHELL={all:'all','2h':'soon','80':'strong',playable:'playable',pbp:'pbp'};
function canonicalControls(){return document.querySelector('#focus-filters')}
function canonicalShell(){return !!document.querySelector('#product-shell')}
function syncCanonicalControls(){
  const controls=canonicalControls();if(!controls)return false;
  const focus=MODE_TO_SHELL[state.mode]||'all';
  controls.querySelectorAll('[data-focus]').forEach(button=>{
    const on=button.dataset.focus===focus;
    button.classList.toggle('active',on);
    button.setAttribute('aria-pressed',on?'true':'false');
  });
  return true;
}
function stripRetiredPresentation(){
  if(!canonicalShell())return;
  document.querySelectorAll('#app .v945-tools,#app [data-playable-top-v917="1"],#app [data-v917-playable-card],#app [data-v917-match-total-preview]').forEach(el=>el.remove());
  document.querySelectorAll('#app .match-filter-row').forEach(el=>el.remove());
}
function ensureTools(){
  if(canonicalControls()){
    state.surface='all';
    state.qualityOnly=false;
    if(!['all','2h','80','playable','pbp'].includes(state.mode))state.mode='all';
    syncCanonicalControls();
    stripRetiredPresentation();
    save();
    return;
  }
  // Legacy shells may still call the behavior API, but this module no longer
  // injects presentation. Existing legacy controls, if present, remain usable.
}
function decorateAndFilter(){
  const groupsWrap=document.querySelector('#app .match-groups');if(!groupsWrap)return;
  ensureTools();
  refreshReadyKeys();
  const groups=[...groupsWrap.querySelectorAll('.match-group')];
  groups.forEach(g=>{
    const gk=groupKey(g);g.dataset.v945Group=gk;
    const cards=[...g.querySelectorAll('.p751-match-card')];
    let ready=0,high=0,play=0,best=null,bestScore=-1;
    cards.forEach(c=>{
      const m=cardMatch(c),show=visibleByState(m);c.hidden=!show;
      if(m&&show&&hasAnalysis(m))ready++;
      if(m&&show&&strength(m)>=80)high++;
      if(m&&show&&isPlayable(m))play++;
      if(m&&show){const qs=qualityScore(m);c.dataset.v945Score=String(qs);c.dataset.v945Time=String(timeMs(m)||0);if(qs>bestScore){bestScore=qs;best=m}}
    });
    const shown=cards.filter(c=>!c.hidden).sort((a,b)=>state.sort==='quality'?Number(b.dataset.v945Score)-Number(a.dataset.v945Score):Number(a.dataset.v945Time)-Number(b.dataset.v945Time));
    const body=g.querySelector('.match-grid');shown.forEach(c=>body?.appendChild(c));
    g.hidden=shown.length===0;
    const small=g.querySelector(':scope > header small');
    if(small){
      const shownSurfaces=[...new Set(shown.map(cardMatch).filter(Boolean).map(surface))].join('/');
      small.textContent=`${shown.length} ${shown.length===1?'mecz':'meczów'}${shownSurfaces?` · ${shownSurfaces}`:''} · ${ready} policz. · ${high} ≥80 · ${play} PLAYABLE`;
      let extra=g.querySelector('.v945-summary-best');
      if(!extra){extra=document.createElement('span');extra.className='v945-summary-best';small.after(extra)}
      const ts=best?topSignal(best):null;
      extra.textContent=best&&ts?`★ ${Math.round(ts.value)} · ${best.p1} vs ${best.p2} · ${ts.label}`:(shown.length?'Brak mocnego typu w tej grupie':'Brak meczów dla aktywnego filtra');
    }
  });
  const shownGroups=groups.filter(g=>!g.hidden).sort((a,b)=>{
    const ac=[...a.querySelectorAll('.p751-match-card:not([hidden])')],bc=[...b.querySelectorAll('.p751-match-card:not([hidden])')];
    if(state.sort==='quality')return Math.max(0,...bc.map(x=>Number(x.dataset.v945Score)||0))-Math.max(0,...ac.map(x=>Number(x.dataset.v945Score)||0));
    return Math.min(...ac.map(x=>Number(x.dataset.v945Time)||Infinity))-Math.min(...bc.map(x=>Number(x.dataset.v945Time)||Infinity));
  });
  shownGroups.forEach(g=>groupsWrap.appendChild(g));
  let empty=groupsWrap.querySelector('.v945-empty');
  if(!shownGroups.length){
    if(!empty){empty=document.createElement('div');empty.className='p751-empty v945-empty';groupsWrap.appendChild(empty)}
    empty.innerHTML='<b>Brak meczów dla tego zestawu filtrów.</b><span>Zmień filtr.</span>';
  }else empty?.remove();
  const count=document.querySelector('#app .match-browser-head > div > b');
  if(count)count.textContent=`${groups.reduce((n,g)=>n+g.querySelectorAll('.p751-match-card:not([hidden])').length,0)} spotkań`;
  syncModelTop();
  syncCanonicalControls();
  stripRetiredPresentation();
  queueMicrotask(()=>window.TENIS_AI_PLAYABLE_UI_V917?.patchHome?.());
}
function enhance(){if(!document.querySelector('#app .match-browser-head'))return;decorateAndFilter()}
function restoreReturnScroll(){if(!state.returnPending)return;const y=num(state.returnScroll);state.returnPending=false;state.returnScroll=null;save();if(y==null)return;requestAnimationFrame(()=>requestAnimationFrame(()=>window.scrollTo({top:y,left:0,behavior:'auto'})))}

document.addEventListener('click',e=>{
  const focus=e.target.closest?.('#focus-filters [data-focus]');
  if(focus){
    const mode=SHELL_TO_MODE[focus.dataset.focus];
    if(mode){e.preventDefault();state.mode=mode;save();enhance();return}
  }
  const mode=e.target.closest?.('[data-v945-mode]');
  if(mode){e.preventDefault();state.mode=mode.dataset.v945Mode;save();enhance();return}
  const ready=e.target.closest?.('[data-v945-ready]');
  if(ready){e.preventDefault();state.qualityOnly=!state.qualityOnly;save();enhance();return}
  const sort=e.target.closest?.('[data-v945-sort]');
  if(sort){e.preventDefault();state.sort=state.sort==='quality'?'time':'quality';save();enhance();return}
  const open=e.target.closest?.('[data-p751-open]');
  if(open&&!e.target.closest?.('.v762-player-link')){state.returnScroll=window.scrollY;state.returnPending=true;save();return}
  const close=e.target.closest?.('[data-p751-close],[data-close-match]');
  if(close)setTimeout(restoreReturnScroll,0);
},true);
document.addEventListener('change',e=>{if(e.target.matches?.('[data-v945-surface]')){state.surface=e.target.value||'all';save();enhance()}},true);
document.addEventListener('tenis-ai:matches-rendered',enhance);
window.addEventListener('pagehide',()=>{save()});
window.addEventListener('pageshow',()=>setTimeout(()=>{enhance();restoreReturnScroll()},0));
setTimeout(enhance,0);
window.TENIS_AI_MATCH_BROWSER_V945=Object.freeze({version:VERSION,hasAnalysis,within2h,qualityScore,visibleByState,syncModelTop,enhance});
})();
