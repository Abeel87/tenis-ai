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
assert.ok(Array.isArray(matches)&&matches.length>0,'results.json must contain current fixtures');

const matchIds=new Set();
let compared=0, matchesWithSignals=0;
for(const match of matches){
  const matchId=String(match.id??match.match_id??[match.p1,match.p2,match.scheduled_time].join('|'));
  assert.ok(!matchIds.has(matchId),`duplicate match identity: ${matchId}`);
  matchIds.add(matchId);

  const rows=center.buildRows(match);
  const signals=api.allSignals(match);
  if(signals.length)matchesWithSignals++;
  const signalKeys=new Set();

  for(const signal of signals){
    assert.ok(String(signal.key||signal.signal_key||'').trim(),`${matchId}: signal without key`);
    assert.ok(String(signal.market||'').trim(),`${matchId}: signal without market`);
    assert.ok(String(signal.pick??'').trim(),`${matchId}: signal without pick`);
    assert.ok(Number.isFinite(Number(signal.v)),`${matchId}: non-finite FINAL for ${signal.key}`);
    assert.ok(Number(signal.v)>=0&&Number(signal.v)<=100,`${matchId}: FINAL outside 0..100 for ${signal.key}`);
    if(signal.line!=null&&signal.line!=='')assert.ok(Number.isFinite(Number(signal.line)),`${matchId}: invalid line for ${signal.key}`);

    const signalKey=String(signal.key||signal.signal_key);
    assert.ok(!signalKeys.has(signalKey),`${matchId}: duplicate production signal ${signalKey}`);
    signalKeys.add(signalKey);

    const row=rows.find(r=>r.market===alias(signal.market)&&r.pick===signal.pick&&
      (r.line==null||Number(r.line)===Number(signal.line)));
    assert.ok(row,`${match.id}: missing ${signal.key}`);
    assert.equal(center.finalScore(row,match,{}),signal.v,`${match.id}: inconsistent ${signal.key}`);
    compared++;
  }
}
assert.ok(compared>0);
assert.ok(matchesWithSignals>0);
console.log(`Current production signal hygiene: PASS (${matches.length} fixtures; ${matchesWithSignals} with signals; ${compared} unique FINAL candidates)`);

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

// The real openMatch function must assemble all panels while the overlay is hidden.
const uiSource=fs.readFileSync('frontend/ui-v751.js','utf8');
const openSource=uiSource.slice(uiSource.indexOf('  function openMatch(k){'),uiSource.indexOf('  function closeMatch(){'));
const order=[];
const overlay={hidden:false,dataset:{},scrollTop:700,querySelector:s=>s==='.dc87'?{}:null};
const opening=vm.createContext({
  findMatch:()=>({id:'next'}),ensureOverlay:()=>overlay,detailHtml:()=>'<section/>',
  bindLazySections78e23:()=>{assert.equal(overlay.hidden,true);order.push('lazy')},
  document:{body:{classList:{add(){order.push('visible')}}}},
  requestAnimationFrame:()=>assert.fail('opening must not schedule late panels'),
  window:{
    TENIS_AI_DECISION_CENTER_V87:{tidy:()=>{assert.equal(overlay.hidden,true);order.push('center')}},
    TENIS_AI_PLAYER_UI_V851:{injectDetail:()=>{assert.equal(overlay.hidden,true);order.push('player')}},
    TENIS_AI_ADAPTIVE_V79:{injectProjectDetail:()=>assert.fail('legacy Adaptive must not compete with the center')}
  }
});
vm.runInContext(openSource+'\nopenMatch("next");',opening);
assert.deepEqual(order,['lazy','center','player','visible']);
assert.equal(overlay.hidden,false);assert.equal(overlay.scrollTop,0);

// Player details belong after the center from the outset, never above its scroll anchor.
const piSource=fs.readFileSync('frontend/player-intelligence-v851b-ui.js','utf8');
const piInject=piSource.slice(piSource.indexOf('  function injectDetail(m){'),piSource.indexOf('\n  function telemetry()'));
const anchors=[];
const detailHost={querySelector:s=>s==='.dc87'?{insertAdjacentHTML:(where)=>anchors.push(where)}:null};
vm.runInNewContext(piInject+'\ninjectDetail({id:"next"});',{
  document:{querySelector:()=>detailHost},details:()=>'<section data-pi851-detail></section>'
});
assert.deepEqual(anchors,['afterend']);

