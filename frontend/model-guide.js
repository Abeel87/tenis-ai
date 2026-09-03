/* Tenis AI v8.7DC1 — Match Decision Center. UI-only; model/tracker math untouched. */
(()=>{
'use strict';

const VERSION='v8.7DC1';
const TOP_LIMIT=8;
const number=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
const matchKey=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));
const allMatches=()=>{try{return Array.isArray(all)?all:[]}catch{return[]}};
const alias=x=>({match_winner:'match_win',set1_winner:'set1_win',set2_winner:'set2_win',set3_winner:'set3_win'})[String(x||'').toLowerCase()]||String(x||'').toLowerCase();

const CATEGORY_META={
  result:{label:'Wynik',long:'Wynik meczu i setów',icon:'🏆'},
  games:{label:'Gemy',long:'Gemy i linie O/U',icon:'🎾'},
  checkpoints:{label:'Po 2/4/6',long:'Wynik po 2 / 4 / 6 gemach',icon:'⏱'},
  special:{label:'Specjalne',long:'Rynki specjalne',icon:'✨'}
};
const FILTERS=[['all','Wszystkie'],['result','Wynik'],['games','Gemy'],['checkpoints','Po 2/4/6'],['special','Specjalne']];
const MODEL_DEFS=[
  ['current','Current'],
  ['catboost','CatBoost'],
  ['tabpfn','TabPFN'],
  ['ensemble','Ensemble'],
  ['adaptive-prod','Adaptive'],
  ['adaptive-base','Adaptive baza'],
  ['early','Early'],
  ['serve','Serve'],
  ['form','Form'],
  ['surface','Surface'],
  ['consensus','Consensus'],
  ['player','Player SH','SHADOW'],
  ['lab','Market Lab','SHADOW'],
  ['joint','Joint']
];

const stateOf=s=>{
  const a=String(s||'').split(':').map(Number);
  return a.length===2&&a.every(Number.isFinite)?a[0]===a[1]?'draw':a[0]>a[1]?'p1_lead':'p2_lead':null;
};
const aggregateState=(o,k)=>{
  const a=Object.entries(o||{}).map(([x,v])=>[x,number(v)]).filter(([,v])=>v!=null);
  const total=a.reduce((z,[,v])=>z+Math.max(0,v),0);
  return total?a.filter(([x])=>stateOf(x)===k).reduce((z,[,v])=>z+Math.max(0,v),0)/total*100:null;
};
const signalLine=s=>{
  const direct=number(s?.line??s?.selected_line??s?.suggested_line);
  if(direct!=null)return String(direct);
  const parts=String(s?.key||s?.signal_key||'').split('|');
  return parts.length>1&&/^\d+(\.\d+)?$/.test(parts[1])?parts[1]:'';
};

