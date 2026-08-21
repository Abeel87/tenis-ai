/* Tenis AI v6.3 — Multi Model + Consensus
   Experimental specialist models. Different weighting of existing pre-match inputs; not ML yet. */
(() => {
  if(typeof bestSignalsData!=='function' || typeof renderMatchDetail!=='function') return;

  const MODEL_KEY='tenis-ai-v63-active-model';
  const MODEL_IDS=['adaptive','early','serve','form','surface'];
  const META={
    consensus:{name:'Consensus',icon:'⚡',desc:'Łączy 5 wariantów modelu współdzielących część danych. Wynik Consensus to siła zgodności /100, nie niezależne prawdopodobieństwo.'},
    adaptive:{name:'Adaptive',icon:'🧠',desc:'Obecny główny model Tenis AI — pełny miks formy, serwisu, returnu, nawierzchni i obciążenia.'},
    early:{name:'Early Hold',icon:'🎯',desc:'Specjalista początku 1. seta: holdy, 1:1 / 2:2 / 3:3, overy pierwszego seta i stabilność serwisu.'},
    serve:{name:'Serve/Return',icon:'🎾',desc:'Najmocniej waży hold, break, punkty po serwisie i return. Dobrze pokazuje przewagę jakości gry.'},
    form:{name:'Form',icon:'🔥',desc:'Mocniej waży aktualną formę, wygrywanie setów, obciążenie i świeżość zawodnika.'},
    surface:{name:'Surface',icon:'🏟️',desc:'Mocniej ufa sygnałom, gdy mamy dobrą próbkę z tej nawierzchni; małe próbki mocno wygasza.'}
  };

  const baseRenderMatchDetail=renderMatchDetail;
  let activeModel=readModel();

  function readModel(){try{return localStorage.getItem(MODEL_KEY)||'consensus'}catch{return 'consensus'}}
  function saveModel(){try{localStorage.setItem(MODEL_KEY,activeModel)}catch{}}
  const clamp=(x,a=0,b=100)=>Math.max(a,Math.min(b,Number.isFinite(Number(x))?Number(x):50));
  const avg=(...xs)=>{const a=xs.filter(x=>Number.isFinite(Number(x))).map(Number);return a.length?a.reduce((s,x)=>s+x,0)/a.length:0.5};
  const pc=x=>Number.isFinite(Number(x))?Number(x):0.5;
  const conf01=x=>clamp(Number(x||50),0,100)/100;
  const pairScore=(a,b,scale=100,confidence=1)=>clamp(50+(a-b)*scale*confidence,8,92);
  const opposite=x=>100-x;
  const keySafe=s=>String(s??'').toLowerCase().replace(/[^a-z0-9.:-]+/g,'_');
  const mk=(key,label,v,market,pick)=>({key,label,v:clamp(v),market,pick});
  const bestEntry=obj=>{if(!obj)return null;const e=Object.entries(obj).filter(([,v])=>Number.isFinite(Number(v))).sort((a,b)=>Number(b[1])-Number(a[1]))[0];return e||null};
  const playerStats=(m,p)=>p===1?(m.p1_stats||{}):(m.p2_stats||{});
  const playerName=(m,p)=>p===1?m.p1:m.p2;

  function adaptiveSignals(m){
    const c=[];
    const bin=(market,prefix,obj)=>{const e=bestEntry(obj);if(e)c.push(mk(`${market}|${keySafe(e[0])}`,`${prefix}: ${e[0]}`,e[1],market,e[0]))};
    bin('match_win','Mecz',m.match_win);bin('set1_win','1. set',m.first_set_win);bin('set2_win','2. set',m.second_set_win);bin('set3_win','3. set*',m.third_set_win);bin('total_sets','Sety',m.total_sets);
    if(m.over_under)Object.entries(m.over_under).forEach(([line,v])=>{if(!v)return;const over=Number(v.over),under=Number(v.under);const pick=over>=under?'over':'under';c.push(mk(`set1_total|${line}|${pick}`,`1S ${pick==='over'?'O':'U'}${line}`,pick==='over'?over:under,'set1_total',pick))});
    if(m.match_over_under)Object.entries(m.match_over_under).forEach(([line,v])=>{if(!v)return;const over=Number(v.over),under=Number(v.under);const pick=over>=under?'over':'under';c.push(mk(`match_total|${line}|${pick}`,`M ${pick==='over'?'O':'U'}${line}`,pick==='over'?over:under,'match_total',pick))});
    if(m.game_states) ['2','4','6'].forEach(n=>{const e=bestEntry(m.game_states[n]);if(e)c.push(mk(`state|${n}|${e[0]}`,`Po ${n}: ${e[0]}`,e[1],`state${n}`,e[0]))});
    return c;
  }

  function strengthServe(s){return .34*pc(s.hold_rate)+.22*pc(s.break_rate)+.18*pc(s.serve_points_won)+.16*pc(s.return_points_won)+.10*pc(s.won)}
  function strengthSet1(s){return .30*pc(s.first_set_won)+.25*pc(s.hold_rate)+.18*pc(s.break_rate)+.14*pc(s.serve_points_won)+.13*pc(s.return_points_won)}
  function strengthForm(s){
    const fatigue=clamp(Number(s.fatigue_load||0),0,6)/6;
    const inactivity=clamp((Number(s.days_since_last||0)-35)/140,0,1);
    return .40*pc(s.won)+.30*pc(s.first_set_won)+.16*pc(s.second_set_won)+.08*pc(s.third_set_won)+.06*(1-fatigue)-.05*inactivity;
  }
  function sampleConfidence(s,kind='all'){
    const n=kind==='surface'?Number(s.surface_matches||0):Number(s.matches||0);
    const data=conf01(s.data_confidence||60);
    return clamp((n/(n+5))*.70+data*.30,0.22,1);
  }
  function overHist(s,line){
    const map={'8.5':'first_set_over85','9.5':'first_set_over95','10.5':'first_set_over105','11.5':'first_set_over115','12.5':'first_set_over125'};
    const v=s?.[map[String(line)]];return Number.isFinite(Number(v))?Number(v):null;
  }
  function expectedOver(s1,s2,line){
    const h=[overHist(s1,line),overHist(s2,line)].filter(x=>x!=null);
    if(h.length)return avg(...h);
    const games=avg(s1.first_set_games,s2.first_set_games);
    return clamp(.5+(games-Number(line))*.09,.08,.92);
  }
  function holdBalance(m){
    const h1=Number(m.service_model?.p1_hold ?? (pc(m.p1_stats?.hold_rate)*100));
    const h2=Number(m.service_model?.p2_hold ?? (pc(m.p2_stats?.hold_rate)*100));
    return {h1:clamp(h1),h2:clamp(h2),avg:(clamp(h1)+clamp(h2))/2,diff:Math.abs(clamp(h1)-clamp(h2))};
  }

  function winnerSignals(m,mode){
    const s1=playerStats(m,1),s2=playerStats(m,2);let a,b,conf=1;
    if(mode==='serve'){a=strengthServe(s1);b=strengthServe(s2);conf=avg(sampleConfidence(s1),sampleConfidence(s2));}
    else if(mode==='form'){a=strengthForm(s1);b=strengthForm(s2);conf=avg(sampleConfidence(s1),sampleConfidence(s2));}
    else {a=.30*pc(s1.won)+.25*pc(s1.first_set_won)+.20*pc(s1.hold_rate)+.15*pc(s1.break_rate)+.10*pc(s1.return_points_won);b=.30*pc(s2.won)+.25*pc(s2.first_set_won)+.20*pc(s2.hold_rate)+.15*pc(s2.break_rate)+.10*pc(s2.return_points_won);conf=avg(sampleConfidence(s1,'surface'),sampleConfidence(s2,'surface'));}
    const p1=pairScore(a,b,145,conf),p2=opposite(p1);const matchP=p1>=p2?1:2;const matchV=Math.max(p1,p2);
    let a1,b1;
    if(mode==='serve'){a1=strengthSet1(s1);b1=strengthSet1(s2)}
    else if(mode==='form'){a1=.55*pc(s1.first_set_won)+.30*pc(s1.won)+.15*pc(s1.hold_rate);b1=.55*pc(s2.first_set_won)+.30*pc(s2.won)+.15*pc(s2.hold_rate)}
    else {a1=.50*pc(s1.first_set_won)+.22*pc(s1.hold_rate)+.16*pc(s1.break_rate)+.12*pc(s1.won);b1=.50*pc(s2.first_set_won)+.22*pc(s2.hold_rate)+.16*pc(s2.break_rate)+.12*pc(s2.won)}
    const f1=pairScore(a1,b1,155,conf),f2=opposite(f1);const setP=f1>=f2?1:2;
    return [
      mk(`match_win|${keySafe(playerName(m,matchP))}`,`Mecz: ${playerName(m,matchP)}`,matchV,'match_win',playerName(m,matchP)),
      mk(`set1_win|${keySafe(playerName(m,setP))}`,`1. set: ${playerName(m,setP)}`,Math.max(f1,f2),'set1_win',playerName(m,setP))
    ];
  }

  function totalSignals(m,mode){
    const s1=m.p1_stats||{},s2=m.p2_stats||{},out=[];const hb=holdBalance(m);
    if(m.over_under)Object.keys(m.over_under).forEach(line=>{
      let over=expectedOver(s1,s2,line);
      if(mode==='serve') over=.62*over+.38*clamp((hb.avg-58)/30,0,1);
      else if(mode==='form') over=.78*over+.22*avg(pc(s1.first_set_over85),pc(s2.first_set_over85));
      else if(mode==='surface'){
        const cf=avg(sampleConfidence(s1,'surface'),sampleConfidence(s2,'surface'));
        over=.5+(over-.5)*cf;
      }else if(mode==='early') over=.55*over+.45*clamp((hb.avg-56)/34,0,1);
      over=clamp(over*100,7,93);const under=100-over;const pick=over>=under?'over':'under';
      out.push(mk(`set1_total|${line}|${pick}`,`1S ${pick==='over'?'O':'U'}${line}`,Math.max(over,under),'set1_total',pick));
    });
    if(mode!=='early'&&m.match_over_under)Object.entries(m.match_over_under).forEach(([line,v])=>{
      const base=Number(v?.over);if(!Number.isFinite(base))return;let over=base;
      if(mode==='serve')over=.70*base+.30*clamp(50+(hb.avg-68)*1.3,15,85);
      if(mode==='form')over=.82*base+.18*clamp(50+(avg(s1.first_set_games,s2.first_set_games)-9.5)*5,25,75);
      if(mode==='surface'){const cf=avg(sampleConfidence(s1,'surface'),sampleConfidence(s2,'surface'));over=50+(base-50)*cf}
      const under=100-over,pick=over>=under?'over':'under';out.push(mk(`match_total|${line}|${pick}`,`M ${pick==='over'?'O':'U'}${line}`,Math.max(over,under),'match_total',pick));
    });
    return out;
  }

  function stateSignals(m,mode){
    if(!m.game_states)return [];const hb=holdBalance(m),out=[];
    ['2','4','6'].forEach(n=>{
      const states=m.game_states[n];if(!states)return;let best=null;
      Object.entries(states).forEach(([state,base])=>{
        let v=Number(base);if(!Number.isFinite(v))return;const parts=state.split(':').map(Number);const balanced=parts.length===2&&parts[0]===parts[1];const diff=Math.abs((parts[0]||0)-(parts[1]||0));
        if(mode==='early')v=.62*v+.38*(balanced?clamp(42+(hb.avg-60)*1.25-hb.diff*.45,18,88):clamp(30+hb.diff*1.8+diff*4,10,78));
        else if(mode==='serve')v=.78*v+.22*(balanced?clamp(45+(hb.avg-65),20,80):clamp(35+hb.diff,15,75));
        else if(mode==='surface'){const cf=avg(sampleConfidence(m.p1_stats||{},'surface'),sampleConfidence(m.p2_stats||{},'surface'));v=50+(v-50)*cf}
        else if(mode==='form'){const cf=avg(sampleConfidence(m.p1_stats||{}),sampleConfidence(m.p2_stats||{}));v=50+(v-50)*(.65+.35*cf)}
        if(!best||v>best.v)best={state,v};
      });
      if(best)out.push(mk(`state|${n}|${best.state}`,`Po ${n}: ${best.state}`,best.v,`state${n}`,best.state));
    });
    return out;
  }

  function earlyWinner(m){
    const s1=m.p1_stats||{},s2=m.p2_stats||{};const a=.48*pc(s1.first_set_won)+.26*pc(s1.hold_rate)+.16*pc(s1.break_rate)+.10*pc(s1.serve_points_won);const b=.48*pc(s2.first_set_won)+.26*pc(s2.hold_rate)+.16*pc(s2.break_rate)+.10*pc(s2.serve_points_won);const conf=avg(sampleConfidence(s1),sampleConfidence(s2));const p1=pairScore(a,b,145,conf),p2=100-p1,p=p1>=p2?1:2;return mk(`set1_win|${keySafe(playerName(m,p))}`,`1. set: ${playerName(m,p)}`,Math.max(p1,p2),'set1_win',playerName(m,p));
  }

  function modelSignals(id,m){
    if(id==='adaptive')return adaptiveSignals(m);
    if(id==='early')return [earlyWinner(m),...stateSignals(m,'early'),...totalSignals(m,'early')];
    if(id==='serve')return [...winnerSignals(m,'serve'),...stateSignals(m,'serve'),...totalSignals(m,'serve')];
    if(id==='form')return [...winnerSignals(m,'form'),...stateSignals(m,'form'),...totalSignals(m,'form')];
    if(id==='surface')return [...winnerSignals(m,'surface'),...stateSignals(m,'surface'),...totalSignals(m,'surface')];
    return [];
  }

  function consensusSignals(m){
    const maps=MODEL_IDS.map(id=>new Map(modelSignals(id,m).map(x=>[x.key,x])));const keys=new Set(maps.flatMap(mp=>[...mp.keys()]));const out=[];
    for(const key of keys){
      const vals=maps.map(mp=>mp.get(key)).filter(Boolean);if(vals.length<2)continue;
      const supporters=vals.filter(x=>x.v>=68);if(supporters.length<2)continue;
      const strong=supporters.filter(x=>x.v>=72).length;const mean=supporters.reduce((s,x)=>s+x.v,0)/supporters.length;const score=clamp(mean+(supporters.length-1)*1.7+(strong>=3?1.5:0),0,98);
      const x=supporters.sort((a,b)=>b.v-a.v)[0];out.push({...x,v:score,votes:supporters.length,strongVotes:strong,modelScores:Object.fromEntries(MODEL_IDS.map((id,i)=>[id,maps[i].get(key)?.v??null]))});
    }
    return out.sort((a,b)=>b.votes-a.votes||b.strongVotes-a.strongVotes||b.v-a.v);
  }

  function selectedSignals(m,limit=20){
    const rows=activeModel==='consensus'?consensusSignals(m):modelSignals(activeModel,m).sort((a,b)=>b.v-a.v);
    return rows.filter(x=>x.v>=68).slice(0,limit);
  }

  function selectedName(){return `${META[activeModel]?.icon||''} ${META[activeModel]?.name||activeModel}`.trim()}

  window.TENIS_AI_MODEL_API={
    version:'v7.7.2',
    get active(){return activeModel},
    activeName:()=>selectedName(),
    signals:(m,limit=20)=>selectedSignals(m,limit).map(x=>({...x})),
    allSignals:(m)=>{
      const rows=activeModel==='consensus'?consensusSignals(m):modelSignals(activeModel,m).sort((a,b)=>b.v-a.v);
      return rows.map(x=>({...x}));
    },
    signalsFor:(id,m)=>{
      const rows=id==='consensus'?consensusSignals(m):modelSignals(id,m).sort((a,b)=>b.v-a.v);
      return rows.map(x=>({...x}));
    }
  };

  bestSignalsData=(m,limit=3)=>selectedSignals(m,limit);
  bestSignals=(m)=>{
    const top=selectedSignals(m,3);if(!top.length)return '';
    const title=activeModel==='consensus'?'⚡ Consensus — najmocniejsze wspólne sygnały':`🔥 ${META[activeModel].name} — najmocniejsze sygnały`;
    return `<div class="signals"><div class="signals-title">${title}</div><div class="signals-grid">${top.map(x=>pill(x.votes?`${x.votes}/5 · ${x.label}`:x.label,x.v)).join('')}</div></div>`;
  };
  compactSignals=(m)=>{
    const top=selectedSignals(m,2);if(!top.length)return '';
    return `<div class="compact-signals">${top.map(x=>`<span class="compact-signal ${cls(x.v)} ${activeModel==='consensus'?'consensus':''}">${esc(x.votes?`${x.votes}/5 · ${x.label}`:x.label)} <b>${Math.round(x.v)}</b></span>`).join('')}</div>`;
  };

  function topFor(id,m){const rows=(id==='consensus'?consensusSignals(m):modelSignals(id,m).sort((a,b)=>b.v-a.v)).filter(x=>x.v>=55);return rows[0]||null}
  function scoreClass(v){return v>=80?'elite':v>=72?'good':''}
  function modelPanel(m){
    const consensus=consensusSignals(m).slice(0,3);
    const cards=MODEL_IDS.map(id=>{const x=topFor(id,m);return `<div class="model-mini ${activeModel===id?'active':''}"><div class="model-mini-name"><span>${META[id].icon} ${META[id].name}</span></div><div class="model-mini-score ${x?scoreClass(x.v):''}">${x?Math.round(x.v):'—'}</div><div class="model-mini-pick">${x?esc(x.label):'Brak mocnego sygnału'}</div></div>`}).join('');
    return `<section class="multi-model-panel"><div class="multi-model-head"><b>🧠 Porównanie modeli</b><span>aktywny: ${esc(selectedName())}</span></div><div class="multi-model-grid">${cards}</div><div class="consensus-box"><div class="consensus-title"><b>⚡ Consensus</b><span>poparcie ≥68/100</span></div><div class="consensus-list">${consensus.length?consensus.map(x=>`<div class="consensus-row"><div class="consensus-votes">${x.votes}/5</div><span>${esc(x.label)}</span><b>${Math.round(x.v)}/100</b></div>`).join(''):'<div class="multi-model-note">Brak typu popieranego przez co najmniej 2 modele.</div>'}</div></div><div class="multi-model-note">Modele v6.3 są specjalistycznymi wariantami heurystycznymi. Każdy inaczej waży te same dane wejściowe. To jeszcze nie ML i wynik 0–100 nie jest gwarantowanym prawdopodobieństwem.</div></section>`;
  }

  renderMatchDetail=(m)=>`${modelPanel(m)}${baseRenderMatchDetail(m)}`;

  function syncSwitcher(){
    const desc=document.querySelector('#model-description');if(desc)desc.textContent=META[activeModel]?.desc||'';
    document.querySelectorAll('[data-model]').forEach(b=>b.classList.toggle('active',b.dataset.model===activeModel));
  }
  function refreshViews(){
    try{if(typeof view!=='undefined'&&view==='matches'&&typeof renderMatches==='function')renderMatches()}catch{}
    const panel=document.querySelector('#player-profile-panel');const input=document.querySelector('#player-search-input');
    if(panel&&!panel.hidden&&input?.value){try{input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))}catch{}}
  }
  document.querySelectorAll('[data-model]').forEach(b=>b.addEventListener('click',()=>{activeModel=b.dataset.model;if(!META[activeModel])activeModel='consensus';saveModel();syncSwitcher();refreshViews()}));
  syncSwitcher();
  setTimeout(refreshViews,0);
})();
