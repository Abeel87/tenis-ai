/* Tenis AI v7.7 — Model Performance Center */
(() => {



  const KEY='tenis-ai-v77-performance-state';
  const CURRENT_MODEL_VERSION='v7.8D-calibration-guard';
  const state=Object.assign({period:'all',tour:'all',surface:'all',minSample:10},readState());
  let extras=null, extrasPromise=null;

  const esc77=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct77=x=>x==null||!Number.isFinite(Number(x))?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const num77=x=>Number.isFinite(Number(x))?Number(x):0;
  const fmtInt=x=>Math.round(num77(x)).toLocaleString('pl-PL');
  const STANDARD_SET_SCORES=new Set(['0:6','1:6','2:6','3:6','4:6','5:7','6:7']);

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

  // Mirror backend/history_sampling.py::unique_signals for read-only reporting.
  // Archived snapshots stay untouched; only the Performance Center view is canonicalized.
  function reportSignals(m){
    const final=m?.result||{};
    const sets=Array.isArray(final?.sets)?final.sets:[];
    const first=Array.isArray(sets[0])?sets[0]:null;
    const firstPair=first&&first.length>=2
      ? [Number(first[0]),Number(first[1])].sort((a,b)=>a-b)
      : null;
    const standard=!!(
      final?.status==='completed' &&
      firstPair && firstPair.every(Number.isFinite) &&
      STANDARD_SET_SCORES.has(`${firstPair[0]}:${firstPair[1]}`)
    );
    const rows=[...(m?.signals||[])].sort((a,b)=>String(a?.line??'').localeCompare(String(b?.line??'')));
    const out=[],seen=new Set();

    for(const raw of rows){
      if(!raw?.market||raw?.pick==null){out.push(raw);continue}
      let line=raw?.line;
      if(line!=null&&line!==''&&Number.isFinite(Number(line)))line=Number(line);
      const originalLine=line;
      if(standard&&raw.market==='set1_total'&&(line===10.5||line===11.5))line=10.5;
      const key=JSON.stringify([
        raw.market,raw.pick,line,raw?.checkpoint??null,
        raw?.source_model??null,raw?.tracker_version??null
      ]);
      if(seen.has(key))continue;
      seen.add(key);
      if(originalLine!==line){
        out.push({...raw,line,label:String(raw?.label||'').replace('11.5','10.5')});
      }else out.push(raw);
    }
    return out;
  }

  function flatten(rows=history()){
    const out=[];
    for(const m of rows){
      const d=new Date(m.scheduled_time||m.captured_at||m.first_captured_at||0);
      if(!Number.isFinite(d.getTime()))continue;
      for(const s of reportSignals(m)){
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
window.TENIS_AI_PERFORMANCE={reportSignals,flatten,stats,group,wilson,filtered,periodBounds};
})();
