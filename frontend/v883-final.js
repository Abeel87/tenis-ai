/* Tenis AI v8.8.3 · final UI cleanup.
   No model math changes. This layer only unifies visible versioning,
   removes legacy stats clutter and exposes Pair Selector reasoning.
   v8.8.20 runtime cleanup: explicit events replace delayed global polish loops.
*/
(()=>{
'use strict';

const VERSION='v8.8.3';
const RUNTIME_FIX='v8.8.20';
const DRAFT_KEY='tenis-ai-v82a-scenario-draft';
const WRAP_KEY='__v883EventDriven';
const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));
const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');

const PAIR_LABELS={
  SET1_WIN_OVER:'1. set: zwycięzca + OVER gemów',
  SET1_WIN_TOTAL:'1. set: zwycięzca + suma gemów',
  EARLY_HOLD_JOINT:'1. set + wczesny checkpoint',
  MATCH_AND_SET_WIN:'Mecz + 1. set: ten sam kierunek',
  DOUBLE_TOTAL_OVER:'OVER 1. seta + OVER meczu',
  MATCH_DIRECTION_TOTAL:'Kierunek meczu + suma gemów',
  DIVERSE_PAIR:'Dwa różne rynki',
  NEUTRAL_PAIR:'Para neutralna'
};

const REASON_LABELS={
  '1S winner + 1S over':'kierunek 1. seta + over',
  '1S winner + 1S total':'kierunek 1. seta + suma gemów',
  '1S winner + early checkpoint':'kierunek 1. seta + checkpoint',
  'match winner + 1S winner':'zwycięzca meczu + zwycięzca 1. seta',
  '1S over + match over':'over 1. seta + over meczu',
  'match direction + total':'kierunek meczu + suma gemów',
  'rozne kategorie':'różne kategorie',
  'neutralna para':'neutralna para'
};

function loadDraft(){
  try{
    const x=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');
    return x&&Array.isArray(x.items)?x:{items:[],profile:'manual'};
  }catch{
    return {items:[],profile:'manual'};
  }
}

function draftGroups(){
  const d=loadDraft();
  const map=new Map();
  d.items.forEach(item=>{
    const key=String(item?.match_key||'');
    if(!key)return;
    if(!map.has(key))map.set(key,{match_key:key,items:[],profile:d.profile||'manual'});
    map.get(key).items.push(item);
  });
  return [...map.values()];
}

function signalLine(s){
  const direct=num(s?.line??s?.selected_line??s?.suggested_line);
  if(direct!=null)return direct;
  const parts=String(s?.key||s?.signal_key||'').split('|');
  return num(parts?.[1]);
}

function findSignal(match,item){
  const api=window.TENIS_AI_MODEL_API;
  let rows=[];
  try{rows=api?.allSignals?.(match)||[]}catch{}
  const key=String(item?.signal_key||'');
  const market=String(item?.market||'').toLowerCase();
  const pick=norm(item?.pick);
  const line=num(item?.selected_line??item?.suggested_line);
  return rows.find(s=>{
    if(key&&String(s?.key||s?.signal_key||'')===key)return true;
    if(String(s?.market||'').toLowerCase()!==market)return false;
    if(norm(s?.pick)!==pick)return false;
    if(line!=null){
      const sl=signalLine(s);
      if(sl==null||Math.abs(sl-line)>.001)return false;
    }
    return true;
  })||null;
}

function historyForGroup(group){
  const bridge=window.TENIS_AI_PROJECT_UI;
  const perf=window.TENIS_AI_PERFORMANCE_V882;
  if(!bridge?.findMatch||!perf?.priorFor)return null;

  let match=null;
  try{match=bridge.findMatch(group.match_key)}catch{}
  if(!match)return null;

  const priors=[];
  group.items.forEach(item=>{
    const signal=findSignal(match,item);
    if(!signal)return;
    try{
      const p=perf.priorFor(match,signal);
      if(p?.n>=10&&num(p?.accuracy)!=null)priors.push(p);
    }catch{}
  });

  return priors.length?{min:Math.min(...priors.map(x=>x.accuracy)),max:Math.max(...priors.map(x=>x.accuracy)),n:Math.min(...priors.map(x=>x.n)),covered:priors.length,total:group.items.length}:null;
}

