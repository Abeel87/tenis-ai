import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const saved = new Map([['tenis-ai-v63-active-model','consensus']]);
const context = vm.createContext({
  console, setTimeout:()=>0, clearTimeout(){},
  bestSignalsData(){}, renderMatchDetail(){},
  localStorage:{getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)},
  document:{readyState:'loading',addEventListener(){},querySelector(){return null},querySelectorAll(){return []}},
  historyRows:[],
});
context.window=context;
const run = file=>vm.runInContext(fs.readFileSync('frontend/'+file,'utf8'),context);
run('app-meta.js'); run('multi-model.js'); run('model-guide.js');
const api=context.TENIS_AI_MODEL_API, center=context.TENIS_AI_DECISION_CENTER_V87;
assert.equal(api.active,'adaptive-prod','hidden saved Consensus must not change production ranking');
const alias=m=>({match_winner:'match_win',set1_winner:'set1_win',set2_winner:'set2_win',set3_winner:'set3_win'})[m]||m;
const matches=JSON.parse(fs.readFileSync('frontend/data/results.json','utf8'));
let compared=0;
for(const match of matches){
  const rows=center.buildRows(match);
  for(const signal of api.allSignals(match)){
    const row=rows.find(r=>r.market===alias(signal.market)&&r.pick===signal.pick&&
      (r.line==null||Number(r.line)===Number(signal.line)));
    assert.ok(row,`${match.id}: missing ${signal.key}`);
    assert.equal(center.finalScore(row,match,{}),signal.v,`${match.id}: inconsistent ${signal.key}`);
    compared++;
  }
}
assert.ok(compared>0);

// The compatibility bridge exposes final separately and never rewrites RAW.
context.TENIS_AI_AUTOLEARN_V84={scoreFor:()=>({ensemble:80,current:78})};
run('v88-upgrade.js');
context.TENIS_AI_V88.wrapAutoLearn();
const bridge=context.TENIS_AI_AUTOLEARN_V84.scoreFor({autolearn_v84:{signals:[
  {key:'match_total|18.5|over',market:'match_total',line:18.5,pick:'over',final_score:76.4}
]}},{key:'match_total|18.5|over',market:'match_total',line:18.5,pick:'over'});
assert.equal(bridge.ensemble,80); assert.equal(bridge.adaptive_prod_score,76.4);

run('v882-cleanup.js');
const perf=context.TENIS_AI_PERFORMANCE_V882;
const now=Date.now();
const signal={market:'match_total',line:18.5,pick:'over',result:'hit',tracker_version:'v8.4B',adaptive_prod_v79:{final_score:75}};
context.historyRows=Array.from({length:20},(_,i)=>({
  match_key:String(i),status:'settled',scheduled_time:new Date(now-86400000).toISOString(),
  settled_at:new Date(now-3600000).toISOString(),tour:'ATP',surface:'hard',
  autolearn_signals_v84:[signal],
}));
const match={tour:'ATP',surface:'hard',scheduled_time:new Date(now+86400000).toISOString(),autolearn_v84:{version:'v8.4B'}};
assert.equal(perf.priorFor(match,signal).n,20);
assert.equal(perf.priorFor(match,{...signal,pick:'under'}).n,0);
assert.equal(perf.priorFor(match,{...signal,line:22.5}).n,0);
assert.equal(perf.priorFor({...match,autolearn_v84:{version:'other'}},signal).n,0);
assert.equal(perf.priorFor({...match,scheduled_time:new Date(now-7200000).toISOString()},signal).n,0);

run('scenario-settlement-v83c.js');
const pair=(key,a,b)=>({items:[{match_key:key,signal_key:'a',market:'match_win',pick:'A',result:a},
  {match_key:key,signal_key:'b',market:'set1_win',pick:'A',result:b}]});
const pairs=context.TENIS_AI_SCENARIO_SETTLEMENT.summarizePairs([
  pair('1','hit','hit'),pair('1','hit','hit'),pair('2','hit','miss'),
  pair('3','hit','pending'),pair('4','hit','void')
]);
assert.equal(pairs.n,2); assert.equal(pairs.accuracy,50);
assert.equal(pairs.pending,1); assert.equal(pairs.voids,1);
console.log(`Audit cross-view smoke: PASS (${compared} candidate scores; RAW preserved; exact priors; saved pairs)`);
