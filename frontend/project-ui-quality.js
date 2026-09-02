/* Tenis AI v8.8.15 — Project UI Quality Bridge
   Recommendation surfaces use FINAL Adaptive PROD + CORE Quality Lock.
   Full diagnostic markets remain visible in match analysis and SHADOW.
*/
(()=>{
'use strict';

const VERSION='v8.8.15';
const RUNTIME_FIX='v8.8.18';
const WRAP_KEY='__projectUiQualityV8815';
const STARTUP_SUPPRESS_MS=1250;
const bootClock=performance.now();
let userRenderPermit=0;

const num=x=>Number.isFinite(Number(x))?Number(x):null;
const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ');
const api=()=>window.TENIS_AI_MODEL_API||null;
const bridge=()=>window.TENIS_AI_PROJECT_UI||null;

function finalSignals(match,limit=20){
  const model=api();
  if(!match||typeof model?.signals!=='function')return [];
  try{return (model.signals(match,Math.max(1,Number(limit)||20))||[]).filter(x=>num(x?.v)!=null)}catch{return []}
}

function decodeKey(raw){
  try{return decodeURIComponent(String(raw||''))}catch{return String(raw||'')}
}

function matchFromElement(el){
  const key=decodeKey(el?.dataset?.p751Open||el?.closest?.('[data-p751-open]')?.dataset?.p751Open||'');
  if(!key)return null;
  try{return bridge()?.findMatch?.(key)||null}catch{return null}
}

function scoreText(v){
  v=num(v);
  return v==null?'—':`${Math.round(v)}/100`;
}

function setBars(root,v){
  v=num(v)||0;
  root?.querySelectorAll?.('.p751-bars i').forEach((bar,index)=>bar.classList.toggle('on',v>=(index+1)*18));
}

function shortTour(match){
  const x=String(match?.tour||'').trim();
  return x?x.toUpperCase():'TENIS';
}

function patchTopMeta(button,match,signal){
  button.querySelector('.pc882-top-meta')?.remove();
  if(!signal)return;

  let adaptive=null;
  try{adaptive=window.TENIS_AI_AUTOLEARN_V84?.scoreFor?.(match,signal)||null}catch{}
  let prior=null;
  try{prior=window.TENIS_AI_PERFORMANCE_V882?.priorFor?.(match,signal)||null}catch{}
  const delta=num(adaptive?.adaptive_delta_pp);

  const meta=document.createElement('small');
  meta.className='pc882-top-meta';
  meta.dataset.v8815FinalMeta='1';
  meta.textContent=[
    `${shortTour(match)} · ${String(match?.surface||'N/D').toUpperCase()}`,
    delta!=null?`Adaptive ${delta>=0?'+':''}${delta.toFixed(1)} pp`:null,
    Number(prior?.n||0)>=10&&num(prior?.accuracy)!=null?`hist ${Math.round(prior.accuracy)}% n=${prior.n}`:null,
    'FINAL Quality'
  ].filter(Boolean).join(' · ');
  button.append(meta);
}

function patchTopStrip(){
  const strip=document.querySelector('.p751-top');
  if(!strip)return false;

  [...strip.querySelectorAll('button[data-p751-open]')].forEach(button=>{
    const match=matchFromElement(button);
    const signal=finalSignals(match,1)[0]||null;
    const value=num(signal?.v);
    if(!match||!signal||value==null||value<72){button.remove();return}

    const label=button.querySelector('b');
    const score=button.querySelector('strong');
    if(label)label.textContent=String(signal.label||signal.pick||signal.key||'Sygnał FINAL');
    if(score)score.textContent=scoreText(value);
    setBars(button,value);
    patchTopMeta(button,match,signal);
  });

  const count=strip.querySelector('header span');
  const visible=strip.querySelectorAll('button[data-p751-open]').length;
  if(count)count.textContent=`${visible} najmocniejsze`;
  if(!visible)strip.remove();
  return true;
}

function patchMatchCards(){
  const strongOnly=!!document.querySelector('[data-p751-focus="strong"].active');
  [...document.querySelectorAll('.p751-match-card[data-p751-open]')].forEach(card=>{
    const match=matchFromElement(card);
    if(!match)return;
    const signals=finalSignals(match,20);
    const top=signals[0]||null;
    const value=num(top?.v);

    if(strongOnly&&(value==null||value<80)){card.remove();return}

    const pick=card.querySelector('.p751-top-pick');
    const pickLabel=pick?.querySelector('b');
    const pickScore=pick?.querySelector('em');
    if(pickLabel)pickLabel.textContent=top?String(top.label||top.pick||top.key||'Sygnał FINAL'):'Brak rynku CORE';
    if(pickScore)pickScore.textContent=scoreText(value);

    const strength=card.querySelector('.p751-strength');
    const strengthScore=strength?.querySelector('b');
    const greenCount=strength?.querySelector('small');
    if(strengthScore)strengthScore.textContent=scoreText(value);
    if(greenCount)greenCount.textContent=`${signals.filter(x=>Number(x.v)>=72).length} zielonych CORE`;
    setBars(strength,value);
  });

  if(strongOnly){
    document.querySelectorAll('.p751-group').forEach(group=>{
      const cards=group.querySelectorAll('.p751-match-card').length;
      if(!cards){group.remove();return}
      const small=group.querySelector('summary small');
      if(small)small.textContent=small.textContent.replace(/^\d+\s+mecz(?:ów)?/i,`${cards} ${cards===1?'mecz':'meczów'}`);
    });
  }
  return true;
}

function patchSignalPage(){
  const page=document.querySelector('.p751-signals-page');
  if(!page)return false;

  [...page.querySelectorAll('button[data-p751-open]')].forEach(button=>{
    const match=matchFromElement(button);
    if(!match){button.remove();return}
    const label=norm(button.querySelector('span')?.textContent||'');
    const candidate=finalSignals(match,40).find(x=>norm(x.label||x.pick||x.key)===label&&Number(x.v)>=68);
    if(!candidate){button.remove();return}
    const score=button.querySelector('strong');
    if(score)score.textContent=scoreText(candidate.v);
  });

  if(!page.querySelector('button[data-p751-open]')){
    const body=page.querySelector('header')?.nextElementSibling;
    if(body)body.innerHTML='<div class="p751-empty"><b>Brak sygnałów spełniających CORE Quality Lock.</b><span>Pełne dane diagnostyczne pozostają w analizie meczu i SHADOW.</span></div>';
  }
  return true;
}

function setVerdictArticle(article,label,signal){
  if(!article)return;
  const title=article.querySelector('span');
  const name=article.querySelector('b');
  const score=article.querySelector('strong');
  if(title)title.textContent=label;
  if(name)name.textContent=signal?String(signal.label||signal.pick||signal.key||'Sygnał FINAL'):'—';
  if(score)score.textContent=scoreText(signal?.v);
}

function patchVerdict(){
  const overlay=document.querySelector('#p751-match-overlay');
  const verdict=overlay?.querySelector('.p751-verdict');
  if(!overlay||overlay.hidden||!verdict)return false;
  const key=String(overlay.dataset.matchKey||'');
  let match=null;
  try{match=bridge()?.findMatch?.(key)||null}catch{}
  if(!match)return false;

  const selected=finalSignals(match,3);
  const articles=[...verdict.querySelectorAll('article')];
  setVerdictArticle(articles[0],'Najlepszy typ · FINAL',selected[0]);
  setVerdictArticle(articles[1],'Alternatywa · FINAL',selected[1]);

  const quality=articles[2];
  const value=num(selected[0]?.v);
  if(quality){
    const name=quality.querySelector('b');
    const score=quality.querySelector('strong');
    if(name)name.textContent=value==null?'Brak rynku CORE':value>=85?'Bardzo mocny':value>=72?'Mocny':'Umiarkowany';
    if(score)score.textContent=scoreText(value);
  }
  return true;
}

function markDiagnosticRow(row,suffix){
  if(!row)return;
  row.querySelectorAll('.hot').forEach(x=>x.classList.remove('hot'));
  const label=row.querySelector('span');
  if(label&&!label.dataset.v8815Diagnostic){
    label.dataset.v8815Diagnostic='1';
    label.textContent=`${label.textContent} · ${suffix}`;
  }
}

function patchDiagnosticCoreRows(){
  const overlay=document.querySelector('#p751-match-overlay');
  if(!overlay||overlay.hidden)return false;
  const key=String(overlay.dataset.matchKey||'');
  let match=null;
  try{match=bridge()?.findMatch?.(key)||null}catch{}
  if(!match)return false;

  const cpApi=window.TENIS_AI_CHECKPOINT_QUALITY_V887;
  const resultApi=window.TENIS_AI_RESULT_QUALITY_V889;
  [...overlay.querySelectorAll('.p751-market-row')].forEach(row=>{
    const label=String(row.querySelector('span')?.textContent||'');
    if(/^1:1 po 2 gemach/i.test(label)&&cpApi?.checkpointEligible?.('2',match)===false)markDiagnosticRow(row,'LAB / NIE CORE');
    if(/^2:2 po 4 gemach/i.test(label)&&cpApi?.checkpointEligible?.('4',match)===false)markDiagnosticRow(row,'LAB / NIE CORE');
    if(/^3:3 po 6 gemach/i.test(label)&&cpApi?.checkpointEligible?.('6',match)===false)markDiagnosticRow(row,'LAB / NIE CORE');
    if(/^Wygrany 1\. set/i.test(label)&&resultApi?.eligible?.('set1_winner')===false)markDiagnosticRow(row,'DIAGNOSTYKA / NIE CORE');
    if(/^Wygrany mecz/i.test(label)&&resultApi?.eligible?.('match_winner')===false)markDiagnosticRow(row,'DIAGNOSTYKA / NIE CORE');
  });
  return true;
}

function patchServePropsHonesty(){
  const overlay=document.querySelector('#p751-match-overlay');
  if(!overlay||overlay.hidden)return false;
  const details=[...overlay.querySelectorAll('details.p751-acc')].find(d=>/Asy i podwójne błędy/i.test(String(d.querySelector('summary b')?.textContent||'')));
  if(!details)return false;

  const summaryTag=details.querySelector('summary em');
  if(summaryTag)summaryTag.textContent='LAB · N/D';
  const summarySmall=details.querySelector('summary small');
  if(summarySmall)summarySmall.textContent='model count · niekalibrowany';

  const note=details.querySelector('.p751-acc-body > .p751-note');
  if(note)note.textContent='Wpisz linię buka. OVER/UNDER to wynik niekalibrowanego modelu count; kurs modelowy nie jest potwierdzonym fair oddsem i nie wchodzi do CORE.';

  details.querySelectorAll('.sp72-market').forEach(card=>{
    card.classList.remove('strong','lean');
    const head=card.querySelector('.sp72-market-head span');
    if(head&& !/LAB/i.test(head.textContent||''))head.textContent=`LAB · ${head.textContent}`;
  });
  details.dataset.v8818ServeLab='1';
  return true;
}

function patchExactScoreHonesty(){
  const overlay=document.querySelector('#p751-match-overlay');
  if(!overlay||overlay.hidden)return false;
  let changed=false;
  overlay.querySelectorAll('.p751-model-grid article').forEach(article=>{
    const title=article.querySelector('h4');
    if(!title||!/Dokładny wynik/i.test(String(title.textContent||'')))return;
    if(!title.dataset.v8818ExactLab){
      title.dataset.v8818ExactLab='1';
      title.textContent='Dokładny wynik · MODEL LAB · N/D';
    }
    article.querySelectorAll('.hot,.strong,.lean').forEach(x=>x.classList.remove('hot','strong','lean'));
    let note=article.querySelector('[data-v8818-exact-note]');
    if(!note){
      note=document.createElement('small');
      note.dataset.v8818ExactNote='1';
      note.textContent='Brak osobnej telemetrii FINAL — diagnostyka, nie CORE.';
      article.append(note);
    }
    changed=true;
  });
  return changed;
}

function patchProjectHome(){
  patchTopStrip();
  patchMatchCards();
}

function patchProjectDetail(){
  patchVerdict();
  patchDiagnosticCoreRows();
  patchServePropsHonesty();
  patchExactScoreHonesty();
}

function patchAll(){
  patchProjectHome();
  patchSignalPage();
  patchProjectDetail();
}

function startupRenderShouldBeSuppressed(){
  if(performance.now()-bootClock>=STARTUP_SUPPRESS_MS)return false;
  if(userRenderPermit>0)return false;
  return !!document.querySelector('#app .p751-match-card, #app .p751-empty, #app .p751-groups');
}

function wrapRenderMatches(){
  const current=window.renderMatches;
  if(typeof current!=='function'||current[WRAP_KEY])return false;
  const wrapped=function(...args){
    if(startupRenderShouldBeSuppressed()){
      queueMicrotask(patchProjectHome);
      return undefined;
    }
    if(userRenderPermit>0)userRenderPermit-=1;
    const result=current.apply(this,args);
    queueMicrotask(patchProjectHome);
    return result;
  };
  Object.defineProperty(wrapped,WRAP_KEY,{value:true});
  window.renderMatches=wrapped;
  return true;
}

function wrapProjectOpen(){
  const project=bridge();
  if(!project||project[WRAP_KEY]||typeof project.openMatch!=='function')return false;
  const open=project.openMatch;
  project.openMatch=(...args)=>{
    const result=open.apply(project,args);
    queueMicrotask(patchProjectDetail);
    return result;
  };
  Object.defineProperty(project,WRAP_KEY,{value:true});
  return true;
}

function isUserRenderControl(event){
  return !!event.target?.closest?.('[data-p751-focus],[data-filter],[data-view="matches"],[data-p751-nav="matches"]');
}

function boot(){
  wrapRenderMatches();
  wrapProjectOpen();
  patchAll();

  document.addEventListener('click',event=>{
    if(isUserRenderControl(event))userRenderPermit=1;
    if(event.target?.closest?.('[data-p751-open],[data-p751-focus],[data-p751-nav="signals"],[data-view="matches"],[data-filter]')){
      requestAnimationFrame(patchAll);
    }
  },true);

  document.addEventListener('tenis-ai:stats-ready',()=>queueMicrotask(patchProjectHome));
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_PROJECT_UI_QUALITY_V8815=Object.freeze({
  version:VERSION,
  runtimeFix:RUNTIME_FIX,
  finalSignals,
  patchAll,
  patchHome:patchProjectHome,
  patchDetail:patchProjectDetail
});
})();