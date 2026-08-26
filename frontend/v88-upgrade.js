/* Tenis AI v8.8 - Generator + Performance Intelligence */
(()=>{
'use strict';

const VERSION='v8.8';
const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));
const pct=x=>num(x)==null?'N/D':Number(x).toFixed(1).replace('.0','')+'%';
const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');
const marketAlias=x=>({
  match_winner:'match_win',
  set1_winner:'set1_win',
  set2_winner:'set2_win',
  set3_winner:'set3_win'
})[String(x||'').toLowerCase()]||String(x||'').toLowerCase();

function signalLine(s){
  const direct=num(s?.line??s?.selected_line??s?.suggested_line);
  if(direct!=null)return direct;

  const parts=String(s?.key||s?.signal_key||'').split('|');
  const candidate=num(parts?.[1]);
  return candidate;
}

function adaptiveSignal(match,signal){
  const market=marketAlias(signal?.market);
  const pick=norm(signal?.pick);
  const line=signalLine(signal);
  const key=String(signal?.key||signal?.signal_key||'');

  const rows=[
    ...(Array.isArray(match?.adaptive_learning_v79?.signals)
      ? match.adaptive_learning_v79.signals : []),
    ...(Array.isArray(match?.autolearn_v84?.signals)
      ? match.autolearn_v84.signals : [])
  ];

  return rows.find(x=>{
    const xKey=String(x?.key||x?.signal_key||'');
    if(key&&xKey===key)return true;

    if(marketAlias(x?.market)!==market)return false;
    if(norm(x?.pick)!==pick)return false;

    if(line!=null){
      const xl=signalLine(x);
      if(xl==null||Math.abs(xl-line)>.001)return false;
    }

    return true;
  })||null;
}

function wrapAutoLearn(){
  const api=window.TENIS_AI_AUTOLEARN_V84;

  if(!api||api.__v88Wrapped||typeof api.scoreFor!=='function')
    return false;

  const base=api.scoreFor.bind(api);

  api.scoreFor=function(match,signal){
    const raw=base(match,signal);
    const learned=adaptiveSignal(match,signal);
    const prod=learned?.adaptive_prod_v79||{};

    const final=num(
      learned?.final_score ??
      learned?.adaptive_prod_score ??
      prod?.final_score ??
      raw?.final_score ??
      raw?.adaptive_prod_score ??
      raw?.adaptive_prod_v79?.final_score
    );

    if(final==null)return raw;

    const rawEnsemble=num(
      raw?.ensemble ??
      learned?.ensemble_raw ??
      learned?.raw_score ??
      prod?.raw_score
    );

    return {
      ...(raw||{}),
      adaptive_prod_score:final,
      adaptive_delta_pp:num(
        learned?.adaptive_delta_pp ??
        learned?.delta_pp ??
        prod?.delta_pp
      ),
      adaptive_evidence:String(
        prod?.status ??
        prod?.evidence ??
        match?.adaptive_learning_v79?.status ??
        'COLLECTING'
      ),
      raw_ensemble:rawEnsemble,
      ensemble:final,
      status:String(raw?.status||'ACTIVE').toUpperCase()==='ACTIVE'
        ? 'ACTIVE'
        : (raw?.status||'ACTIVE')
    };
  };

  api.__v88Wrapped=true;
  api.v88AdaptiveProd=true;

  console.info('[Tenis AI] v8.8 Adaptive PROD bridge active');
  return true;
}

function decorateGenerator(){
  const builder=document.querySelector('.sc82-builder');
  if(!builder||builder.querySelector('.sc88-generator-head'))return;

  builder.insertAdjacentHTML('afterbegin',`
    <div class="sc88-generator-head">
      <div>
        <span>GENERATOR AI v8.8</span>
        <b>Adaptive PROD jako glowny wynik</b>
        <small>RAW Ensemble zostaje do audytu. Player Intelligence i Accuracy Lab nadal SHADOW.</small>
      </div>
      <em>PROD ACTIVE</em>
    </div>
  `);
}

/* ===================== STATS ===================== */

function history(){
  try{
    return Array.isArray(historyRows)?historyRows:[];
  }catch{
    return [];
  }
}