function buildRows(m){
  const out=[],seen=new Map();
  const add=row=>{
    const key=[row.category,row.market,row.pick,row.line||'',row.extra||''].join('|');
    if(seen.has(key)){
      const existing=seen.get(key);
      ['base','lab','joint'].forEach(field=>{if(number(row[field])!=null)existing[field]=row[field]});
      return existing;
    }
    row.order=out.length;
    seen.set(key,row);
    out.push(row);
    return row;
  };
  const objectMarket=(category,market,label,o)=>Object.entries(o||{}).forEach(([pick,value])=>{
    if(number(value)!=null)add({category,market,label,pick,base:Number(value)});
  });
  const overUnder=(market,label,o,category='games',field='base')=>Object.entries(o||{}).forEach(([line,x])=>{
    if((market==='set1_total'||market==='set2_total')&&String(line)==='11.5')return;
    ['over','under'].forEach(pick=>{
      if(number(x?.[pick])!=null)add({category,market,label:label+' '+line,pick,line:String(line),[field]:Number(x[pick])});
    });
  });

  objectMarket('result','match_win','Kto wygra mecz',m.match_win);

  // Missing base probabilities must not be fabricated from a candidate score.
  (m?.autolearn_v84?.signals||[]).forEach(signal=>{
    if(alias(signal.market)==='match_win'&&!out.some(row=>row.market==='match_win'&&norm(row.pick)===norm(signal.pick))){
      add({category:'result',market:'match_win',label:'Kto wygra mecz',pick:signal.pick});
    }
  });
  objectMarket('result','set1_win','Kto wygra 1. set',m.first_set_win);
  objectMarket('result','set2_win','Kto wygra 2. set',m.second_set_win);
  objectMarket('result','set3_win','Kto wygra 3. set',m.third_set_win);
  objectMarket('result','total_sets','Liczba setów',m.total_sets);
  objectMarket('result','exact_match_score','Dokładny wynik',m.exact_match_score);
  overUnder('set1_total','1. set · gemy',m.over_under);
  overUnder('match_total','Mecz · gemy',m.match_over_under);

  ['2','4','6'].forEach(games=>{
    const values=m.game_states?.[games];
    if(!values)return;
    Object.entries(values).forEach(([pick,value])=>{
      add({category:'checkpoints',market:'state'+games,label:'Po '+games+' gemach',
        pick,displayPick:pick,checkpoint:Number(games),base:number(value),state:true});
    });
  });

  const lab=m.market_lab_v741||{};
  overUnder('set1_total','1. set · gemy',lab.set1_total,'games','lab');
  overUnder('set2_total','2. set · gemy',lab.set2_total,'games','lab');
  Object.entries(lab.player_total_games||{}).forEach(([player,lines])=>Object.entries(lines||{}).forEach(([line,x])=>{
    ['over','under'].forEach(pick=>{
      if(number(x?.[pick])!=null)add({category:'games',market:'player_total_games',label:player+' · gemy '+line,pick,line:String(line),extra:player,lab:Number(x[pick])});
    });
  }));
  const yesNo=(market,label,x)=>{
    const yes=number(x?.yes??x),no=number(x?.no);
    if(yes==null)return;
    add({category:'special',market,label,pick:'yes',displayPick:'TAK',lab:yes});
    add({category:'special',market,label,pick:'no',displayPick:'NIE',lab:no??(yes<=100?100-yes:null)});
  };
  yesNo('set1_exact_six_games','Dokładnie 6 gemów 1S',lab.set1_exact_six_games);
  yesNo('set1_tiebreak','Tie-break 1S',lab.set1_tiebreak);
  yesNo('match_tiebreak','Tie-break w meczu',lab.match_tiebreak);
  yesNo('both_players_win_set','Obaj wygrają seta',lab.both_players_win_set);
  Object.entries(lab.tiebreak_count||{}).forEach(([pick,value])=>{
    if(number(value)!=null)add({category:'special',market:'tiebreak_count',label:'Liczba tie-breaków',pick,lab:Number(value)});
  });
  const combo=(set,o)=>['p1','p2'].forEach(side=>['under','over'].forEach(pick=>{
    const value=number(o?.[side]?.[pick]);
    if(value!=null)add({
      category:'special',
      market:set+'_winner_player_games_6_5',
      label:(set==='set1'?'1.':'2.')+' set · zwycięzca + gemy',
      pick:side+'|'+pick,
      displayPick:(side==='p1'?m.p1:m.p2)+' + '+(pick==='under'?'U':'O')+'6.5',
      lab:value
    });
  }));
  combo('set1',lab.set1_winner_player_games_6_5);
  combo('set2',lab.set2_winner_player_games_6_5);

  const joint=m.joint_builder_v78b;
  if(joint?.status==='READY'){
    const best=joint.best||{},player=String(best.player||'');
    const side=norm(player)===norm(m.p1)?'p1':norm(player)===norm(m.p2)?'p2':null;
    const sideData=side?joint[side]||{}:{};
    if(side){
      let row=out.find(x=>x.market==='state6'&&x.pick===side+'_lead');
      if(row)row.joint=number(sideData.lead_after_6);
      row=out.find(x=>x.market==='set1_total'&&x.line==='8.5'&&x.pick==='over');
      if(row)row.joint=number(sideData.over_8_5_set1);
      row=out.find(x=>x.market==='set1_win'&&norm(x.pick)===norm(player));
      if(row)row.joint=number(sideData.win_set1);
    }
    add({
      category:'special',
      market:'joint_3of3',
      label:'Joint 3/3',
      pick:player||'—',
      displayPick:(player||'—')+' · lead6 + O8.5 + win1S',
      joint:number(best.joint_all_3)
    });
  }
  return out;
}

