/* Tenis AI v8.4B — AutoLearn bridge + model comparison UI
   v8.4C adds read-only telemetry for specialist/ML/generator performance.
*/
(() => {
  'use strict';
  const VERSION='v8.4B';
  const REPORT='data/autolearn_v84.json';
  const TELEMETRY='data/model_telemetry_v84c.json';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const brier=x=>num(x)==null?'—':Number(x).toFixed(3);
  const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');
  let reportPromise=null,telemetryPromise=null;

  function lineOf(s){
    const direct=num(s?.line??s?.selected_line??s?.suggested_line);if(direct!=null)return direct;
    const p=String(s?.key||s?.signal_key||'').split('|');
    return p.length>1?num(p[1]):null;
  }
  function marketAlias(m){
    return ({match_win:'match_winner',set1_win:'set1_winner',set2_win:'set2_winner',set3_win:'set3_winner'})[String(m||'').toLowerCase()]||String(m||'').toLowerCase();
  }
  function scoreFor(match,signal){
    const a=match?.autolearn_v84;if(!a)return null;
    const key=String(signal?.key||signal?.signal_key||'');
    const direct=a?.by_key?.[key];
    if(direct)return {...direct,status:a.status,weights:a.weights,weight_policy:a.weight_policy||null};
    const market=marketAlias(signal?.market),pick=norm(signal?.pick),line=lineOf(signal);
    const row=(a?.signals||[]).find(x=>{
      if(marketAlias(x?.market)!==market||norm(x?.pick)!==pick)return false;
      const xl=lineOf(x);
      return line==null?xl==null:xl!=null&&Math.abs(xl-line)<0.001;
    });
    return row?{...row,status:a.status,weights:a.weights,weight_policy:a.weight_policy||null}:null;
  }

  function modelVoteText(row){
    if(!row)return 'AI N/D';
    const parts=[];
    if(num(row.catboost)!=null)parts.push(`C${Math.round(Number(row.catboost))}`);
    if(num(row.tabpfn)!=null)parts.push(`T${Math.round(Number(row.tabpfn))}`);
    if(num(row.current)!=null)parts.push(`E${Math.round(Number(row.current))}`);
    return parts.length?`Ensemble ${parts.join('/')}`:'Ensemble';
  }

  async function loadReport(force=false){
    if(force)reportPromise=null;
    if(!reportPromise)reportPromise=fetch(`${REPORT}?v=84b1&ts=${Date.now()}`,{cache:'no-store'})
      .then(r=>r.ok?r.json():{}).catch(()=>({}));
    return reportPromise;
  }
  async function loadTelemetry(force=false){
    if(force)telemetryPromise=null;
    if(!telemetryPromise)telemetryPromise=fetch(`${TELEMETRY}?v=84c1&ts=${Date.now()}`,{cache:'no-store'})
      .then(r=>r.ok?r.json():{}).catch(()=>({}));
    return telemetryPromise;
  }
window.TENIS_AI_AUTOLEARN_V84={version:VERSION,scoreFor,loadReport,loadTelemetry};
})();
