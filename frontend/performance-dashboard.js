/* Tenis AI v8.8.2 — Generator UX + Performance cleanup */
(()=>{
'use strict';

const VERSION='v8.8.2';
const RUNTIME_FIX='v8.8.13';
const PERIOD_KEY='tenis-ai-v882-period';
const TAB_KEY='tenis-ai-v882-tab';

const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));
const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');
const nameKey=s=>norm(s).replace(/[^a-z0-9]+/g,' ').split(' ').filter(Boolean).sort().join(' ');
const pct=x=>num(x)==null?'N/D':`${Number(x).toFixed(1).replace('.0','')}%`;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,Number(x)||0));

function aliasMarket(x){
  return ({
    match_winner:'match_win',
    set1_winner:'set1_win',
    set2_winner:'set2_win',
    set3_winner:'set3_win'
  })[String(x||'').toLowerCase()]||String(x||'').toLowerCase();
}

function surf(v){
  const x=norm(v);
  if(x.includes('hard'))return'HARD';
  if(x.includes('clay'))return'CLAY';
  if(x.includes('grass'))return'GRASS';
  if(x.includes('carpet'))return'CARPET';
  return String(v||'N/D').toUpperCase();
}

function tour(v){
  const x=norm(v);
  if(x.includes('chall'))return'CH';
  if(x.includes('itf'))return'ITF';
  if(x.includes('wta'))return'WTA';
  if(x.includes('atp'))return'ATP';
  return String(v||'N/D').toUpperCase();
}

function history(){
  try{return Array.isArray(historyRows)?historyRows:[]}catch{return[]}
}

function eventKey(match,signal){
  const rawMarket=aliasMarket(signal.market);
  const market=/^state[246]$/.test(rawMarket)?'game_state':rawMarket;
  const parts=String(signal.key||signal.signal_key||'').split('|');
  let line=num(signal.line??signal.selected_line??signal.suggested_line??(market.endsWith('_total')?parts[1]:null));
  const sets=match?.result?.sets||[];
  const pair=sets[0]?[...sets[0]].sort((a,b)=>a-b):[];
  const standard=match?.result?.status==='completed'&&((pair[1]===6&&pair[0]<=4)||(pair[1]===7&&[5,6].includes(pair[0])));
  if(standard&&market==='set1_total'&&line===11.5)line=10.5;
  const cp=market==='game_state'?num(signal.checkpoint??rawMarket.match(/^state([246])$/)?.[1]??parts[1]):null;
  let pick=norm(signal.pick);
  if(['match_win','set1_win','set2_win','set3_win'].includes(market)){
    const player=nameKey(signal.pick),p1=nameKey(match.p1),p2=nameKey(match.p2);
    pick=player&&player===p1?'p1':player&&player===p2?'p2':pick;
  }
  return [market,line??'',cp??'',pick].join('|');
}
function flatten(source='base'){
  const out=[];
  for(const m of history()){
    const time=new Date(m?.scheduled_time??m?.captured_at??m?.first_captured_at??0);
    if(!Number.isFinite(time.getTime()))continue;
    const seen=new Set();
    const signals=source==='final'?m.autolearn_signals_v84:m.signals;
    for(const s of [...(signals||[])].sort((a,b)=>String(a.line??'').localeCompare(String(b.line??'')))){
      if(s?.result!=='hit'&&s?.result!=='miss')continue;
      const score=source==='final'?num(s.adaptive_prod_v79?.final_score):num(s.score);
      if(score==null)continue;
      const event=eventKey(m,s),model=source==='final'?'adaptive-prod':String(s.source_model||'legacy');
      const key=event+'|'+model;
      if(seen.has(key))continue;
      seen.add(key);
      out.push({time,settledTime:new Date(m.settled_at||m.scheduled_time),hit:s.result==='hit',score,event,
        matchKey:String(m.match_key||m.match_id||[m.p1,m.p2,m.scheduled_time].join('|')),
        label:String(s.label||s.market||'Inny'),market:aliasMarket(s.market||'other'),source:model,
        tour:tour(m.tour),surface:surf(m.surface),
        version:source==='final'?String(s.tracker_version||'N/D'):String(m.model_version||'N/D')});
    }
  }
  return out;
}