function specialistSets(m){
  const api=window.TENIS_AI_MODEL_API,ids=['adaptive','early','serve','form','surface'];
  const out=Object.fromEntries(ids.map(id=>{
    try{return[id,api?.signalsFor?.(id,m)||[]]}catch{return[id,[]]}
  }));
  out.consensus=(m?.specialist_signals_v79b_current||[]).filter(x=>x?.source_model==='consensus');
  return out;
}
function signalMatches(row,signal){
  if(row.state){
    const cp=signal?.checkpoint??String(signal?.market||'').match(/^state([246])$/)?.[1]??String(signal?.key||'').split('|')[1];
    return ['game_state','state'+row.checkpoint].includes(signal?.market)&&
      Number(cp)===row.checkpoint&&norm(signal?.pick)===norm(row.pick);
  }
  if(alias(signal?.market)!==alias(row.market))return false;
  if(row.market==='player_total_games')return false;
  if(row.line&&signalLine(signal)!==String(row.line))return false;
  return norm(signal?.pick)===norm(row.pick);
}
const findSignal=(row,list)=>(list||[]).find(signal=>signalMatches(row,signal))||null;
const autoSignal=(row,m)=>findSignal(row,m?.autolearn_v84?.signals);
const learningSignal=(row,m)=>findSignal(row,m?.adaptive_learning_v79?.signals);

function adaptiveInfo(row,m){
  const auto=autoSignal(row,m);
  const prod=auto?.adaptive_prod_v79||{};
  const declaredMode=String(prod.mode||m?.adaptive_learning_v79?.mode||'PROD').toUpperCase();
  const raw=number(auto?.ensemble_raw??auto?.raw_score??prod.raw_score??auto?.ensemble);
  const final=number(auto?.final_score??auto?.adaptive_prod_score??prod.final_score);
  return {
    raw,
    final,
    delta:number(auto?.adaptive_delta_pp??prod.delta_pp),
    mode:'PROD',
    legacyMode:declaredMode!=='PROD',
    status:String(prod.status||m?.adaptive_learning_v79?.status||'COLLECTING').toUpperCase(),
    evidence:number(prod.evidence),
    applied:prod.applied,
    cap:number(prod.cap_pp),
    similar:number(prod.similar_n),
    accuracy:number(prod.historical_accuracy),
    action:prod.action,
    lesson:prod.lesson
  };
}
function modelValue(row,id,sets,m){
  const auto=autoSignal(row,m),adaptive=adaptiveInfo(row,m);
  if(id==='adaptive-base'){
    if(number(row.base)!=null)return[number(row.base),'%'];
    const found=findSignal(row,sets.adaptive);
    return found?[number(found.v),'%',row.state?found.pick:'']:null;
  }
  if(['early','serve','form','surface','consensus'].includes(id)){
    const found=findSignal(row,sets[id]),score=number(found?.score??found?.v);
    return score==null?null:[score,'/100',row.state?found.pick:''];
  }
  if(['current','catboost','tabpfn'].includes(id))return number(auto?.[id])==null?null:[number(auto[id]),'/100'];
  if(id==='ensemble')return adaptive.raw==null?null:[adaptive.raw,'/100',auto?.dynamic_weighting?.active?'DYN':'RAW'];
  if(id==='adaptive-prod'){
    if(adaptive.final!=null)return[adaptive.final,'/100',adaptive.status];
    return null;
  }
  if(id==='player')return number(auto?.player_intelligence_v85?.shadow_score)==null?null:[number(auto.player_intelligence_v85.shadow_score),'%'];
  if(id==='lab')return number(row.lab)==null?null:[number(row.lab),'%'];
  if(id==='joint')return number(row.joint)==null?null:[number(row.joint),'%'];
  return null;
}
function finalScore(row,m,sets){
  return adaptiveInfo(row,m).final;
}
const scoreText=(value,unit='/100')=>number(value)==null?'—':Number(value).toFixed(1).replace('.0','')+unit;
const pickText=row=>String(row.displayPick||row.pick||'—').toUpperCase();