function flattenHistory(){
  const out=[];

  for(const m of history()){
    const time=new Date(
      m?.scheduled_time ??
      m?.captured_at ??
      m?.first_captured_at ??
      0
    );

    if(!Number.isFinite(time.getTime()))continue;

    for(const s of (m?.signals||[])){
      if(s?.result!=='hit'&&s?.result!=='miss')continue;

      out.push({
        time,
        hit:s.result==='hit',
        score:num(s.score),
        market:String(s.label||s.market||'Inny'),
        marketId:String(s.market||'other'),
        source:String(s.source_model||'legacy'),
        tour:String(m.tour||'N/D').toUpperCase(),
        surface:String(m.surface||'N/D').toUpperCase(),
        version:String(m.model_version||'N/D')
      });
    }
  }

  return out;
}

function stat(rows){
  const n=rows.length;
  const hits=rows.reduce((a,x)=>a+(x.hit?1:0),0);
  return {
    n,
    hits,
    misses:n-hits,
    accuracy:n?hits*100/n:null
  };
}

function groups(rows,key){
  const map=new Map();

  rows.forEach(x=>{
    const k=key(x);
    if(!map.has(k))map.set(k,[]);
    map.get(k).push(x);
  });

  return [...map.entries()].map(([name,list])=>({
    name,
    ...stat(list)
  }));
}

function confidenceBand(v){
  if(v==null)return 'N/D';
  if(v<72)return '<72';
  if(v<75)return '72-74';
  if(v<80)return '75-79';
  if(v<85)return '80-84';
  if(v<90)return '85-89';
  return '90+';
}

function confidenceRows(rows){
  const order=['<72','72-74','75-79','80-84','85-89','90+'];

  return order.map(name=>{
    const list=rows.filter(x=>confidenceBand(x.score)===name);
    const st=stat(list);

    const scored=list.filter(x=>x.score!=null);
    const predicted=scored.length
      ? scored.reduce((a,x)=>a+x.score,0)/scored.length
      : null;

    return {
      name,
      ...st,
      predicted,
      gap:st.accuracy!=null&&predicted!=null
        ? st.accuracy-predicted
        : null
    };
  }).filter(x=>x.n);
}

async function json(url){
  try{
    const r=await fetch(url+'?v88='+Date.now(),{cache:'no-store'});
    return r.ok?await r.json():{};
  }catch{
    return {};
  }
}

function width(v){
  return Math.max(0,Math.min(100,Number(v)||0));
}

function modelRows(telemetry){
  const models=telemetry?.scopes?.['30d']?.by_model||{};

  return Object.entries(models)
    .map(([id,x])=>({
      id,
      label:x?.label||id,
      n:Number(x?.selected_n||0),
      accuracy:num(x?.accuracy),
      brier:num(x?.brier),
      roi:num(x?.roi)
    }))
    .filter(x=>x.n)
    .sort((a,b)=>{
      const aa=a.n>=10&&a.accuracy!=null?a.accuracy:-1;
      const bb=b.n>=10&&b.accuracy!=null?b.accuracy:-1;
      return bb-aa||b.n-a.n;
    });
}

function segmentRows(rows){
  const min=10;

  const all=[
    ...groups(rows,x=>x.market).map(x=>({...x,type:'Rynek'})),
    ...groups(rows,x=>x.source).map(x=>({...x,type:'Model'})),
    ...groups(rows,x=>x.tour).map(x=>({...x,type:'Tour'})),
    ...groups(rows,x=>x.surface).map(x=>({...x,type:'Nawierzchnia'}))
  ].filter(x=>x.n>=min&&x.accuracy!=null);

  return {
    best:[...all]
      .sort((a,b)=>b.accuracy-a.accuracy||b.n-a.n)
      .slice(0,6),

    weak:[...all]
      .sort((a,b)=>a.accuracy-b.accuracy||b.n-a.n)
      .slice(0,6)
  };
}

function renderConfidence(rows){
  const buckets=confidenceRows(rows);

  if(!buckets.length)
    return '<div class="pc88-empty">Brak danych do kalibracji.</div>';

  return `<div class="pc88-confidence">
    ${buckets.map(x=>`
      <div class="pc88-conf-row">
        <div><b>${esc(x.name)}</b><small>n=${x.n}</small></div>

        <div class="pc88-track">
          <i style="width:${width(x.accuracy)}%"></i>
          ${x.predicted!=null
            ? `<em style="left:${width(x.predicted)}%"></em>`
            : ''}
        </div>

        <div>
          <b>${pct(x.accuracy)}</b>
          <small>
            model ${pct(x.predicted)}
            ${x.gap==null?'':` · ${x.gap>=0?'+':''}${x.gap.toFixed(1)} pp`}
          </small>
        </div>
      </div>
    `).join('')}
  </div>`;
}