function stat(rows){
  const n=rows.length;
  const hits=rows.reduce((a,x)=>a+(x.hit?1:0),0);
  return {n,hits,misses:n-hits,accuracy:n?hits*100/n:null};
}

function group(rows,key){
  const map=new Map();
  rows.forEach(x=>{
    const k=key(x);
    if(!map.has(k))map.set(k,[]);
    map.get(k).push(x);
  });
  return [...map.entries()].map(([name,list])=>({name,...stat(list),rows:list}));
}

function wilsonLower(h,n){
  if(!n)return null;
  const z=1.96,p=h/n,d=1+z*z/n;
  const c=(p+z*z/(2*n))/d;
  const half=z*Math.sqrt((p*(1-p)+z*z/(4*n))/n)/d;
  return Math.max(0,(c-half)*100);
}

/* History -> Generator.
   Small capped ranking bonus only. FINAL probability is untouched. */
function priorFor(match,signal){
  const end=Math.min(Date.now(),new Date(match?.scheduled_time||Date.now()).getTime());
  const cut=end-30*86400000;
  const event=eventKey(match,signal);
  const wanted=String(match?.autolearn_v84?.version||window.TENIS_AI_META?.productionModelVersion||'');
  const rows=flatten('final').filter(x=>x.time.getTime()>=cut&&x.settledTime.getTime()<end&&x.version===wanted&&x.event===event);
  const t=tour(match?.tour),sf=surf(match?.surface);
  const options=[
    {scope:'FINAL + zdarzenie + tour + nawierzchnia',min:10,rows:rows.filter(x=>x.tour===t&&x.surface===sf)},
    {scope:'FINAL + zdarzenie + nawierzchnia',min:12,rows:rows.filter(x=>x.surface===sf)},
    {scope:'FINAL + zdarzenie',min:20,rows}
  ];
  const chosen=options.find(x=>x.rows.length>=x.min);
  if(!chosen)return {n:0,accuracy:null,adjustment:0,scope:'brak probki'};

  const st=stat(chosen.rows);
  const factor=chosen.rows.length>=30?1:Math.max(.45,chosen.rows.length/30);
  const adjustment=clamp((Number(st.accuracy)-65)/5,-2.5,2.5)*factor;

  return {
    n:chosen.rows.length,
    accuracy:st.accuracy,
    adjustment:Number(adjustment.toFixed(2)),
    scope:chosen.scope,
    lower95:wilsonLower(st.hits,st.n)
  };
}

window.TENIS_AI_PERFORMANCE_V882=Object.freeze({version:VERSION,priorFor,eventKey,flatten});

function period(){
  try{
    const x=localStorage.getItem(PERIOD_KEY);
    return ['7d','30d','all'].includes(x)?x:'30d';
  }catch{return'30d'}
}
function scoped(rows){
  if(period()==='all')return rows;
  const days=period()==='7d'?7:30;
  const cut=Date.now()-days*86400000;
  return rows.filter(x=>x.time.getTime()>=cut);
}

function confidence(rows){
  const bands=[['<65',-1e9,65],['65-69',65,70],['70-74',70,75],['75-79',75,80],['80-84',80,85],['85+',85,1e9]];
  return bands.map(([name,a,b])=>{
    const list=rows.filter(x=>x.score!=null&&x.score>=a&&x.score<b);
    const st=stat(list);
    const predicted=list.length?list.reduce((z,x)=>z+Number(x.score),0)/list.length:null;
    return {...st,name,predicted,gap:st.accuracy!=null&&predicted!=null?st.accuracy-predicted:null};
  }).filter(x=>x.n);
}