function modelCell(row,definition,sets,m){
  const id=definition[0],label=definition[1],badge=definition[2];
  const value=modelValue(row,id,sets,m),has=!!value&&number(value[0])!=null;
  return '<div class="dc87-model '+(has?'':'nd')+' '+(id==='adaptive-prod'?'adaptive':'')+'">'+
    '<small>'+esc(label)+(badge?'<span>'+esc(badge)+'</span>':'')+'</small>'+
    '<b>'+(has?scoreText(value[0],value[1]):'N/D')+(has&&value[2]?' · '+esc(value[2]):'')+'</b></div>';
}
function adaptiveMeta(info){
  const fields=[
    ['Status',info.mode+' · '+info.status+(info.legacyMode?' · SYNC':'')],
    ['Próbka',info.similar==null?null:'n='+info.similar],
    ['Historyczna trafność',info.accuracy==null?null:scoreText(info.accuracy,'%')],
    ['Limit korekty',info.cap==null?null:'±'+info.cap+' pp'],
    ['Zastosowano',info.applied==null?null:(info.applied?'TAK':'NIE')],
    ['Akcja',info.action]
  ].filter(([,value])=>value!=null&&value!=='');
  if(!fields.length&&!info.lesson)return'';
  return '<div class="dc87-adaptive-meta">'+fields.map(([label,value])=>'<span>'+esc(label)+' <b>'+esc(value)+'</b></span>').join('')+
    (info.lesson?'<span class="dc87-lesson">Lekcja: <b>'+esc(info.lesson)+'</b></span>':'')+'</div>';
}
function flow(row,m,sets){
  const info=adaptiveInfo(row,m),score=finalScore(row,m,sets);
  if(info.raw!=null){
    const delta=info.delta==null?'bez przeliczeń w UI':(info.delta>0?'+':'')+info.delta.toFixed(1)+' pp';
    return '<div class="dc87-flow"><span>RAW Ensemble<b>'+scoreText(info.raw)+'</b></span><i>→</i>'+
      '<span class="after">Po Adaptive<b>'+scoreText(info.final)+'</b></span>'+
      '<em class="'+(info.delta>0?'up':info.delta<0?'down':'')+'">'+esc(delta)+'</em></div>';
  }
  return '<div class="dc87-flow"><span>Model bazowy<b>'+scoreText(row.base,'%')+'</b></span><i>→</i>'+
    '<span class="after">Źródło<b>'+(number(row.base)!=null?'Adaptive baza':'N/D')+'</b></span><em>brak FINAL dla tego zdarzenia</em></div>';
}
function proStrip(row,sets,m){
  const ids=['current','catboost','tabpfn','ensemble','adaptive-prod','player','lab','joint'];
  return '<div class="dc87-pro-strip">'+ids.map(id=>{
    const def=MODEL_DEFS.find(x=>x[0]===id),value=modelValue(row,id,sets,m),shadow=def?.[2]==='SHADOW';
    return '<span class="'+(shadow?'shadow':'')+'">'+esc(def?.[1]||id)+(shadow?' · SH':'')+
      '<b>'+(value&&number(value[0])!=null?scoreText(value[0],value[1]):'N/D')+'</b></span>';
  }).join('')+'</div>';
}
function card(row,m,sets,mode){
  const score=finalScore(row,m,sets),info=adaptiveInfo(row,m);
  const available=MODEL_DEFS.reduce((sum,def)=>sum+(modelValue(row,def[0],sets,m)?1:0),0);
  const category=CATEGORY_META[row.category]||CATEGORY_META.special;
  const book=row.operator_playable===true?'🎯 SUPERBET PLAYABLE ✓':'MODEL / RAW';
  return '<article class="dc87-card '+(mode==='pro'?'pro':'')+'" data-dc-category="'+esc(row.category)+'" data-dc-market="'+esc(row.market)+'" data-dc-playable="'+(row.operator_playable===true?'1':'0')+'">'+
    '<div class="dc87-card-head"><div class="dc87-market"><span>'+category.icon+' '+esc(category.label)+'</span><span>'+esc(book)+'</span>'+
    '<h4>'+esc(row.label)+'</h4><strong class="dc87-pick">'+esc(pickText(row))+'</strong></div>'+
    '<div class="dc87-final '+(score==null?'nd':'')+'"><small>FINAL</small><b>'+scoreText(score)+'</b></div></div>'+
    flow(row,m,sets)+proStrip(row,sets,m)+
    '<details class="dc87-details" '+(mode==='pro'?'open':'')+'><summary><span>Pełne szczegóły modeli</span><b>'+available+'/'+MODEL_DEFS.length+
    ' z danymi</b><i aria-hidden="true"></i></summary><div class="dc87-details-body"><div class="dc87-model-grid">'+
    MODEL_DEFS.map(def=>modelCell(row,def,sets,m)).join('')+'</div>'+adaptiveMeta(info)+
    '<p class="dc87-note">Player SH i Market Lab działają wyłącznie w SHADOW. Nie wpływają na FINAL. Accuracy Lab v8.6 pozostaje osobnym raportem SHADOW bez wyniku live per rynek. RAW oraz wynik po Adaptive pochodzą z backendu — UI niczego nie przelicza. Status SUPERBET PLAYABLE jest wyłącznie dodatkowym pokryciem bieżącej oferty i nie usuwa MODEL / RAW.</p></div></details></article>';
}

