/* Tenis AI v9.4.4 — Match Browser 2.0
   Presentation/navigation only. Never changes model math, Symphony or PLAYABLE eligibility. */
(()=>{
'use strict';
const VERSION='v9.4.4';
const STORE='tenis-ai-match-browser-v944';
const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
const key=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));
const state={qualityOnly:true,sort:'quality',collapsed:false};
try{Object.assign(state,JSON.parse(sessionStorage.getItem(STORE)||'{}'))}catch{}
const save=()=>{try{sessionStorage.setItem(STORE,JSON.stringify(state))}catch{}};
const modelSignals=m=>{try{return window.TENIS_AI_MODEL_API?.allSignals?.(m)||[]}catch{return []}};
const strength=m=>{
  const vals=modelSignals(m).map(x=>num(x?.v)).filter(x=>x!=null&&x>=55);
  if(vals.length)return Math.max(...vals);
  return num(m?.model_confidence)||0;
};
const hasAnalysis=m=>strength(m)>=55 || modelSignals(m).some(x=>num(x?.v)!=null);
const playable=m=>{try{return (window.TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,1)||[]).length>0}catch{return false}};
const within2h=m=>{const t=new Date(m?.scheduled_time||'').getTime(),d=t-Date.now();return Number.isFinite(t)&&d>=0&&d<=2*60*60*1000&&hasAnalysis(m)};
const qualityScore=m=>(playable(m)?1000:0)+(m?.early_hold_v7?.ready?150:0)+strength(m);
function enhanceFocus(){
  const bar=document.querySelector('#app .p751-focus');if(!bar)return;
  const live=bar.querySelector('[data-p751-focus="live"]');
  if(live){live.dataset.p751Focus='upcoming2h';live.textContent='⏱ Do 2h'}
  if(!bar.querySelector('[data-v944-quality]')){
    const b=document.createElement('button');b.dataset.v944Quality='1';b.className=state.qualityOnly?'active':'';b.textContent='✓ Z danymi';bar.appendChild(b);
  }
  if(!bar.querySelector('[data-v944-sort]')){
    const b=document.createElement('button');b.dataset.v944Sort='1';b.textContent=state.sort==='quality'?'⇅ Najlepsze':'⇅ Godzina';bar.appendChild(b);
  }
}
function decorateGroups(){
  document.querySelectorAll('#app .p751-group').forEach(g=>{
    const cards=[...g.querySelectorAll('.p751-match-card')];
    let ready=0,strong=0,play=0;
    cards.forEach(c=>{let k=c.dataset.p751Open||'';try{k=decodeURIComponent(k)}catch{};const m=(Array.isArray(all)?all:[]).find(x=>key(x)===k);if(!m)return;if(hasAnalysis(m))ready++;if(strength(m)>=80)strong++;if(playable(m))play++});
    const small=g.querySelector('summary small');if(small){const base=(small.textContent||'').split(' · ')[0];small.textContent=`${base} · ${ready} policz. · ${strong} ≥80 · ${play} PLAYABLE`}
    if(state.collapsed)g.open=false;
  });
}
function filterAndSortDom(){
  const groups=document.querySelector('#app .p751-groups');if(!groups)return;
  [...groups.querySelectorAll('.p751-group')].forEach(g=>{
    const body=g.querySelector('.p751-group-body');if(!body)return;
    const cards=[...body.querySelectorAll('.p751-match-card')];
    cards.forEach(c=>{let k=c.dataset.p751Open||'';try{k=decodeURIComponent(k)}catch{};const m=(Array.isArray(all)?all:[]).find(x=>key(x)===k);c.hidden=!!(state.qualityOnly&&m&&!hasAnalysis(m));c.dataset.v944Score=m?String(qualityScore(m)):'0';c.dataset.v944Time=m?String(new Date(m.scheduled_time||'').getTime()||0):'0'});
    const shown=cards.filter(c=>!c.hidden).sort((a,b)=>state.sort==='quality'?Number(b.dataset.v944Score)-Number(a.dataset.v944Score):Number(a.dataset.v944Time)-Number(b.dataset.v944Time));
    shown.forEach(c=>body.appendChild(c));
    g.hidden=shown.length===0;
  });
}
function restoreScroll(){
  const y=num(state.scrollY);if(y!=null)requestAnimationFrame(()=>scrollTo(0,y));
}
function enhance(){enhanceFocus();decorateGroups();filterAndSortDom();restoreScroll()}
document.addEventListener('click',e=>{
  const q=e.target.closest('[data-v944-quality]');if(q){state.qualityOnly=!state.qualityOnly;save();window.TENIS_AI_MATCH_VISIBILITY_V916?.refresh?.();setTimeout(enhance,0);return}
  const s=e.target.closest('[data-v944-sort]');if(s){state.sort=state.sort==='quality'?'time':'quality';save();enhance();return}
  const open=e.target.closest('[data-p751-open]');if(open){state.scrollY=scrollY;state.openGroups=[...document.querySelectorAll('#app .p751-group')].map((g,i)=>g.open?i:null).filter(x=>x!=null);save()}
},true);
const oldRender=window.renderMatches;
if(typeof oldRender==='function')window.renderMatches=function(){const r=oldRender.apply(this,arguments);setTimeout(enhance,0);return r};
// Intercept the legacy LIVE focus and turn it into useful upcoming, analysed matches.
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-p751-focus="upcoming2h"]');if(!b)return;
  e.preventDefault();e.stopImmediatePropagation();
  document.querySelectorAll('#app .p751-match-card').forEach(c=>{let k=c.dataset.p751Open||'';try{k=decodeURIComponent(k)}catch{};const m=(Array.isArray(all)?all:[]).find(x=>key(x)===k);c.hidden=!m||!within2h(m)});
},true);
const collapse=document.querySelector('#collapse-all'),expand=document.querySelector('#expand-all');
collapse?.addEventListener('click',()=>{state.collapsed=true;save();setTimeout(enhance,0)});
expand?.addEventListener('click',()=>{state.collapsed=false;save()});
window.addEventListener('pagehide',()=>{if(document.querySelector('#app .p751-groups')){state.scrollY=scrollY;save()}});
window.addEventListener('pageshow',()=>setTimeout(enhance,0));
setTimeout(enhance,0);
window.TENIS_AI_MATCH_BROWSER_V944=Object.freeze({version:VERSION,hasAnalysis,within2h,qualityScore});
})();