function clarifyScenarioScores(){
  document.querySelectorAll('.sc82-draft-entry .sc82-draft-row small').forEach(el=>{
    const t=String(el.textContent||'');
    const next=t
      .replace(/\bRanking\s+(\d+(?:\.\d+)?\/100)/g,'Composer $1')
      .replace(/\bFINAL\s+(\d+(?:\.\d+)?\/100)/g,'Model FINAL $1');
    if(next!==t)el.textContent=next;
  });

  const score=document.querySelector('.sc82-score');
  if(score){
    const label=score.querySelector(':scope > span');
    if(label)label.textContent='Ocena scenariusza · Composer';

    let note=document.querySelector('.sc883-score-note');
    if(!note){
      note=document.createElement('div');
      note.className='sc883-score-note';
      note.innerHTML='<b>Jak czytać te liczby?</b><span><strong>Model FINAL</strong> = wynik produkcyjnego modelu Adaptive. <strong>Composer</strong> = ocena używana do rankingu po jakości danych, zgodności modeli i profilu. <strong>Ocena scenariusza</strong> = średnia ocen Composer pomniejszona o kary za powtarzalność. To nie są gwarantowane prawdopodobieństwa.</span>';
      score.insertAdjacentElement('afterend',note);
    }
  }

  document.querySelectorAll('.sc82-saved-score').forEach(row=>{
    const b=row.querySelector('b');
    if(!b||row.querySelector('.sc883-saved-label'))return;
    const label=document.createElement('small');
    label.className='sc883-saved-label';
    label.textContent='COMPOSER';
    b.insertAdjacentElement('beforebegin',label);
  });
}

function decorateGeneratorCards(){
  clarifyScenarioScores();
  const cards=[...document.querySelectorAll('.sc82-draft-list article')];
  if(!cards.length)return;
  const groups=draftGroups();

  cards.forEach((card,i)=>{
    card.querySelector('.sc883-pairbar')?.remove();
    const group=groups[i];
    if(!group)return;

    const first=group.items.find(x=>num(x?.selector_match_score)!=null)||group.items[0];
    const pairScore=num(first?.selector_match_score);
    const pairType=String(first?.selector_pair||'');
    const pairReason=String(first?.selector_reason||'');
    if(pairScore==null&&!pairType)return;

    const hist=historyForGroup(group);
    const shadow=String(first?.selector_mode||'').toUpperCase().includes('SHADOW')||
      String(group.profile||'').toLowerCase()==='experimental';

    const meta=document.createElement('div');
    meta.className='sc883-pairbar';
    meta.innerHTML=`
      <span><small>PAIR SELECTOR · RANKING</small><b>${pairScore==null?'N/D':Math.round(pairScore)+'/100'}</b></span>
      <span class="wide"><small>DLACZEGO TEN MECZ</small><b>${esc(PAIR_LABELS[pairType]||REASON_LABELS[pairReason]||pairReason||'najlepsza spójna para')}</b></span>
      <span><small>HISTORIA ZDARZEŃ · NIE PARY</small><b>${hist?`${Math.round(hist.min)}–${Math.round(hist.max)}% · min n=${hist.n} · ${hist.covered}/${hist.total} zdarzeń`:'brak mocnej próbki'}</b></span>
      <em class="${shadow?'shadow':'prod'}">${shadow?'MODEL TEST · SHADOW':'CORE · PROD'}</em>
    `;

    const head=card.firstElementChild;
    if(head)head.insertAdjacentElement('afterend',meta);
    else card.prepend(meta);
  });

  const gh=document.querySelector('.sc88-generator-head');
  if(gh){
    const tag=gh.querySelector('span');
    if(tag)tag.textContent='GENERATOR AI '+(window.TENIS_AI_META?.displayVersion||VERSION);
    const title=gh.querySelector('b');
    if(title)title.textContent='Pair-first + Adaptive PROD';
    const small=gh.querySelector('small');
    if(small)small.textContent='Najpierw najlepsza para rynków, potem ranking meczu. Historia wpływa tylko na selekcję.';
  }
}