function topRows(rows,m,sets){
  const best=new Map();
  rows.forEach(row=>{
    const key=[row.category,row.market,row.line||'',row.extra||''].join('|');
    const score=finalScore(row,m,sets);
    if(score==null)return;
    const existing=best.get(key);
    if(!existing||score>existing.score)best.set(key,{row,score});
  });
  const sorted=[...best.values()]
    .sort((a,b)=>b.score-a.score||a.row.order-b.row.order);

  return sorted.slice(0,TOP_LIMIT).map(x=>x.row);
}
function searchable(row,m,sets){
  const models=MODEL_DEFS.filter(def=>modelValue(row,def[0],sets,m)).map(def=>def[1]).join(' ');
  const availability=row.operator_playable===true?'superbet playable':'model raw';
  return norm([row.label,pickText(row),CATEGORY_META[row.category]?.long,row.market,row.line,row.extra,models,availability,m.p1,m.p2].join(' '));
}
function shell(m,rows){
  const declaredMode=String(m?.adaptive_learning_v79?.mode||'PROD').toUpperCase();
  const mode=declaredMode==='PROD'?declaredMode:'PROD';
  const legacyMode=declaredMode!=='PROD';
  const status=String(m?.adaptive_learning_v79?.status||'COLLECTING').toUpperCase();
  return '<section class="dc87" aria-labelledby="dc87-title"><header class="dc87-head"><div>'+
    '<span class="dc87-kicker">Centrum Decyzji Meczu</span><h3 id="dc87-title">Najważniejsze rynki bez szerokiej tabeli</h3>'+
    '<p>FINAL to ocena 0–100 po Adaptive, nie prawdopodobieństwo. Top porównuje wyłącznie FINAL. Brak oceny oznacza N/D; baza jest pokazana osobno.</p></div>'+
    '<div class="dc87-health"><span class="prod">Adaptive '+esc(mode)+' · '+esc(status)+(legacyMode?' · SYNC':'')+'</span>'+
    '<span class="shadow">Player SH · SHADOW</span><span class="shadow">Accuracy Lab v8.6 · SHADOW</span></div></header>'+
    '<div class="dc87-controls"><div class="dc87-modes" role="tablist" aria-label="Tryb Centrum Decyzji">'+
    '<button type="button" role="tab" data-dc-mode="top" aria-selected="true">Top</button>'+
    '<button type="button" role="tab" data-dc-mode="all" aria-selected="false">Wszystkie</button>'+
    '<button type="button" role="tab" data-dc-mode="pro" aria-selected="false">PRO</button></div>'+
    '<div class="dc87-toolbar"><div class="dc87-filters" aria-label="Filtr rynków">'+FILTERS.map((filter,index)=>
      '<button type="button" data-dc-filter="'+filter[0]+'" aria-pressed="'+(index===0?'true':'false')+'">'+filter[1]+'</button>'
    ).join('')+'</div><label class="dc87-search"><span aria-hidden="true">⌕</span>'+
    '<input type="search" data-dc-search placeholder="Szukaj rynku, typu lub modelu…" aria-label="Szukaj rynku, typu lub modelu"></label></div></div>'+
    '<div class="dc87-count" data-dc-count aria-live="polite">Ładowanie '+rows.length+' rynków…</div><div class="dc87-grid" data-dc-grid></div></section>';
}
function installDecisionCenter(root,m,rows=buildRows(m)){
  if(!root||root.dataset.dc87==='1')return;
  root.dataset.dc87='1';
  const sets=specialistSets(m),state={mode:'top',filter:'all',query:''};
  const grid=root.querySelector('[data-dc-grid]'),count=root.querySelector('[data-dc-count]');
  const draw=()=>{
    const query=norm(state.query);
    const filtered=rows.filter(row=>(state.filter==='all'||row.category===state.filter)&&(!query||searchable(row,m,sets).includes(query)));
    const visible=state.mode==='top'?topRows(filtered,m,sets):filtered;
    grid.innerHTML=visible.length?visible.map(row=>card(row,m,sets,state.mode)).join(''):
      '<div class="dc87-empty"><b>Brak pasujących rynków</b>Zmień filtr, tryb albo wpisaną frazę.</div>';
    count.innerHTML='Widoczne <b>'+visible.length+'</b> z '+filtered.length+(state.mode==='top'?' · Top maks. '+TOP_LIMIT:'');
    root.querySelectorAll('[data-dc-mode]').forEach(button=>button.setAttribute('aria-selected',String(button.dataset.dcMode===state.mode)));
    root.querySelectorAll('[data-dc-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.dcFilter===state.filter)));
  };
  root.addEventListener('click',event=>{
    const modeButton=event.target.closest('[data-dc-mode]');
    if(modeButton){state.mode=modeButton.dataset.dcMode;draw();return}
    const filterButton=event.target.closest('[data-dc-filter]');
    if(filterButton){state.filter=filterButton.dataset.dcFilter;draw()}
  });
  root.querySelector('[data-dc-search]')?.addEventListener('input',event=>{state.query=event.target.value;draw()});
  draw();
}
function decisionCenter(m){
  const built=buildRows(m);
  return {html:shell(m,built),rows:built};
}
function currentMatch(raw){
  let wanted=String(raw||'');
  try{wanted=decodeURIComponent(wanted)}catch{}
  return allMatches().find(m=>matchKey(m)===wanted)||null;
}

function tidy(m){
  const screen=document.querySelector('.p751-detail-screen');
  if(!screen||screen.querySelector('.dc87'))return;
  screen.querySelector('#eh771-match-compare')?.remove();
  screen.querySelectorAll('[data-p751-models]').forEach(x=>x.remove());
  screen.querySelector('.p751-verdict')?.remove();
  screen.querySelector('.v79-live-panel')?.remove();
  const list=screen.querySelector('.p751-acc-list');
  if(list){
    const keep=[...list.querySelectorAll('[data-p751-lazy78e23="stats"],[data-p751-lazy78e23="analytics"],[data-p751-lazy78e23="serve"]')];
    list.innerHTML='';
    list.append(...keep);
    const built=decisionCenter(m),mount=document.createElement('div');
    mount.innerHTML=built.html;
    const center=mount.firstElementChild;
    list.before(center);
    installDecisionCenter(center,m,built.rows);
  }
}
// openMatch owns synchronous composition; document click timers must not rebuild it.

function clean(){
  document.querySelector('#model-switcher')?.remove();
  document.querySelectorAll('[data-p751-models]').forEach(x=>x.remove());
}
clean();
setTimeout(clean,300);
setTimeout(clean,1200);

window.TENIS_AI_DECISION_CENTER_V87={version:VERSION,buildRows,adaptiveInfo,finalScore,topRows,decisionCenter,install:installDecisionCenter,tidy};
window.TENIS_AI_MATCH_MATRIX_V853M={version:VERSION,matrix:m=>decisionCenter(m).html,tidy};
})();
