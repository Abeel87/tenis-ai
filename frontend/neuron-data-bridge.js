/* New Neuron publication adapter. Read-only: maps the retired admin report slots to rebuilt SHADOW_RESEARCH artifacts. */
(()=>{
'use strict';
const D=window.TenisPresentation;
if(!D||typeof D.json!=='function')return;
const json=D.json.bind(D);
const clearJson=typeof D.clearCache==='function'?D.clearCache.bind(D):null;
let cached=null;
async function bundle(force=false){
  if(cached&&!force)return cached;
  const [current,metrics]=await Promise.all([
    json('data/neuron_current.json',force),
    json('data/neuron_metrics.json',force)
  ]);
  cached={current:current&&typeof current==='object'?current:{},metrics:metrics&&typeof metrics==='object'?metrics:{}};
  return cached;
}
async function summary(force=false){
  const {current,metrics}=await bundle(force);
  const matches=Array.isArray(current.matches)?current.matches:[];
  const scored=matches.filter(x=>x&&x.status==='SHADOW_SCORE');
  return {
    mode:current.mode||metrics.mode||'SHADOW_RESEARCH',
    status:scored.length?'SHADOW_ACTIVE':'SHADOW_NO_SCORES',
    status_source:'UI_DERIVED_FROM_PUBLISHED_ROWS',
    generated_at:current.generated_at||metrics.generated_at||null,
    matches_count:matches.length,
    neural_rows_count:scored.length,
    state_only_rows_count:0,
    rows_count:scored.length,
    production_influence:false,
    playable_influence:false,
    symphony_influence:false,
    ineed_influence:false,
    quality_gate:metrics.quality_gate||null,
    splits:metrics.splits||null,
    test:metrics.test||null,
    elo_baseline_test:metrics.elo_baseline_test||null,
    source_artifacts:['neuron_current.json','neuron_metrics.json'],
    matches
  };
}
D.json=async(path,force=false)=>{
  if(path==='data/neuro_shadow_current_v936.json')return summary(force);
  if(path==='data/neuro_shadow_stats_v935.json')return (await bundle(force)).metrics;
  if(path==='data/neuro_shadow_neural_v936.json')return json('data/neuron_model.json',force);
  if(path==='data/neuro_shadow_history_v935.json')return (await bundle(force)).current;
  return json(path,force);
};
if(clearJson)D.clearCache=()=>{cached=null;return clearJson()};
document.addEventListener('click',e=>{
  const a=e.target?.closest?.('a[href="data/neuro_shadow_history_v935.json"]');
  if(!a)return;
  e.preventDefault();
  window.open?.('data/neuron_current.json','_blank','noopener');
},true);
window.TENIS_AI_NEURON_DATA={bundle,summary,clear(){cached=null}};
})();