function cleanupStats(){
  document.querySelectorAll('#pc88-dashboard').forEach(x=>x.remove());

  const host=document.querySelector('#pc77');
  const dash=document.querySelector('#pc882-dashboard');
  if(!host||!dash)return;

  const title=dash.querySelector('.pc882-head span');
  if(title)title.textContent='CENTRUM SKUTECZNOŚCI';

  let legacy=host.querySelector('#pc882-legacy');
  if(!legacy){
    legacy=document.createElement('details');
    legacy.id='pc882-legacy';
    legacy.className='pc882-legacy';
    legacy.innerHTML='<summary><b>PRO / pełna diagnostyka</b><span>starsze tabele, Player SH, telemetry i audyt</span></summary><div class="pc882-legacy-body"></div>';
    host.append(legacy);
  }else{
    const b=legacy.querySelector('summary b');
    const s=legacy.querySelector('summary span');
    if(b)b.textContent='PRO / pełna diagnostyka';
    if(s)s.textContent='starsze tabele, Player SH, telemetry i audyt';
  }

  const body=legacy.querySelector('.pc882-legacy-body');
  if(!body)return;
  const head=host.querySelector('.pc77-head');

  [...host.children].forEach(node=>{
    if(node===head||node===dash||node===legacy||node.id==='coh892-shadow')return;
    body.append(node);
  });
}

function brand(){
  window.TENIS_AI_APPLY_META?.();
  document.documentElement.dataset.tenisAiFeatureVersion=window.TENIS_AI_META?.displayVersion||VERSION;

  const footer=document.querySelector('footer');
  if(footer){
    const lines=[...footer.children];
    if(lines[1])lines[1].textContent=(window.TENIS_AI_META?.displayVersion||VERSION)+' · Adaptive PROD + Pair Selector + Analytics · Player Intelligence i Accuracy Lab pozostają SHADOW.';
  }
}

function compactAdaptive(){
  const h=document.querySelector('#v79-health');
  if(!h)return;
  let expanded='0';
  try{expanded=localStorage.getItem('tenis-ai-v882-adaptive-expanded')||'0'}catch{}
  if(expanded!=='1')h.classList.remove('expanded');
}

function polish(){
  brand();
  compactAdaptive();
  clarifyScenarioScores();
  decorateGeneratorCards();
  cleanupStats();
}

function wrapScenarioOpen(){
  const api=window.TENIS_AI_SCENARIOS;
  if(!api||api[WRAP_KEY]||typeof api.open!=='function')return false;
  const open=api.open;
  api.open=(...args)=>{
    const result=open.apply(api,args);
    queueMicrotask(decorateGeneratorCards);
    return result;
  };
  Object.defineProperty(api,WRAP_KEY,{value:true});
  return true;
}

function scenarioClick(event){
  return !!event.target?.closest?.('#scenario-v82a-panel,[data-p751-nav="scenarios"]');
}

function boot(){
  brand();
  compactAdaptive();
  wrapScenarioOpen();
  clarifyScenarioScores();
  decorateGeneratorCards();
  cleanupStats();
}

document.addEventListener('tenis-ai:stats-ready',()=>queueMicrotask(cleanupStats));
document.addEventListener('tenis-ai:stats-dashboard-ready',()=>queueMicrotask(cleanupStats));
document.addEventListener('click',event=>{
  if(!scenarioClick(event))return;
  requestAnimationFrame(()=>{
    wrapScenarioOpen();
    clarifyScenarioScores();
    decorateGeneratorCards();
  });
},true);
document.addEventListener('visibilitychange',()=>{
  if(document.hidden)return;
  brand();
  compactAdaptive();
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_V883=Object.freeze({
  version:VERSION,
  runtimeFix:RUNTIME_FIX,
  polish,
  cleanupStats,
  clarifyScenarioScores,
  decorateGeneratorCards,
  wrapScenarioOpen
});
})();
