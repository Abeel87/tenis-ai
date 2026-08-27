/* Tenis AI v7.7 — Model Performance Center */
(() => {
  if(typeof renderStats!=='function') return;

  const legacyRenderStats=renderStats;
  const KEY='tenis-ai-v77-performance-state';
  const CURRENT_MODEL_VERSION='v7.8D-calibration-guard';
  const state=Object.assign({period:'all',tour:'all',surface:'all',minSample:10},readState());
  let extras=null, extrasPromise=null;

  const esc77=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct77=x=>x==null||!Number.isFinite(Number(x))?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const num77=x=>Number.isFinite(Number(x))?Number(x):0;
  const fmtInt=x=>Math.round(num77(x)).toLocaleString('pl-PL');

  function readState(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')||{}}catch{return {}}}
  function saveState(){try{localStorage.setItem(KEY,JSON.stringify(state))}catch{}}
  function history(){try{return Array.isArray(historyRows)?historyRows:[]}catch{return []}}
  function baseStats(){try{return statsData||{}}catch{return {}}}
  async function j(url){try{const r=await fetch(url+'?v77='+Date.now());return r.ok?await r.json():{}}catch{return {}}}
  function loadExtras(){
    if(extras)return Promise.resolve(extras);
    if(extrasPromise)return extrasPromise;
    extrasPromise=Promise.all([
      j('data/pbp_tracker_stats.json'),j('data/pbp_backtest.json'),j('data/market_lab_stats.json'),j('data/meta.json')
    ]).then(([tracker,backtest,lab,meta])=>extras={tracker,backtest,lab,meta}).catch(()=>extras={tracker:{},backtest:{},lab:{},meta:{}});
    return extrasPromise;
  }

  function flatten(rows=history()){
    const out=[];
    for(const m of rows){
      const d=new Date(m.scheduled_time||m.captured_at||m.first_captured_at||0);
      if(!Number.isFinite(d.getTime()))continue;
      for(const s of (m.signals||[])){
        if(s.result!=='hit'&&s.result!=='miss')continue;
        out.push({
          time:d,
          day:dayKey(d),
          hit:s.result==='hit',
          result:s.result,
          score:Number(s.score),
          label:s.label||s.market||'Rynek',
          market:s.market||'inne',
          tour:String(m.tour||'N/D').toUpperCase(),
          surface:normSurface(m.surface),
          tournament:m.tournament||'N/D',
          version:m.model_version||'N/D',
          legacy:m.model_version!==CURRENT_MODEL_VERSION,
          sourceModel:s.source_model||'legacy',
          matchKey:m.match_key||String(m.match_id||[m.p1,m.p2,m.scheduled_time].join('|'))
        });
      }
    }
    return out;
  }
  function dayKey(d){return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
  function normSurface(s){const x=String(s||'N/D').trim().toLowerCase();if(!x)return'N/D';if(x.includes('hard'))return'HARD';if(x.includes('clay'))return'CLAY';if(x.includes('grass'))return'GRASS';if(x.includes('carpet'))return'CARPET';return x.toUpperCase()}
  function scoreBand(v){if(!Number.isFinite(v))return'N/D';if(v<72)return'<72';if(v<75)return'72–74';if(v<80)return'75–79';if(v<85)return'80–84';if(v<90)return'85–89';return'90+'}

  function periodBounds(period,offset=0){
    const now=new Date();
    if(period==='all')return null;
    if(period==='today'){
      const start=new Date(now.getFullYear(),now.getMonth(),now.getDate());
      start.setDate(start.getDate()-offset);
      const end=new Date(start);end.setDate(end.getDate()+1);
      return [start,end];
    }
    const days=period==='7d'?7:30;
    const end=new Date(now.getTime()-offset*days*86400000);
    const start=new Date(end.getTime()-days*86400000);
    return [start,end];
  }
  function filtered(all,period=state.period,previous=false){
    const bounds=periodBounds(period,previous?1:0);
    return all.filter(x=>{
      if(x.legacy)return false;
      if(bounds&&(x.time<bounds[0]||x.time>=bounds[1]))return false;
      if(state.tour!=='all'&&x.tour!==state.tour)return false;
      if(state.surface!=='all'&&x.surface!==state.surface)return false;
      return true;
    });
  }
  function stats(rows){const n=rows.length,h=rows.reduce((a,x)=>a+(x.hit?1:0),0);return {n,h,m:n-h,accuracy:n?h*100/n:null,matches:new Set(rows.map(x=>x.matchKey)).size}}
  function group(rows,keyfn){const m=new Map();for(const x of rows){const k=keyfn(x);if(!m.has(k))m.set(k,[]);m.get(k).push(x)}return [...m.entries()].map(([name,r])=>({name,...stats(r)}))}
  function wilson(h,n){if(!n)return null;const z=1.96,p=h/n,d=1+z*z/n,c=(p+z*z/(2*n))/d,half=z*Math.sqrt((p*(1-p)+z*z/(4*n))/n)/d;return [Math.max(0,(c-half)*100),Math.min(100,(c+half)*100)]}
  function sampleMeta(n){if(n>=50)return['MOCNA','strong'];if(n>=20)return['ŚREDNIA','medium'];if(n>=10)return['OK','ok'];if(n>=5)return['MAŁA','small'];return['BARDZO MAŁA','tiny']}
  function sampleBadge(n){const [t,c]=sampleMeta(n);return `<em class="pc77-sample ${c}">${t} próba · ${n} wyników</em>`}
  function ciText(x){const ci=wilson(x.h,x.n);return ci?`95% CI ${ci[0].toFixed(0)}–${ci[1].toFixed(0)}%`:'CI —'}
  function deltaText(cur,prev){if(cur.accuracy==null||prev.accuracy==null)return {txt:'—',cls:''};const d=cur.accuracy-prev.accuracy;return {txt:`${d>=0?'+':''}${d.toFixed(1)} pp`,cls:d>=0?'up':'down'}}
  function periodLabel(){return ({today:'Dzisiaj','7d':'7 dni','30d':'30 dni',all:'Wszystko'})[state.period]||'Wszystko'}

  function topSegments(rows){
    const min=Number(state.minSample||10);
    const sets=[
      ...group(rows,x=>x.label).map(x=>({...x,type:'Rynek'})),
      ...group(rows,x=>x.tour).map(x=>({...x,type:'Tour'})),
      ...group(rows,x=>x.surface).map(x=>({...x,type:'Nawierzchnia'})),
      ...group(rows,x=>x.tournament).map(x=>({...x,type:'Turniej'}))
    ].filter(x=>x.n>=min&&x.accuracy!=null);
    const best=[...sets].sort((a,b)=>b.accuracy-a.accuracy||b.n-a.n).slice(0,5);
    const weak=[...sets].sort((a,b)=>a.accuracy-b.accuracy||b.n-a.n).slice(0,5);
    return {best,weak};
  }

  function row(x){return `<div class="pc77-row"><div><b>${esc77(x.name)}</b><small>${x.h} ✅ · ${x.m} ❌ · ${ciText(x)}</small></div><div><strong>${pct77(x.accuracy)}</strong>${sampleBadge(x.n)}</div></div>`}
  function segmentRow(x){return `<div class="pc77-segment"><span>${esc77(x.type)}</span><div><b>${esc77(x.name)}</b><small>${x.h}/${x.n} · ${ciText(x)}</small></div><strong>${pct77(x.accuracy)}</strong>${sampleBadge(x.n)}</div>`}
  function section(title,rows,open=false,limit=50){if(!rows.length)return'';const sorted=[...rows].sort((a,b)=>b.n-a.n||b.accuracy-a.accuracy).slice(0,limit);return `<details class="pc77-details" ${open?'open':''}><summary><b>${title}</b><span>${sorted.length} pozycji</span></summary><div class="pc77-table">${sorted.map(row).join('')}</div></details>`}

  function trend(rows){
    const days=group(rows,x=>x.day).map(x=>({...x,date:x.name})).sort((a,b)=>a.date.localeCompare(b.date)).slice(-30);
    if(!days.length)return '<div class="pc77-empty">Jeszcze brak rozliczonych dni dla wybranego filtra.</div>';
    if(days.length===1)return `<div class="pc77-one-day"><b>${pct77(days[0].accuracy)}</b><span>${esc77(days[0].date)} · ${days[0].h}/${days[0].n}</span></div>`;
    const W=320,H=122,pad=22,minY=40,maxY=100;
    const pts=days.map((d,i)=>{const x=pad+i*(W-pad*2)/(days.length-1);const a=Math.max(minY,Math.min(maxY,d.accuracy||0));const y=H-pad-(a-minY)/(maxY-minY)*(H-pad*2);return {x,y,d}});
    const poly=pts.map(p=>`${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const dots=pts.map(p=>`<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3"><title>${esc77(p.d.date)} · ${pct77(p.d.accuracy)} · n=${p.d.n}</title></circle>`).join('');
    const avg=stats(rows).accuracy;
    return `<div class="pc77-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Trend skuteczności"><line x1="${pad}" y1="${H-pad}" x2="${W-pad}" y2="${H-pad}"/><line x1="${pad}" y1="${pad}" x2="${pad}" y2="${H-pad}"/><line class="target" x1="${pad}" y1="${(H-pad-(72-minY)/(maxY-minY)*(H-pad*2)).toFixed(1)}" x2="${W-pad}" y2="${(H-pad-(72-minY)/(maxY-minY)*(H-pad*2)).toFixed(1)}"/><polyline points="${poly}"/>${dots}</svg><div><span>${esc77(days[0].date)}</span><b>Śr. ${pct77(avg)}</b><span>${esc77(days.at(-1).date)}</span></div></div>`;
  }

  function modelValidation(cur,ex){
    const t=ex?.tracker||{},b=ex?.backtest||{},l=ex?.lab||{},m=ex?.meta||{};
    const rows=[
      {name:'Główna historia zamrożonych sygnałów',value:cur.accuracy,n:cur.n,note:'Adaptive + PBP game states; źródło modelu zapisywane per sygnał od v7.7.2'},
      {name:'Early Hold · production PBP',value:t.green_72_plus?.accuracy,n:t.green_72_plus?.settled||0,note:`kierunek TAK/NIE · confidence=max(p,1-p) · ${t.production_matches_pending||0} meczów czeka`},
      {name:'Early Hold · walk-forward',value:b.overall?.green_accuracy,n:b.overall?.green_n||0,note:'diagnostyczny replay chronologiczny, nie pełny model produkcyjny'},
      {name:'Market Lab · zielone',value:l.overall?.green_accuracy,n:l.overall?.green_n||0,note:`LAB · ${m.market_lab_tracker_settled_total||0} rozliczone mecze źródłowe`}
    ];
    return `<div class="pc77-models">${rows.map(x=>`<div class="pc77-model-row"><div><b>${esc77(x.name)}</b><small>${esc77(x.note)}</small></div><strong>${pct77(x.value)}</strong>${sampleBadge(x.n)}</div>`).join('')}<div class="pc77-model-note"><b>Consensus / Serve/Return / Form / Surface</b><span>N/D osobno — te warianty wspierają analizę, ale nie są jeszcze zamrażane jako osobne typy w historii. Nie będziemy udawać skuteczności, której nie mierzymy.</span></div></div>`
  }

  function dataQuality(ex,bs){const m=ex?.meta||{},t=ex?.tracker||{},l=ex?.lab||{};return `<div class="pc77-quality-grid">
    <div><span>Aktualne mecze</span><b>${fmtInt(m.visible_fixtures)}</b><small>${fmtInt(m.model_ready)} model-ready</small></div>
    <div><span>Profile zawodników</span><b>${fmtInt(m.tendencies_v71_profiles)}</b><small>tendencies 5/10/20</small></div>
    <div><span>Serve Props ready</span><b>${fmtInt(m.serve_props_v72_ready_matches)}</b><small>z pełną próbką</small></div>
    <div><span>PBP Early Hold</span><b>${fmtInt(m.pbp_v7_ready_matches)} / ${fmtInt(m.pbp_v7_target_matches)}</b><small>gotowe / cel</small></div>
    <div><span>PBP production</span><b>${fmtInt(t.production_matches_settled)}</b><small>${fmtInt(t.production_matches_pending)} oczekuje</small></div>
    <div><span>Market Lab</span><b>${fmtInt(l.overall?.n)}</b><small>${fmtInt(m.market_lab_tracker_settled_total)} mecze rozliczone</small></div>
    <div><span>Historia meczów</span><b>${fmtInt(bs.matches_tracked)}</b><small>${fmtInt(bs.matches_pending)} oczekuje</small></div>
    <div><span>Wyłączone z accuracy</span><b>${fmtInt(bs.excluded_signals)}</b><small>brak jednoznacznego wyniku</small></div>
  </div>`}

  function pbpPanel(ex){
    const b=ex?.backtest||{},t=ex?.tracker||{};
    const metrics=Object.entries(b.metrics||{}).map(([name,v])=>({name,n:v.green_n||0,h:Math.round((v.green_accuracy||0)*(v.green_n||0)/100),m:Math.max(0,(v.green_n||0)-Math.round((v.green_accuracy||0)*(v.green_n||0)/100)),accuracy:v.green_accuracy,brier:v.brier})).filter(x=>x.n).sort((a,b)=>b.n-a.n);
    return `<details class="pc77-details"><summary><b>🧪 Early Hold / PBP</b><span>production + walk-forward</span></summary><div class="pc77-pbp-kpis"><div><span>Production</span><b>${pct77(t.green_72_plus?.accuracy)}</b><small>n=${t.green_72_plus?.settled||0}</small></div><div><span>Replay green</span><b>${pct77(b.overall?.green_accuracy)}</b><small>n=${b.overall?.green_n||0}</small></div><div><span>Brier replay</span><b>${b.overall?.brier==null?'—':Number(b.overall.brier).toFixed(3)}</b><small>niżej = lepiej</small></div></div>${metrics.length?`<div class="pc77-table">${metrics.map(x=>`<div class="pc77-row"><div><b>${esc77(x.name)}</b><small>green n=${x.n} · Brier ${x.brier==null?'—':Number(x.brier).toFixed(3)}</small></div><div><strong>${pct77(x.accuracy)}</strong>${sampleBadge(x.n)}</div></div>`).join('')}</div>`:'<div class="pc77-empty">Production tracker jeszcze zbiera próbkę.</div>'}<p class="pc77-note">Walk-forward sprawdza chronologiczne tendencje PBP. „Green” w replay to pewny kierunek zdarzenia (max(p,1−p) ≥72), więc nie jest to identyczna próbka jak produkcyjne zielone typy.</p></details>`
  }

  function labPanel(ex){const l=ex?.lab||{};const o=l.overall||{};const rows=Object.entries(l.markets||{}).map(([name,v])=>({name,n:v.green_n||0,h:Math.round((v.green_accuracy||0)*(v.green_n||0)/100),m:Math.max(0,(v.green_n||0)-Math.round((v.green_accuracy||0)*(v.green_n||0)/100)),accuracy:v.green_accuracy,brier:v.brier})).filter(x=>x.n).sort((a,b)=>b.n-a.n);return `<details class="pc77-details"><summary><b>🧰 Market Lab</b><span>osobna walidacja eksperymentalna</span></summary><div class="pc77-pbp-kpis"><div><span>Wszystkie</span><b>${pct77(o.accuracy)}</b><small>n=${o.n||0}</small></div><div><span>Zielone</span><b>${pct77(o.green_accuracy)}</b><small>n=${o.green_n||0}</small></div><div><span>Brier</span><b>${o.brier==null?'—':Number(o.brier).toFixed(3)}</b><small>niżej = lepiej</small></div></div>${rows.length?`<div class="pc77-table">${rows.slice(0,20).map(x=>`<div class="pc77-row"><div><b>${esc77(x.name)}</b><small>green n=${x.n} · Brier ${x.brier==null?'—':Number(x.brier).toFixed(3)}</small></div><div><strong>${pct77(x.accuracy)}</strong>${sampleBadge(x.n)}</div></div>`).join('')}</div>`:''}<p class="pc77-note">LAB ma obecnie mało rozliczonych meczów źródłowych, więc wysokie procenty pojedynczych rynków mogą być przypadkowe. Patrz przede wszystkim na n i Brier.</p></details>`}


  function simpleTrust(n){
    if(n>=50)return {label:'Mocna próba',cls:'strong',note:'wynik jest już oparty na dużej liczbie rozliczeń'};
    if(n>=20)return {label:'Średnia próba',cls:'medium',note:'warto brać wynik pod uwagę, ale nadal obserwujemy'};
    if(n>=10)return {label:'Wstępna próba',cls:'ok',note:'kierunek jest ciekawy, lecz danych wciąż nie ma dużo'};
    if(n>=5)return {label:'Mała próba',cls:'small',note:'procent może mocno się zmienić po kilku kolejnych wynikach'};
    return {label:'Za mało danych',cls:'tiny',note:'nie wyciągamy jeszcze wniosków'};
  }

  function simpleStatus(acc,n){
    if(acc==null||!n)return {label:'Brak danych',cls:'neutral'};
    if(n<5)return {label:'Tylko obserwuj',cls:'warn'};
    if(acc>=80&&n>=20)return {label:'Bardzo dobrze',cls:'good'};
    if(acc>=72)return {label:'Na plus',cls:'good'};
    if(acc>=60)return {label:'Neutralnie',cls:'neutral'};
    return {label:'Uważać',cls:'bad'};
  }

  function simpleMarketRows(rows){
    return group(rows,x=>x.label)
      .filter(x=>x.n>=5&&x.accuracy!=null)
      .sort((a,b)=>{
        const ta=simpleTrust(a.n),tb=simpleTrust(b.n);
        const rank={strong:5,medium:4,ok:3,small:2,tiny:1};
        return (rank[tb.cls]-rank[ta.cls]) || (b.accuracy-a.accuracy) || (b.n-a.n);
      });
  }

  function simpleMarketCard(x){
    const t=simpleTrust(x.n),s=simpleStatus(x.accuracy,x.n);
    return `<article class="pc12-market ${s.cls}">
      <div class="pc12-market-top"><b>${esc77(x.name)}</b><strong>${pct77(x.accuracy)}</strong></div>
      <div class="pc12-market-meta"><span>${x.h} trafionych z ${x.n}</span><em class="${t.cls}">${t.label}</em></div>
      <small>${esc77(t.note)}</small>
    </article>`;
  }

  function simpleOverall(cur,delta){
    const trust=simpleTrust(cur.n),status=simpleStatus(cur.accuracy,cur.n);
    const base=cur.accuracy==null
      ? 'Nie ma jeszcze wystarczająco rozliczonych sygnałów dla tego filtra.'
      : `Model trafił ${cur.h} z ${cur.n} rozliczonych sygnałów w ${cur.matches} meczach.`;
    const caution=cur.matches<10
      ? ' Liczba meczów jest jeszcze mała, więc nie traktuj tego procentu jako stałej skuteczności.'
      : '';
    return `<section class="pc12-summary">
      <div class="pc12-hero ${status.cls}">
        <span>Jak idzie modelowi?</span>
        <b>${pct77(cur.accuracy)}</b>
        <strong>${status.label}</strong>
        <small>${esc77(base+caution)}</small>
      </div>
      <div class="pc12-mini">
        <article><span>Ile mamy danych?</span><b>${cur.n} sygnałów</b><small>${cur.matches} meczów</small></article>
        <article><span>Czy ufać próbce?</span><b class="${trust.cls}">${trust.label}</b><small>${esc77(trust.note)}</small></article>
        <article><span>Zmiana formy</span><b class="${delta.cls}">${delta.txt}</b><small>vs poprzedni taki sam okres</small></article>
      </div>
    </section>`;
  }

  function simpleLegend(){
    return `<div class="pc12-legend">
      <div><i class="good"></i><b>Mocny kierunek</b><span>dobry wynik + sensowna próbka</span></div>
      <div><i class="warn"></i><b>Obserwuj</b><span>procent wygląda dobrze, ale danych jest mało</span></div>
      <div><i class="bad"></i><b>Uważać</b><span>ta grupa nie wspiera dziś kuponu</span></div>
    </div>`;
  }

  function controls(all){
    const surfaces=[...new Set(all.map(x=>x.surface).filter(Boolean))].sort();
    const tours=[...new Set(all.map(x=>x.tour).filter(Boolean))].sort();
    const pbtn=(id,txt)=>`<button type="button" data-pc77-period="${id}" class="${state.period===id?'active':''}">${txt}</button>`;
    return `<div class="pc77-controls"><div class="pc77-periods">${pbtn('today','Dziś')}${pbtn('7d','7 dni')}${pbtn('30d','30 dni')}${pbtn('all','Wszystko')}</div><div class="pc77-selects"><label>Rozgrywki<select data-pc77="tour"><option value="all">Wszystkie</option>${tours.map(x=>`<option value="${esc77(x)}" ${state.tour===x?'selected':''}>${esc77(x)}</option>`).join('')}</select></label><label>Nawierzchnia<select data-pc77="surface"><option value="all">Wszystkie</option>${surfaces.map(x=>`<option value="${esc77(x)}" ${state.surface===x?'selected':''}>${esc77(x)}</option>`).join('')}</select></label><label>Minimum wyników<select data-pc77="minSample">${[5,10,20,50].map(x=>`<option value="${x}" ${Number(state.minSample)===x?'selected':''}>co najmniej ${x}</option>`).join('')}</select></label></div></div>`
  }

  function renderPage(ex){
    const app=document.querySelector('#app');if(!app)return;
    const all=flatten(),rows=filtered(all),prev=filtered(all,state.period,true),cur=stats(rows),pr=stats(prev),delta=deltaText(cur,pr),rank=topSegments(rows),bs=baseStats();
    const byMarket=group(rows,x=>x.label),byTour=group(rows,x=>x.tour),bySurface=group(rows,x=>x.surface),byBand=group(rows,x=>scoreBand(x.score)),byVersion=group(rows,x=>x.version),byTournament=group(rows,x=>x.tournament);
    const legacy=bs.legacy_overall||{};
    const markets=simpleMarketRows(rows);
    const bestMarkets=markets.slice(0,4);
    const weakMarkets=[...markets].filter(x=>x.n>=10).sort((a,b)=>a.accuracy-b.accuracy||b.n-a.n).slice(0,3);
    const appVer=window.TENIS_AI_META?.displayVersion||window.TENIS_AI_META?.appVersion||'v7.8E12';

    app.innerHTML=`<section id="pc77" class="pc77-wrap pc12-wrap">
      <div class="pc77-head pc12-head">
        <div>
          <span>📊 SKUTECZNOŚĆ MODELU</span>
          <h2>Czy modelowi można dziś ufać?</h2>
          <p>Najpierw prosty wniosek. Szczegóły statystyczne są niżej dla chętnych.</p>
        </div>
        <b>${esc77(appVer)}</b>
      </div>

      ${controls(all)}
      ${simpleOverall(cur,delta)}

      <section class="pc77-card pc12-card">
        <div class="pc77-card-head">
          <div><b>🎯 Najlepiej działające rynki</b><small>najpierw patrzymy na wielkość próbki, potem na procent</small></div>
        </div>
        ${bestMarkets.length
          ? `<div class="pc12-market-grid">${bestMarkets.map(simpleMarketCard).join('')}</div>`
          : '<div class="pc77-empty">Za mało rozliczonych wyników, żeby wskazać sensowny rynek.</div>'}
      </section>

      ${weakMarkets.length?`<section class="pc77-card pc12-card">
        <div class="pc77-card-head"><div><b>⚠️ Rynki do obserwacji</b><small>tu skuteczność jest najsłabsza przy sensownej próbce</small></div></div>
        <div class="pc12-market-grid">${weakMarkets.map(simpleMarketCard).join('')}</div>
      </section>`:''}

      <section class="pc77-card pc12-card">
        <div class="pc77-card-head"><div><b>🧭 Jak to czytać?</b><small>bez statystycznego żargonu</small></div></div>
        ${simpleLegend()}
        <p class="pc12-help"><b>Najważniejsze:</b> 90% przy 5 wynikach jest mniej wiarygodne niż 78% przy 50 wynikach. Dlatego aplikacja pokazuje teraz wielkość próbki obok procentu.</p>
      </section>

      <details class="pc77-details pc12-pro">
        <summary><b>📊 Statystyki PRO</b><span>trend, stare wersje, CI, segmenty, PBP, Market Lab</span></summary>
        <div class="pc12-pro-body">
          <section class="pc77-card">
            <div class="pc77-card-head"><div><b>📚 Historia referencyjna</b><small>starsze wersje modelu · nie miesza się z bieżącą</small></div><span>cała baza</span></div>
            <div class="pc77-pbp-kpis">
              <div><span>Skuteczność</span><b>${pct77(legacy.accuracy)}</b><small>${fmtInt(legacy.settled)} wyników</small></div>
              <div><span>Trafione</span><b>${fmtInt(legacy.hits)}</b><small>✅ historyczne</small></div>
              <div><span>Nietrafione</span><b>${fmtInt(legacy.misses)}</b><small>❌ historyczne</small></div>
            </div>
          </section>

          <section class="pc77-card"><div class="pc77-card-head"><div><b>📈 Trend skuteczności</b><small>do 30 ostatnich aktywnych dni</small></div><span>linia 72%</span></div>${trend(rows)}</section>

          <section class="pc77-card"><div class="pc77-card-head"><div><b>🏆 Najmocniejsze i najsłabsze kategorie</b><small>minimum ${Number(state.minSample)} wyników</small></div></div><div class="pc77-rank-grid"><div><h3>Najmocniejsze historycznie</h3>${rank.best.length?rank.best.map(segmentRow).join(''):'<div class="pc77-empty">Brak kategorii z taką próbką.</div>'}</div><div><h3>Do poprawy / obserwacji</h3>${rank.weak.length?rank.weak.map(segmentRow).join(''):'<div class="pc77-empty">Brak kategorii z taką próbką.</div>'}</div></div></section>

          ${section('🎯 Według rynku',byMarket,true)}
          ${section('🏟️ Według rozgrywek',byTour,true)}
          ${section('🧱 Według nawierzchni',bySurface)}
          ${section('⚡ Według siły sygnału',byBand,true)}
          ${section('🧠 Według wersji modelu',byVersion)}
          ${section('🏆 Według turnieju',byTournament,false,20)}

          <details class="pc77-details"><summary><b>🤖 Modele i walidatory</b><span>różne typy testów</span></summary>${modelValidation(cur,ex)}</details>
          <details class="pc77-details"><summary><b>🧬 Jakość danych</b><span>co faktycznie jest gotowe</span></summary>${dataQuality(ex,bs)}</details>
          ${pbpPanel(ex)}
          ${labPanel(ex)}
        </div>
      </details>

      <p class="pc77-final-note"><b>Pamiętaj:</b> skuteczność historyczna nie gwarantuje kolejnego wyniku. Najpierw patrz na wielkość próbki, potem na procent.</p>
    </section>`;
    bind();
    document.dispatchEvent(new CustomEvent('tenis-ai:stats-ready'));
  }

  function bind(){
    document.querySelectorAll('[data-pc77-period]').forEach(b=>b.onclick=()=>{state.period=b.dataset.pc77Period;saveState();renderPage(extras)});
    document.querySelectorAll('[data-pc77]').forEach(el=>el.onchange=()=>{const k=el.dataset.pc77;state[k]=k==='minSample'?Number(el.value):el.value;saveState();renderPage(extras)});
  }

  let renderRequest=0;
  function performanceRender(){
    const request=++renderRequest;
    const app=document.querySelector('#app');
    if(!app)return;
    app.innerHTML='<div class="pc77-loading"><b>📊 Model Performance Center</b><span>Liczymy segmenty i walidację…</span></div>';
    return loadExtras().then(ex=>{if(request!==renderRequest||!app.querySelector('.pc77-loading'))return;try{renderPage(ex)}catch(err){console.error('Performance Center',err);legacyRenderStats()}}).catch(()=>legacyRenderStats());
  }

  renderStats=performanceRender;
})();
