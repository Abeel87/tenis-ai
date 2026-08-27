/* Tenis AI v8.8.3 ? final UI cleanup.
   No model math changes. This layer only unifies visible versioning,
   removes legacy stats clutter and exposes Pair Selector reasoning. */
(()=>{
'use strict';

const VERSION='v8.8.3';
const DRAFT_KEY='tenis-ai-v82a-scenario-draft';
const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));
const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');

const PAIR_LABELS={
  SET1_WIN_OVER:'1. set: zwyci?zca + OVER gem?w',
  SET1_WIN_TOTAL:'1. set: zwyci?zca + suma gem?w',
  EARLY_HOLD_JOINT:'1. set + wczesny checkpoint',
  MATCH_AND_SET_WIN:'Mecz + 1. set: ten sam kierunek',
  DOUBLE_TOTAL_OVER:'OVER 1. seta + OVER meczu',
  MATCH_DIRECTION_TOTAL:'Kierunek meczu + suma gem?w',
  DIVERSE_PAIR:'Dwa r??ne rynki',
  NEUTRAL_PAIR:'Para neutralna'
};

const REASON_LABELS={
  '1S winner + 1S over':'kierunek 1. seta + over',
  '1S winner + 1S total':'kierunek 1. seta + suma gem?w',
  '1S winner + early checkpoint':'kierunek 1. seta + checkpoint',
  'match winner + 1S winner':'zwyci?zca meczu + zwyci?zca 1. seta',
  '1S over + match over':'over 1. seta + over meczu',
  'match direction + total':'kierunek meczu + suma gem?w',
  'rozne kategorie':'r??ne kategorie',
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

  return priors.sort((a,b)=>Number(b.n||0)-Number(a.n||0))[0]||null;
}

function decorateGeneratorCards(){
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
      <span><small>PAIR SCORE</small><b>${pairScore==null?'N/D':Math.round(pairScore)+'/100'}</b></span>
      <span class="wide"><small>DLACZEGO TEN MECZ</small><b>${esc(PAIR_LABELS[pairType]||REASON_LABELS[pairReason]||pairReason||'najlepsza sp?jna para')}</b></span>
      <span><small>HISTORIA</small><b>${hist?`${Math.round(Number(hist.accuracy))}% ? n=${Number(hist.n)}`:'brak mocnej pr?bki'}</b></span>
      <em class="${shadow?'shadow':'prod'}">${shadow?'MODEL TEST ? SHADOW':'CORE ? PROD'}</em>
    `;

    const head=card.firstElementChild;
    if(head)head.insertAdjacentElement('afterend',meta);
    else card.prepend(meta);
  });

  const gh=document.querySelector('.sc88-generator-head');
  if(gh){
    const tag=gh.querySelector('span');
    if(tag)tag.textContent='GENERATOR AI v8.8.3';
    const title=gh.querySelector('b');
    if(title)title.textContent='Pair-first + Adaptive PROD';
    const small=gh.querySelector('small');
    if(small)small.textContent='Najpierw najlepsza para rynk?w, potem ranking meczu. Historia wp?ywa tylko na selekcj?.';
  }
}

function cleanupStats(){
  document.querySelectorAll('#pc88-dashboard').forEach(x=>x.remove());

  const host=document.querySelector('#pc77');
  const dash=document.querySelector('#pc882-dashboard');
  if(!host||!dash)return;

  const title=dash.querySelector('.pc882-head span');
  if(title)title.textContent='CENTRUM SKUTECZNO?CI v8.8.3';

  let legacy=host.querySelector('#pc882-legacy');
  if(!legacy){
    legacy=document.createElement('details');
    legacy.id='pc882-legacy';
    legacy.className='pc882-legacy';
    legacy.innerHTML='<summary><b>PRO / pe?na diagnostyka</b><span>starsze tabele, Player SH, telemetry i audyt</span></summary><div class="pc882-legacy-body"></div>';
    host.append(legacy);
  }else{
    const b=legacy.querySelector('summary b');
    const s=legacy.querySelector('summary span');
    if(b)b.textContent='PRO / pe?na diagnostyka';
    if(s)s.textContent='starsze tabele, Player SH, telemetry i audyt';
  }

  const body=legacy.querySelector('.pc882-legacy-body');
  if(!body)return;
  const head=host.querySelector('.pc77-head');

  [...host.children].forEach(node=>{
    if(node===head||node===dash||node===legacy)return;
    body.append(node);
  });
}

function brand(){
  document.documentElement.dataset.tenisAiFeatureVersion=VERSION;
  document.title='Tenis AI ? v8.8.3';

  const p=document.querySelector('.brand-copy p');
  if(p)p.textContent='Tenis AI v8.8.3 ? Adaptive PROD + Pair Selector + Analytics';

  const footer=document.querySelector('footer');
  if(footer){
    const lines=[...footer.children];
    if(lines[1])lines[1].textContent='v8.8.3 ? Adaptive PROD + Pair Selector + Analytics ? Player Intelligence i Accuracy Lab pozostaj? SHADOW.';
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
  decorateGeneratorCards();
  cleanupStats();
}

function boot(){
  polish();
  [120,350,800,1500,2600].forEach(ms=>setTimeout(polish,ms));
}

document.addEventListener('click',()=>setTimeout(polish,70),true);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(polish,50)});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_V883=Object.freeze({
  version:VERSION,
  polish,
  cleanupStats,
  decorateGeneratorCards
});
})();