function trend(rows){
  const days=group(rows,x=>x.time.toLocaleDateString('en-CA'))
    .sort((a,b)=>String(a.name).localeCompare(String(b.name))).slice(-30);
  if(days.length<2)return '<div class="pc882-empty">Za mało dni do wykresu.</div>';
  const W=460,H=145,p=20;
  const pts=days.map((d,i)=>{
    const x=p+i*(W-p*2)/(days.length-1);
    const y=H-p-clamp((d.accuracy-40)/60,0,1)*(H-p*2);
    return {x,y,d};
  });
  const poly=pts.map(x=>`${x.x.toFixed(1)},${x.y.toFixed(1)}`).join(' ');
  const target=(H-p-(72-40)/60*(H-p*2)).toFixed(1);
  return `<div class="pc882-trend"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Dzienny trend skuteczności">
    <line class="target" x1="${p}" y1="${target}" x2="${W-p}" y2="${target}"/>
    <polyline points="${poly}"/>
    ${pts.map(x=>`<circle cx="${x.x.toFixed(1)}" cy="${x.y.toFixed(1)}" r="3"><title>${esc(x.d.name)} · ${pct(x.d.accuracy)} · n=${x.d.n}</title></circle>`).join('')}
  </svg><small>${esc(days[0].name)} → ${esc(days.at(-1).name)} · linia 72%</small></div>`;
}

function calibration(rows){
  const b=confidence(rows);
  if(!b.length)return '<div class="pc882-empty">Brak danych do kalibracji.</div>';
  return `<div class="pc882-bars">${b.map(x=>`
    <div class="pc882-bar">
      <span><b>${esc(x.name)}</b><small>n=${x.n}</small></span>
      <div><i style="width:${clamp(x.accuracy,0,100)}%"></i>${x.predicted!=null?`<em style="left:${clamp(x.predicted,0,100)}%"></em>`:''}</div>
      <strong>${pct(x.accuracy)}<small>${x.gap==null?'':`${x.gap>=0?'+':''}${x.gap.toFixed(1)} pp`}</small></strong>
    </div>`).join('')}</div>`;
}

function marketBars(rows){
  const list=group(rows,x=>x.label).filter(x=>x.n>=10).sort((a,b)=>b.n-a.n).slice(0,10);
  if(!list.length)return '<div class="pc882-empty">Brak rynku z próbą n≥10.</div>';
  return `<div class="pc882-market-bars">${list.map(x=>`
    <div class="pc882-market-row"><span><b>${esc(x.name)}</b><small>n=${x.n}</small></span>
    <div><i style="width:${clamp(x.accuracy,0,100)}%"></i></div><strong>${pct(x.accuracy)}</strong></div>`).join('')}</div>`;
}

function heatmap(rows){
  const tours=['ATP','WTA','CH','ITF'], surfaces=['HARD','CLAY','GRASS'];
  return `<div class="pc882-heat"><span></span>${surfaces.map(x=>`<b>${x}</b>`).join('')}
  ${tours.map(t=>[`<b>${t}</b>`,...surfaces.map(sf=>{
    const st=stat(rows.filter(x=>x.tour===t&&x.surface===sf));
    const cls=st.n<5?'nd':st.accuracy>=72?'good':st.accuracy<60?'bad':'mid';
    return `<span class="${cls}"><strong>${st.n>=5?pct(st.accuracy):'N/D'}</strong><small>n=${st.n}</small></span>`;
  })].join('')).join('')}</div>`;
}

function segments(rows){
  const all=[
    ...group(rows,x=>x.label).map(x=>({...x,type:'Rynek'})),
    ...group(rows,x=>x.source).map(x=>({...x,type:'Model'})),
    ...group(rows,x=>x.tour).map(x=>({...x,type:'Tour'})),
    ...group(rows,x=>x.surface).map(x=>({...x,type:'Nawierzchnia'}))
  ].filter(x=>x.n>=10&&x.accuracy!=null).map(x=>({...x,lower:wilsonLower(x.hits,x.n)}));

  const best=[...all].sort((a,b)=>b.lower-a.lower||b.n-a.n).slice(0,6);
  const weak=[...all].sort((a,b)=>a.accuracy-b.accuracy||b.n-a.n).slice(0,6);
  const col=(title,list,cls)=>`<div class="pc882-seg-col ${cls}"><h4>${title}</h4>${list.map(x=>`
    <div class="pc882-seg"><em>${esc(x.type)}</em><span><b>${esc(x.name)}</b><small>${x.hits}/${x.n} · dolny 95% ${pct(x.lower)}</small></span><strong>${pct(x.accuracy)}</strong></div>`).join('')}</div>`;
  return `<div class="pc882-segments">${col('Działa najlepiej',best,'good')}${col('Do poprawy',weak,'bad')}</div>`;
}

