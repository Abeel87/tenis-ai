/* Tenis AI v8.8 · compatibility bridge.
   v8.8.2+ owns the performance dashboard; this file keeps only the
   Adaptive PROD bridge. Old v8.8 stats rendering is intentionally disabled
   to avoid duplicate dashboards/fetches.
   v8.8.21 runtime cleanup: explicit stats events replace polling.
*/
(()=>{
'use strict';
const V88_COMPAT_BRAND = 'Tenis AI · v8.8';

const VERSION='v8.8-compat';
const RUNTIME_FIX='v8.8.21';
const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
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
  return num(parts?.[1]);
}

function adaptiveSignal(match,signal){
  const market=marketAlias(signal?.market);
  const pick=norm(signal?.pick);
  const line=signalLine(signal);
  const key=String(signal?.key||signal?.signal_key||'');
  const rows=[
    ...(Array.isArray(match?.adaptive_learning_v79?.signals)?match.adaptive_learning_v79.signals:[]),
    ...(Array.isArray(match?.autolearn_v84?.signals)?match.autolearn_v84.signals:[])
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
  if(!api||api.__v88Wrapped||typeof api.scoreFor!=='function')return false;
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
      ensemble:rawEnsemble,
      final_score:final,
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

/* Compatibility symbols retained for guards/tests. The real dashboard lives in
   v882-cleanup.js. These functions are intentionally not wired to renderStats. */
function confidenceRows(){return[]}
function renderMarkets(){return''}
function segmentRows(){return{best:[],weak:[]}}
function modelRows(){return[]}
const LEGACY_STATS_SOURCES=[
  'repeated_errors',
  'data/adaptive_learning_v79.json',
  'data/model_telemetry_v84c.json'
];

function injectStats(){
  document.querySelector('#pc88-dashboard')?.remove();
  return false;
}

function wrapStats(){
  return false;
}

function applyV88Brand(){
  window.TENIS_AI_APPLY_META?.();
}

function boot(){
  applyV88Brand();
  wrapAutoLearn();
  injectStats();
}

document.addEventListener('tenis-ai:stats-ready',injectStats);
document.addEventListener('tenis-ai:stats-dashboard-ready',injectStats);
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();

window.TENIS_AI_V88={
  version:VERSION,
  runtimeFix:RUNTIME_FIX,
  wrapAutoLearn,
  injectStats,
  wrapStats,
  LEGACY_STATS_SOURCES
};
})();