// Any old caller of the Adaptive injector must remain harmless after the center mounts.
const adaptiveSource=fs.readFileSync('frontend/adaptive-learning-v79.js','utf8');
const adaptiveInject=adaptiveSource.slice(adaptiveSource.indexOf('  function injectProjectDetail(){'),adaptiveSource.indexOf('\n  function healthHtml('));
vm.runInNewContext(adaptiveInject+'\ninjectProjectDetail();',{
  document:{querySelector:()=>detailHost},
  currentProjectMatch:()=>assert.fail('legacy injector must stop at the existing center')
});

// Charts use a separate root, outside hidden legacy/PRO disclosures; null is not 0%.
run('model-trends-v84e2.js');
const monitor=context.TENIS_AI_MODEL_TRENDS_V84E2;
const telemetry=JSON.parse(fs.readFileSync('frontend/data/model_telemetry_v84c.json','utf8'));
const charts=monitor.render(telemetry,'pc882-trend-monitor');
assert.ok(charts.includes('id="pc882-trend-monitor"'));
assert.ok(charts.includes('FINAL Adaptive PROD'));
assert.ok(charts.includes('<polyline'));
assert.ok(!charts.includes('id="mt84e2"'));
const missing=monitor.render({trends_v84e2:{version:'v8.4E2',models:{adaptive_prod:{series:[{accuracy:null},{accuracy:null}]}}}},'test');
assert.ok(!missing.includes('<polyline'),'missing series cannot invent a zero-accuracy trend');
console.log('Stable match opening and directly accessible model charts: PASS');

// Exercise the async experiment renderer: null metrics, unchanged DOM and navigation.
const coherenceSource=fs.readFileSync('frontend/app-coherence-v892.js','utf8');
let currentHost, currentSection=null, markupWrites=0, readyEvents=0;
const makeHost=()=>({
  querySelector(selector){return selector==='#coh892-shadow'?currentSection:null},
  append(section){currentSection=section;section.parentNode=this}
});
currentHost=makeHost();
let pendingTelemetry;
const experimentContext=vm.createContext({
  setTimeout:()=>0,clearTimeout(){},CustomEvent:class{constructor(type){this.type=type}},
  document:{
    documentElement:{dataset:{}},querySelector:s=>s==='#pc77'?currentHost:null,
    querySelectorAll:()=>[],getElementById:()=>({}),addEventListener(){},
    dispatchEvent:e=>{assert.equal(e.type,'tenis-ai:shadow-experiments-ready');readyEvents++},
    createElement:()=>({set innerHTML(html){this.html=html;markupWrites++}})
  }
});
experimentContext.window=experimentContext;
experimentContext.TENIS_AI_AUTOLEARN_V84={loadTelemetry:()=>new Promise(resolve=>{pendingTelemetry=resolve})};
vm.runInContext(coherenceSource,experimentContext);
const renderExperiments=experimentContext.TENIS_AI_COHERENCE_V892.renderShadowExperiments;
const emptyMetrics={player_model_shadow_v89:{production_influence:false,
  holdout:{player_catboost_shadow:{accuracy:null,brier:null,n:0,selected_n:0}}}};
let rendering=renderExperiments();pendingTelemetry(emptyMetrics);await rendering;
assert.ok(currentSection.html.includes('<b>—</b>'));
assert.ok(currentSection.html.includes('Brier —'));
assert.ok(!currentSection.html.includes('<b>0%</b>'));
const firstSection=currentSection;
rendering=renderExperiments();pendingTelemetry(emptyMetrics);await rendering;
assert.equal(currentSection,firstSection);assert.equal(markupWrites,1);
assert.equal(readyEvents,2);
rendering=renderExperiments();currentHost=makeHost();currentSection=null;
pendingTelemetry(emptyMetrics);assert.equal(await rendering,false);
assert.equal(markupWrites,1,'late telemetry must not mount into a replaced stats view');

// Repeated chart decoration keeps the existing SVG and describes worsening Brier honestly.
const chartSource=fs.readFileSync('frontend/shadow-experiment-charts-v895.js','utf8');
const chartContext=vm.createContext({document:{readyState:'loading',addEventListener(){}},
  setTimeout:()=>0,console});
chartContext.window=chartContext;
vm.runInContext(chartSource.replace('version:VERSION,decorate,refresh,productionInfluence:false',
  'version:VERSION,decorate,refresh,productionInfluence:false,chartHtml,setReport:x=>{report=x}'),chartContext);