const reportCache=new Map();
async function j(path){
  const cached=reportCache.get(path);
  if(cached&&Date.now()-cached.time<60000)return cached.value;
  try{
    const r=await fetch(`${path}?v882=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)return {};
    const value=await r.json();reportCache.set(path,{time:Date.now(),value});return value;
  }catch{return{}}
}

function modelRows(tel){
  const scopes=tel?.scopes||{};
  const key=period()==='7d'?'7d':period()==='30d'?'30d':'all';
  const scope=scopes[key]||scopes['30d']||scopes['7d']||Object.values(scopes)[0]||{};
  return Object.entries(scope?.by_model||{}).map(([id,x])=>({
    id,label:x?.label||id,n:Number(x?.selected_n||0),accuracy:num(x?.accuracy),brier:num(x?.brier)
  })).filter(x=>x.n).sort((a,b)=>{
    const aa=a.n>=10&&a.accuracy!=null?a.accuracy:-1;
    const bb=b.n>=10&&b.accuracy!=null?b.accuracy:-1;
    return bb-aa||b.n-a.n;
  });
}

function activate(dash,tab){
  const valid=['overview','charts','markets','models','adaptive'];
  const next=valid.includes(tab)?tab:'overview';
  try{localStorage.setItem(TAB_KEY,next)}catch{}
  dash.querySelectorAll('[data-pc882-tab]').forEach(x=>x.classList.toggle('active',x.dataset.pc882Tab===next));
  dash.querySelectorAll('[data-pc882-pane]').forEach(x=>x.hidden=x.dataset.pc882Pane!==next);
}

function collapseOld(host,dash){
  const old=host.querySelector('#pc882-legacy');
  if(old){
    const body=old.querySelector('.pc882-legacy-body');
    if(body)[...body.children].forEach(x=>host.append(x));
    old.remove();
  }
  const head=host.querySelector('.pc77-head');
  const nodes=[...host.children].filter(x=>x!==head&&x!==dash);
  if(!nodes.length)return;
  const d=document.createElement('details');
  d.id='pc882-legacy'; d.className='pc882-legacy';
  d.innerHTML='<summary><b>Pełne tabele / starsza diagnostyka</b><span>otwórz gdy chcesz wejść głębiej</span></summary><div class="pc882-legacy-body"></div>';
  const body=d.querySelector('.pc882-legacy-body');
  nodes.forEach(x=>body.append(x));
  host.append(d);
}

let statsGeneration=0;
async function renderStats882(){
  const generation=++statsGeneration;
  const host=document.querySelector('#pc77');
  if(!host)return;
  if(!host.querySelector('#pc882-dashboard'))host.classList.add('pc885-loading');

  let rows=scoped(flatten());
  const wanted=String(window.TENIS_AI_META?.calibrationModelVersion||'');
  const same=rows.filter(x=>x.version===wanted);
  rows=same;
  const finalRows=scoped(flatten('final')).filter(x=>x.version===String(window.TENIS_AI_META?.productionModelVersion||''));
  const finalOverall=stat(finalRows.filter(x=>x.score>=65));

  const [adaptive,tel]=await Promise.all([j('data/adaptive_learning_v79.json'),j('data/model_telemetry_v84c.json')]);
  if(document.querySelector('#pc77')!==host||generation!==statsGeneration)return;

  document.querySelector('#pc88-dashboard')?.remove();
  const previous=host.querySelector('#pc882-dashboard');

  const overall=stat(rows);
  const mk=group(rows,x=>x.label).filter(x=>x.n>=10&&x.accuracy!=null);
  const best=[...mk].sort((a,b)=>b.accuracy-a.accuracy||b.n-a.n)[0];
  const weak=[...mk].sort((a,b)=>a.accuracy-b.accuracy||b.n-a.n)[0];
  const cal=confidence(rows).filter(x=>x.gap!=null);
  const mae=cal.length?cal.reduce((a,x)=>a+Math.abs(x.gap),0)/cal.length:null;
  const models=modelRows(tel);
  const global=adaptive?.cells?.global?.global||{};
  const repeated=Array.isArray(adaptive?.repeated_errors)?adaptive.repeated_errors.slice(0,10):[];

  const dash=document.createElement('section');
  dash.id='pc882-dashboard';
  dash.className='pc882-dashboard';
  dash.innerHTML=`
    <header class="pc882-head"><div><span>CENTRUM SKUTECZNOŚCI</span><h3>Co działa, co nie i gdzie model się myli?</h3><p>FINAL i model bazowy są liczone osobno. Trendy znajdziesz w zakładce Wykresy.</p></div>
      <div class="pc882-period">${['7d','30d','all'].map(x=>`<button data-pc882-period="${x}" class="${period()===x?'active':''}">${x==='all'?'Wszystko':x}</button>`).join('')}</div>
    </header>
    <nav class="pc882-tabs">${[['overview','Przegląd'],['charts','Wykresy'],['markets','Rynki'],['models','Modele'],['adaptive','Adaptive']].map(([k,l])=>`<button data-pc882-tab="${k}">${l}</button>`).join('')}</nav>

    <section data-pc882-pane="overview">
      <div class="pc882-kpis">
        <article><span>FINAL ≥65/100 · trafność</span><b>${pct(finalOverall.accuracy)}</b><small>${finalOverall.hits} HIT · ${finalOverall.misses} MISS · n=${finalOverall.n} · ${new Set(finalRows.filter(x=>x.score>=65).map(x=>x.matchKey)).size} meczów</small></article>
        <article><span>Model bazowy · trafność</span><b>${pct(overall.accuracy)}</b><small>${overall.hits} HIT · ${overall.misses} MISS · n=${overall.n}</small></article>
        <article class="good"><span>Najlepszy rynek · baza</span><b>${best?esc(best.name):'N/D'}</b><small>${best?pct(best.accuracy)+' · n='+best.n:'brak próbki'}</small></article>
        <article class="bad"><span>Najsłabszy rynek · baza</span><b>${weak?esc(weak.name):'N/D'}</b><small>${weak?pct(weak.accuracy)+' · n='+weak.n:'brak próbki'}</small></article>
        <article><span>Błąd kalibracji · baza</span><b>${mae==null?'N/D':mae.toFixed(1)+' pp'}</b><small>średni |realnie − confidence|</small></article>
      </div>
      <div class="pc882-grid">
        <article class="pc882-card"><header><b>Trend skuteczności · model bazowy</b><small>dzień po dniu</small></header>${trend(rows)}</article>
        <article class="pc882-card"><header><b>Ocena a trafność · model bazowy</b><small>pasek = trafność, kreska = ocena modelu</small></header>${calibration(rows)}</article>
      </div>
    </section>

    <section data-pc882-pane="charts" aria-label="Wykresy skuteczności">
      <div class="pc882-grid">
        <article class="pc882-card"><header><b>Model bazowy · trend dzienny</b><small>Wybrany okres · rozliczone zdarzenia</small></header>${trend(rows)}</article>
        <article class="pc882-card"><header><b>FINAL ≥65/100 · trend dzienny</b><small>Wybrany okres · zamrożone oceny po Adaptive</small></header>${trend(finalRows.filter(x=>x.score>=65))}</article>
      </div>
      <p class="pc882-note">Poniżej trendy ostatnich rozliczeń poszczególnych modeli, niezależne od filtra okresu. Próbki modeli mogą się różnić. Brak wyników oznacza brak danych, nie 0%.</p>
      ${window.TENIS_AI_MODEL_TRENDS_V84E2?.render?.(tel,'pc882-trend-monitor')||'<div class="pc882-empty">Brak raportu trendów modeli.</div>'}
    </section>

    <section data-pc882-pane="markets">
      <div class="pc882-grid">
        <article class="pc882-card"><header><b>Najczęstsze sygnały · model bazowy</b><small>minimum n=10; nie są to zakłady użytkownika</small></header>${marketBars(rows)}</article>
        <article class="pc882-card"><header><b>Tour × nawierzchnia</b><small>model bazowy</small></header>${heatmap(rows)}</article>
      </div>
      <article class="pc882-card"><header><b>Co działa / co nie · model bazowy</b><small>uwzględniamy próbkę i dolny przedział 95%</small></header>${segments(rows)}</article>
    </section>

    <section data-pc882-pane="models">
      <article class="pc882-card"><header><b>Ranking modeli</b><small>accuracy + Brier + próbka</small></header>
      <div class="pc882-models">${models.map((x,i)=>`<div class="${i===0?'leader':''}"><em>#${i+1}</em><span><b>${esc(x.label)}</b><small>n=${x.n} · Brier ${x.brier==null?'N/D':x.brier.toFixed(3)}</small></span><strong>${pct(x.accuracy)}</strong></div>`).join('')||'<div class="pc882-empty">Telemetria zbiera próbkę.</div>'}</div></article>
    </section>

    <section data-pc882-pane="adaptive">
      <div class="pc882-kpis">
        <article><span>RAW global</span><b>${pct(global.raw_mean)}</b><small>przed korektą</small></article>
        <article><span>Realnie</span><b>${pct(global.accuracy)}</b><small>wynik historyczny</small></article>
        <article><span>Gap</span><b>${global.gap_pp==null?'N/D':`${Number(global.gap_pp)>=0?'+':''}${Number(global.gap_pp).toFixed(1)} pp`}</b><small>RAW → realnie</small></article>
        <article><span>Wzorce błędów</span><b>${repeated.length}</b><small>${esc(adaptive?.mode||'N/D')} · eff ${Number(adaptive?.training?.effective_rows||0).toFixed(0)}</small></article>
      </div>
      <article class="pc882-card"><header><b>Największe powtarzalne błędy</b><small>Adaptive wykorzystuje je do ograniczonej korekty</small></header>
      <div class="pc882-errors">${repeated.map(x=>`<div><span><b>${esc(String(x.key||'').split('|').slice(1).join(' · '))}</b><small>${esc(String(x.key||'').split('|')[0]||'model')} · n≈${Number(x.effective_n||0).toFixed(0)} · ${esc(x.evidence||'')}</small></span><em>RAW ${pct(x.raw_mean)} → ${pct(x.accuracy)}</em><strong class="${Number(x.gap_pp||0)<0?'bad':'good'}">${Number(x.gap_pp||0)>=0?'+':''}${Number(x.gap_pp||0).toFixed(1)} pp</strong></div>`).join('')||'<div class="pc882-empty">Brak powtarzalnych błędów.</div>'}</article>
    </section>
    <p class="pc882-note">Statystyki wpływają na <b>ranking par Generatora</b> dopiero przy sensownej próbce. Nie zmieniają oceny FINAL. n liczy unikalne zdarzenia na model i mecz; równoważne linie 10.5/11.5 są scalone. Zdarzenia jednego meczu są skorelowane. Proxy selektora nie jest skutecznością zapisanych par. Modele mogą mieć różne próbki. Player Intelligence i Accuracy Lab zostają SHADOW.</p>`;

  const head=host.querySelector('.pc77-head');
  if(previous)previous.replaceWith(dash);
  else {if(head)head.after(dash);else host.prepend(dash);collapseOld(host,dash);}
  host.classList.remove('pc885-loading');
  host.querySelector('.pc885-loading-note')?.remove();
  window.TENIS_AI_V883?.cleanupStats?.();

  let saved='overview';
  try{saved=localStorage.getItem(TAB_KEY)||'overview'}catch{}
  activate(dash,saved);

  dash.querySelectorAll('[data-pc882-tab]').forEach(btn=>btn.addEventListener('click',()=>activate(dash,btn.dataset.pc882Tab)));
  dash.querySelectorAll('[data-pc882-period]').forEach(btn=>btn.addEventListener('click',()=>{
    try{localStorage.setItem(PERIOD_KEY,btn.dataset.pc882Period)}catch{}
    renderStats882().catch(console.error);
  }));

  document.dispatchEvent(new CustomEvent('tenis-ai:stats-dashboard-ready',{detail:{version:RUNTIME_FIX}}));
}

function compactAdaptive(){
  const h=document.querySelector('#v79-health');
  if(!h)return;
  if(h.dataset.v882Ready!=='1'){
    h.dataset.v882Ready='1';
    let saved='0';
    try{saved=localStorage.getItem('tenis-ai-v882-adaptive-expanded')||'0'}catch{}
    if(saved!=='1')h.classList.remove('expanded');
  }
  const b=h.querySelector('.v853b-health-toggle');
  if(b&&b.dataset.v882Bound!=='1'){
    b.dataset.v882Bound='1';
    b.addEventListener('click',()=>setTimeout(()=>{
      try{localStorage.setItem('tenis-ai-v882-adaptive-expanded',h.classList.contains('expanded')?'1':'0')}catch{}
    },0));
  }
}

function decorateGenerator(){
  const builder=document.querySelector('.sc82-builder');
  if(builder){
    const labels={balanced:'🎯 Bet Builder CORE',stable:'🛡️ Stabilny CORE',strong:'🔥 Najmocniejsze pary',experimental:'🧪 Model Test / SHADOW'};
    builder.querySelectorAll('[data-sc-profile]').forEach(x=>{if(labels[x.dataset.scProfile])x.textContent=labels[x.dataset.scProfile]});
    const head=builder.querySelector('.sc88-generator-head');
    if(head){
      head.querySelector('b')?.replaceChildren(document.createTextNode('Pair-first ranking + Adaptive PROD'));
      const sm=head.querySelector('small');
      if(sm)sm.textContent='Najpierw para 2 rynków, potem ranking meczu. Historia koryguje tylko selekcję.';
    }
  }
  document.querySelectorAll('.sc82-draft-list article').forEach(x=>x.classList.add('sc882-match-card'));
}

function decorateTop(){
  const api=window.TENIS_AI_MODEL_API;
  const bridge=window.TENIS_AI_PROJECT_UI;
  if(!api?.allSignals)return;

  document.querySelectorAll('.p751-top button').forEach(btn=>{
    if(btn.querySelector('.pc882-top-meta'))return;
    let k=btn.dataset.p751Open||'';
    try{k=decodeURIComponent(k)}catch{}
    let m=null;
    try{m=bridge?.findMatch?.(k)||null}catch{}
    if(!m)return;

    let sig=null;
    try{sig=(api.allSignals(m)||[]).filter(x=>num(x?.v)!=null).sort((a,b)=>Number(b.v)-Number(a.v))[0]||null}catch{}
    if(!sig)return;

    let al=null;
    try{al=window.TENIS_AI_AUTOLEARN_V84?.scoreFor?.(m,sig)||null}catch{}
    const prior=priorFor(m,sig);
    const delta=num(al?.adaptive_delta_pp);
    const meta=document.createElement('small');
    meta.className='pc882-top-meta';
    meta.textContent=[
      `${tour(m.tour)} · ${surf(m.surface)}`,
      delta!=null?`Adaptive ${delta>=0?'+':''}${delta.toFixed(1)} pp`:null,
      prior.n>=10?`hist ${Math.round(prior.accuracy)}% n=${prior.n}`:null
    ].filter(Boolean).join(' · ');
    btn.append(meta);
  });
}

function brand(){
  window.TENIS_AI_APPLY_META?.();
}

function wrapStats(){
  if(typeof renderStats!=='function'||renderStats.__v882Wrapped)return false;
  const base=renderStats;
  const wrapped=function(){
    const r=base.apply(this,arguments);
    // Async page completion emits tenis-ai:stats-ready. No timer race.
    return r;
  };
  wrapped.__v882Wrapped=true;
  renderStats=wrapped;
  return true;
}

function polish(){
  brand();
  compactAdaptive();
  decorateGenerator();
  decorateTop();
}

function relevantPolishClick(event){
  return !!event.target?.closest?.('[data-view="stats"],[data-pc882-period],[data-pc882-tab],[data-sc-profile],[data-sc-generate],.p751-top button,.v853b-health-toggle');
}

function boot(){
  wrapStats();
  polish();

  // One bounded stabilization for data-loaded widgets. Previous builds ran
  // four delayed full polish passes (250/700/1500/2600 ms), causing visible shifts.
  setTimeout(()=>{
    wrapStats();
    polish();
    if(document.querySelector('#pc77')&&!document.querySelector('#pc882-dashboard'))renderStats882().catch(console.error);
  },700);
}

document.addEventListener('tenis-ai:stats-ready',()=>{
  polish();
  renderStats882().catch(console.error);
});
document.addEventListener('click',event=>{
  if(!relevantPolishClick(event))return;
  queueMicrotask(polish);
},true);
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_V882=Object.freeze({version:VERSION,runtimeFix:RUNTIME_FIX,priorFor,renderStats:renderStats882,polish});
})();