function renderMarkets(rows){
  const markets=groups(rows,x=>x.market)
    .filter(x=>x.n>=10)
    .sort((a,b)=>b.n-a.n)
    .slice(0,8);

  if(!markets.length)
    return '<div class="pc88-empty">Za mala probka rynkow.</div>';

  return `<div class="pc88-market-bars">
    ${markets.map(x=>`
      <div class="pc88-market-row">
        <div>
          <b>${esc(x.name)}</b>
          <small>n=${x.n}</small>
        </div>

        <div class="pc88-track">
          <i style="width:${width(x.accuracy)}%"></i>
        </div>

        <strong>${pct(x.accuracy)}</strong>
      </div>
    `).join('')}
  </div>`;
}

function renderSegments(data){
  const section=(title,rows,cls)=>`
    <div class="pc88-segment-col ${cls}">
      <h4>${title}</h4>

      ${rows.length?rows.map(x=>`
        <div class="pc88-segment">
          <span>${esc(x.type)}</span>
          <div>
            <b>${esc(x.name)}</b>
            <small>${x.hits}/${x.n}</small>
          </div>
          <strong>${pct(x.accuracy)}</strong>
        </div>
      `).join(''):'<div class="pc88-empty">Brak odpowiedniej probki.</div>'}
    </div>`;

  return `<div class="pc88-segments">
    ${section('Najmocniejsze',data.best,'good')}
    ${section('Do poprawy',data.weak,'bad')}
  </div>`;
}