const chartApi=chartContext.TENIS_AI_SHADOW_CHARTS_V895;
chartApi.setReport({models:{test:{points_count:1,points:[{accuracy:null,base_accuracy:null,brier:.3,base_brier:.2}]}}});
assert.ok(chartApi.chartHtml('test').includes('0.10000 pogorszenia'));
assert.ok(!chartApi.chartHtml('test').includes('0.10000 poprawy'));
console.log('SHADOW null metrics, stable async rendering and Brier labels: PASS');

// The production generator and save guard share a pre-render check, including 1/3/4 events.
const qualityContext=vm.createContext({
  fetch:async()=>({ok:true,json:async()=>({market_thresholds_shadow:{match_total:{baseline_65_val:{accuracy:60}}}})}),
  document:{createElement:()=>({}),head:{appendChild(){}},addEventListener(){}},
  console,setTimeout:()=>0
});
qualityContext.window=qualityContext;
vm.runInContext(fs.readFileSync('frontend/generator-quality-v888.js','utf8'),qualityContext);
const quality=qualityContext.TENIS_AI_GENERATOR_QUALITY_V888;
await quality.ready;
assert.equal(quality.checkGroup([{market:'set1_total',composer_score:80}],'balanced',1).valid,true);
assert.equal(quality.checkGroup([{composer_score:80},{composer_score:80},{composer_score:60}],'balanced',3).valid,false);
assert.equal(quality.checkGroup([{market:'match_total',composer_score:77},{composer_score:80}],'balanced',2).valid,false);

const scenarioSource=fs.readFileSync('frontend/scenario-studio-v82a.js','utf8');
const qualityRepair=scenarioSource.slice(scenarioSource.indexOf('  function generatorQuality('),scenarioSource.indexOf('  function draftMatches('));
const generateSource=scenarioSource.slice(scenarioSource.indexOf('  async function generateFromUi('),scenarioSource.indexOf('  function addSignalSilent('));
let generatedPool=[],messages=[],draftRenders=0,clears=0;
const generationContext=vm.createContext({
  window:{TENIS_AI_GENERATOR_QUALITY_V888:quality},
  panel:{hidden:false},currentTab:'generator',draft:{items:[]},
  $:selector=>({dataset:selector.includes('matches')?{scN:'2'}:selector.includes('signals')?{scN:'2'}:{scProfile:'balanced'}}),
  selectorPolicy:()=>({signalFloor:54,softPairFloor:60}),
  generatorProfilePolicy:()=>({floor:72,strong:76,minAverage:72}),
  todaysMatches:()=>[{id:'test'}],scenarioSignals:()=>generatedPool,
  composerSignalScore:(_m,s)=>s.cs,categoryOf:s=>s.market,generatorFamily:s=>s.market,
  generatorTotalMarketable:()=>true,isTotalSignal:()=>false,totalLine:()=>null,
  marketAnchorLine:()=>null,selectorPreferredTotalRows:()=>[],
  selectorBestPair:(_m,rows)=>({signals:rows,type:'test',score:90,reason:'test',floor_used:60}),
  selectorMatchScore:()=>90,clamp:x=>x,
  toast:msg=>messages.push(msg),persistDraft(){},
  clearDraft:()=>{clears++;generationContext.draft={items:[]}},
  addSignalSilent:(_m,s)=>generationContext.draft.items.push(s),
  draftMatches:()=>generationContext.draft.items.length?[{id:'test'}]:[],
  render:()=>{draftRenders++}
});
vm.runInContext(qualityRepair+generateSource,generationContext);
generatedPool=[{key:'winner',market:'match_win',cs:60},{key:'set',market:'set1_win',cs:62}];
await vm.runInContext('generateFromUi()',generationContext);
assert.ok(messages[0].includes('nie znalazło'));
assert.equal(clears,0,'failed generation must preserve an existing draft');
assert.equal(draftRenders,0,'never publish a weak draft then delete it after success');
generatedPool=[{key:'winner',market:'match_win',cs:80},{key:'set',market:'set1_win',cs:82}];
await vm.runInContext('generateFromUi()',generationContext);
assert.equal(generationContext.draft.items.length,2);
assert.equal(generationContext.draft.signals_per_match,2);
assert.equal(draftRenders,1);
assert.ok(messages.at(-1).includes('1/2'));
console.log('Generator pre-publication Quality Lock and requested event counts: PASS');
