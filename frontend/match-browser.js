/* Tenis AI v9.4.9.1 — Match Browser mobile rebuild.
   Presentation/navigation only. Never changes model math, Symphony, Superbet eligibility or PLAYABLE decisions. */
(()=>{
'use strict';
const VERSION='v9.4.9.1';
const STORE='tenis-ai-match-browser-v945';
const state={mode:'all',qualityOnly:true,sort:'quality',surface:'all',openGroups:[],groupStateSaved:false,returnScroll:null,returnPending:false};
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
function groupKey(group){const m=cardMatch(group.querySelector('.p751-match-card'));return m?`${String(m.tour||'')}|${String(m.tournament||'Turniej')}`:(group.querySelector('summary b')?.textContent||'group')}
function visibleByState(m){if(!m)return false;if(state.qualityOnly&&!hasAnalysis(m))return false;if(state.surface!=='all'&&surface(m)!==state.surface)return false;if(state.mode==='2h'&&!within2h(m))return false;if(state.mode==='80'&&strength(m)<80)return false;if(state.mode==='playable'&&!isPlayable(m))return false;if(state.mode==='pbp'&&!pbp(m))return false;return true}
function injectStyle(){if(document.querySelector('#v945-style'))return;const s=document.createElement('style');s.id='v945-style';s.textContent=`.v945-tools{display:grid;gap:8px;margin:8px 0 12px}.v945-primary,.v945-secondary{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding:1px}.v945-primary::-webkit-scrollbar,.v945-secondary::-webkit-scrollbar{display:none}.v945-tools button,.v945-tools select{flex:0 0 auto;border:1px solid var(--border,#334155);background:var(--panel,#101827);color:inherit;border-radius:11px;padding:9px 11px;font:inherit;font-size:13px}.v945-tools button.active{border-color:#22c55e;box-shadow:inset 0 0 0 1px #22c55e}.v945-tools select{max-width:145px}.v945-summary-best{display:block;margin-top:4px;font-size:11px;opacity:.88;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.p751-group[hidden],.p751-match-card[hidden]{display:none!important}.p751-groups{padding-bottom:92px!important}@media(max-width:700px){.p751-focus{display:none!important}.v945-tools{position:sticky;top:0;z-index:20;background:var(--bg,#08111f);padding:7px 0 5px;margin-top:0}.v945-tools button,.v945-tools select{padding:8px 10px;font-size:12px}.p751-group summary small{line-height:1.35}.p751-bottom-nav{padding-bottom:max(6px,env(safe-area-inset-bottom))}}`;document.head.appendChild(s)}
function toolHtml(){const btn=(mode,label)=>`<button data-v945-mode="${mode}" class="${state.mode===mode?'active':''}">${label}</button>`;const surfaces=[...new Set(rowsAll().map(surface).filter(x=>x&&x!=='—'))].sort();return `<section class="v945-tools" aria-label="Filtry meczów"><div class="v945-primary">${btn('all','Wszystkie')}${btn('2h','⏱ Do 2h')}${btn('80','⭐ 80+')}${btn('playable','🎯 PLAYABLE')}${btn('pbp','🧬 PBP')}</div><div class="v945-secondary"><button data-v945-ready class="${state.qualityOnly?'active':''}">✓ Z danymi</button><button data-v945-sort>⇅ ${state.sort==='quality'?'Najlepsze':'Godzina'}</button><select data-v945-surface aria-label="Nawierzchnia"><option value="all">Wszystkie naw.</option>${surfaces.map(x=>`<option value="${x.replace(/"/g,'&quot;')}" ${state.surface===x?'selected':''}>${x}</option>`).join('')}</select></div></section>`}
function ensureTools(){const app=document.querySelector('#app');if(!app)return;app.querySelector('.p751-focus')?.setAttribute('aria-hidden','true');let tools=app.querySelector('.v945-tools');const html=toolHtml();if(!tools)app.insertAdjacentHTML('afterbegin',html);else tools.outerHTML=html}
function decorateAndFilter(){
  const groupsWrap=document.querySelector('#app .p751-groups');if(!groupsWrap)return;
  refreshReadyKeys();
  const groups=[...groupsWrap.querySelectorAll('.p751-group')],open=new Set(state.openGroups||[]);
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
    const body=g.querySelector('.p751-group-body');shown.forEach(c=>body?.appendChild(c));
    g.hidden=shown.length===0;
    if(state.groupStateSaved)g.open=open.has(gk);
    const small=g.querySelector('summary small');
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
    empty.innerHTML='<b>Brak meczów dla tego zestawu filtrów.</b><span>Zmień filtr lub wyłącz „Z danymi”.</span>';
  }else empty?.remove();
  queueMicrotask(()=>window.TENIS_AI_PLAYABLE_UI_V917?.patchHome?.());
}
function enhance(){injectStyle();ensureTools();decorateAndFilter()}
function captureOpenGroups(){const groups=[...document.querySelectorAll('#app .p751-group')];if(!groups.length)return;state.openGroups=groups.filter(g=>g.open&&!g.hidden).map(groupKey);state.groupStateSaved=true;save()}
function restoreReturnScroll(){if(!state.returnPending)return;const y=num(state.returnScroll);state.returnPending=false;state.returnScroll=null;save();if(y==null)return;requestAnimationFrame(()=>requestAnimationFrame(()=>window.scrollTo({top:y,left:0,behavior:'auto'})))}
function setAllGroups(open){const groups=[...document.querySelectorAll('#app .p751-group:not([hidden])')];groups.forEach(g=>g.open=open);state.openGroups=open?groups.map(groupKey):[];state.groupStateSaved=true;save()}
document.addEventListener('click',e=>{const mode=e.target.closest('[data-v945-mode]');if(mode){e.preventDefault();state.mode=mode.dataset.v945Mode;save();enhance();return}const ready=e.target.closest('[data-v945-ready]');if(ready){e.preventDefault();state.qualityOnly=!state.qualityOnly;save();enhance();return}const sort=e.target.closest('[data-v945-sort]');if(sort){e.preventDefault();state.sort=state.sort==='quality'?'time':'quality';save();enhance();return}const collapse=e.target.closest('#collapse-all');if(collapse){setTimeout(()=>setAllGroups(false),0);return}const expand=e.target.closest('#expand-all');if(expand){setTimeout(()=>setAllGroups(true),0);return}const open=e.target.closest('[data-p751-open]');if(open&&!e.target.closest('.v762-player-link')){state.returnScroll=window.scrollY;state.returnPending=true;captureOpenGroups();save();return}const close=e.target.closest('[data-p751-close]');if(close)setTimeout(restoreReturnScroll,0)},true);
document.addEventListener('change',e=>{if(e.target.matches('[data-v945-surface]')){state.surface=e.target.value||'all';save();enhance()}},true);
document.addEventListener('toggle',e=>{if(e.target.matches?.('#app .p751-group'))captureOpenGroups()},true);
const oldRender=window.renderMatches;if(typeof oldRender==='function')window.renderMatches=function(){captureOpenGroups();const r=oldRender.apply(this,arguments);setTimeout(enhance,0);return r};
window.addEventListener('pagehide',()=>{captureOpenGroups();save()});window.addEventListener('pageshow',()=>setTimeout(()=>{enhance();restoreReturnScroll()},0));setTimeout(enhance,0);
window.TENIS_AI_MATCH_BROWSER_V945=Object.freeze({version:VERSION,hasAnalysis,within2h,qualityScore,visibleByState,enhance});
})();