async function injectStats(){
  const host=document.querySelector('#pc77');
  if(!host)return;

  document.querySelector('#pc88-dashboard')?.remove();

  const all=flattenHistory();
  const now=Date.now();
  const d30=all.filter(x=>now-x.time.getTime()<=30*86400000);

  const wantedVersion=String(
    window.TENIS_AI_META?.calibrationModelVersion||''
  );

  const same=d30.filter(x=>x.version===wantedVersion);
  const rows=same.length>=20?same:d30;
  const overall=stat(rows);

  const markets=groups(rows,x=>x.market)
    .filter(x=>x.n>=10&&x.accuracy!=null);

  const best=[...markets]
    .sort((a,b)=>b.accuracy-a.accuracy||b.n-a.n)[0];

  const weak=[...markets]
    .sort((a,b)=>a.accuracy-b.accuracy||b.n-a.n)[0];

  const [adaptive,telemetry]=await Promise.all([
    json('data/adaptive_learning_v79.json'),
    json('data/model_telemetry_v84c.json')
  ]);

  if(!document.querySelector('#pc77'))return;

  const global=adaptive?.cells?.global?.global||{};
  const repeated=Array.isArray(adaptive?.repeated_errors)
    ? adaptive.repeated_errors.slice(0,8)
    : [];

  const models=modelRows(telemetry).slice(0,10);
  const segments=segmentRows(rows);

  const dashboard=document.createElement('section');
  dashboard.id='pc88-dashboard';
  dashboard.className='pc88-dashboard';

  dashboard.innerHTML=`
    <header class="pc88-head">
      <div>
        <span>CENTRUM ANALITYCZNE v8.8</span>
        <h3>Co dziala, co nie i gdzie model sie myli?</h3>
        <p>30 dni · skutecznosc · kalibracja · modele · Adaptive PROD</p>
      </div>
      <b>${rows.length} wynikow</b>
    </header>

    <div class="pc88-kpis">
      <article>
        <span>Skutecznosc</span>
        <b>${pct(overall.accuracy)}</b>
        <small>${overall.hits} HIT · ${overall.misses} MISS</small>
      </article>

      <article class="good">
        <span>Najlepszy rynek</span>
        <b>${best?esc(best.name):'N/D'}</b>
        <small>${best?pct(best.accuracy)+' · n='+best.n:'za mala probka'}</small>
      </article>

      <article class="bad">
        <span>Najsłabszy rynek</span>
        <b>${weak?esc(weak.name):'N/D'}</b>
        <small>${weak?pct(weak.accuracy)+' · n='+weak.n:'za mala probka'}</small>
      </article>

      <article>
        <span>Adaptive global</span>
        <b>${pct(global.accuracy)}</b>
        <small>
          RAW ${pct(global.raw_mean)}
          ${global.gap_pp==null?'':` · ${Number(global.gap_pp)>=0?'+':''}${Number(global.gap_pp).toFixed(1)} pp`}
        </small>
      </article>
    </div>

    <div class="pc88-two">
      <section class="pc88-card">
        <header>
          <b>Confidence vs rzeczywistosc</b>
          <small>pasek = realny HIT% · kreska = confidence modelu</small>
        </header>
        ${renderConfidence(rows)}
      </section>

      <section class="pc88-card">
        <header>
          <b>Najczesciej grane rynki</b>
          <small>minimum 10 rozliczen</small>
        </header>
        ${renderMarkets(rows)}
      </section>
    </div>

    <section class="pc88-card">
      <header>
        <b>Co dziala / co nie</b>
        <small>rynek · model · tour · nawierzchnia</small>
      </header>
      ${renderSegments(segments)}
    </section>

    <section class="pc88-card">
      <header>
        <b>Ranking modeli · 30 dni</b>
        <small>accuracy + Brier + realna probka</small>
      </header>

      <div class="pc88-models">
        ${models.length?models.map((x,i)=>`
          <article class="${i===0?'leader':''}">
            <span>#${i+1}</span>
            <div>
              <b>${esc(x.label)}</b>
              <small>
                n=${x.n} · Brier ${x.brier==null?'N/D':x.brier.toFixed(3)}
              </small>
            </div>
            <strong>${pct(x.accuracy)}</strong>
            <em>${x.roi==null?'ROI N/D':'ROI '+pct(x.roi)}</em>
          </article>
        `).join(''):'<div class="pc88-empty">Telemetria zbiera probke.</div>'}
      </div>
    </section>

    <section class="pc88-card">
      <header>
        <b>Adaptive PROD · powtarzalne bledy</b>
        <small>${repeated.length} najwazniejszych wzorcow z raportu uczacego</small>
      </header>

      <div class="pc88-errors">
        ${repeated.length?repeated.map(x=>`
          <div class="pc88-error">
            <div>
              <b>${esc(String(x.key||'').split('|').slice(1).join(' · '))}</b>
              <small>
                ${esc(String(x.key||'').split('|')[0]||'model')}
                · n≈${Number(x.effective_n||0).toFixed(0)}
                · ${esc(x.evidence||'')}
              </small>
            </div>

            <span>
              RAW ${pct(x.raw_mean)} → realnie ${pct(x.accuracy)}
            </span>

            <strong class="${Number(x.gap_pp||0)<0?'down':'up'}">
              ${Number(x.gap_pp||0)>=0?'+':''}${Number(x.gap_pp||0).toFixed(1)} pp
            </strong>
          </div>
        `).join(''):'<div class="pc88-empty">Brak powtarzalnych wzorcow bledow.</div>'}
      </div>
    </section>

    <p class="pc88-note">
      Procent bez odpowiedniej probki nie jest traktowany jako mocny dowod.
      Player Intelligence i Accuracy Lab nadal pozostaja SHADOW.
    </p>
  `;

  const head=host.querySelector('.pc77-head');
  if(head)head.after(dashboard);
  else host.prepend(dashboard);
}

function wrapStats(){
  if(typeof renderStats!=='function'||renderStats.__v88Wrapped)
    return false;

  const base=renderStats;

  const wrapped=function(){
    const r=base.apply(this,arguments);

    [120,500,1200].forEach(ms=>
      setTimeout(()=>injectStats().catch(console.error),ms)
    );

    return r;
  };

  wrapped.__v88Wrapped=true;
  renderStats=wrapped;

  return true;
}


function applyV88Brand(){
  document.documentElement.dataset.tenisAiFeatureVersion='v8.8';
  document.title='Tenis AI · v8.8';

  const copy=document.querySelector('.brand-copy p');
  if(copy){
    copy.textContent='Tenis AI v8.8 · Decision + Generator + Stats + Adaptive PROD';
  }
}

function boot(){
  applyV88Brand();
  wrapAutoLearn();
  wrapStats();
  decorateGenerator();

  [250,800,1600].forEach(ms=>setTimeout(()=>{
    wrapAutoLearn();
    wrapStats();
    decorateGenerator();
  },ms));
}

document.addEventListener('click',()=>{
  setTimeout(decorateGenerator,30);
},true);

if(document.readyState==='loading')
  document.addEventListener('DOMContentLoaded',boot,{once:true});
else
  boot();

window.TENIS_AI_V88={
  version:VERSION,
  wrapAutoLearn,
  injectStats,
  decorateGenerator
};

})();
