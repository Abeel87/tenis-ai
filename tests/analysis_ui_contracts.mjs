import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {execFileSync} from 'node:child_process';
import {buildDelivery} from '../scripts/build_delivery.mjs';

const now=Date.parse('2026-11-11T12:00:00Z'),RealDate=Date;
const ctx={console,Date:class extends RealDate{static now(){return now}},Map,Set,URL,JSON,Math,Number,String,Object,Array};
ctx.window=ctx;vm.createContext(ctx);
for(const name of ['playable-ui.js','presentation-data.js'])vm.runInContext(fs.readFileSync('frontend/'+name,'utf8'),ctx);
const D=ctx.TenisPresentation;
assert.equal(D.pct(99.98),'>99.9%','Rounded model confidence must not imply certainty');
assert.equal(D.pct(0.02),'<0.1%','A positive probability must not display as zero');
assert.equal(D.pct(100),'100%');assert.equal(D.pct(0),'0%');
assert.equal(D.pct(47.58),'47.6%');
assert.equal(D.pct(null),'Brak danych');
const match={id:1,p1:'Alpha',p2:'Beta',scheduled_time:'2026-11-11T15:00:00Z',superbet_market_v91:{operator:'superbet.pl',operator_verified:true,status:'VERIFIED',canonical_selections:[],source_generated_at:'2026-11-11T12:00:00Z',operator_start_time:'2026-11-11T15:00:00Z'}};
const quote={combined_odds:2.75,expected_value_net:.21,odds_timestamp:'2026-11-11T12:00:00Z',price_status:'EXACT_CURRENT_QUOTE'};
const comp={component_comparison:{mode:'SHADOW_COMPARISON',production_influence:false,ranking_influence:false,
 reservation_enabled:false,automatic_real_betting:false,synthetic_prices:false,odds_max_age_minutes:108,
 full:quote,without_leg:[{...quote,combined_odds:2.,net_ev_change:-.154}]}};
const original=JSON.stringify(comp);
assert.equal(D.builderComparison(match,comp,now).full.combined_odds,2.75);
assert.equal(D.builderComparison(match,comp,now+109*60000).full.expected_value_net,null);
assert.equal(D.builderComparison(match,comp,now-1).full.combined_odds,null);
assert.equal(D.builderComparison({...match,scheduled_time:'2026-11-11T11:00:00Z'},comp,now).full.combined_odds,null);
assert.equal(D.builderComparison({...match,event_status:'Finished'},comp,now).full.combined_odds,null);
assert.equal(D.builderComparison(match,{component_comparison:{...comp.component_comparison,production_influence:true}},now),null);
assert.equal(JSON.stringify(comp),original,'Display must never rewrite source comparisons');
const partial=structuredClone(comp);partial.component_comparison.full.odds_timestamp='2026-11-10T12:00:00Z';
assert.equal(D.builderComparison(match,partial,now).without_leg[0].combined_odds,2.);
assert.equal(D.builderComparison(match,partial,now).without_leg[0].net_ev_change,null);
const predictions=['miss','hit','void','unverifiable'].map(result=>({result,signal:{market:'set1_total',pick:'over',line:8.5},value:70,unit:'%',capturedAt:'2026-11-11T10:00:00Z'}));
const review=D.postMatchReview({...match,final:{sets:[[6,2],[6,4]]},predictions});
assert.equal(review.missed.length,1);assert.equal(review.unresolved.length,1);assert.equal(review.void.length,1);
assert.equal(review.score,'6:2 · 6:4');assert.equal(review.causalConclusion,null);
assert.equal(review.missed[0].value,70,'Frozen probability is not recomputed after a miss');

// Exercise the actual renderers on missing and populated evidence, including HTML escaping.
const app=fs.readFileSync('frontend/app.js','utf8');
Object.assign(ctx,{D,E:D.esc,details:new Map(),state:{},sym:()=>({}),top:()=>null,playable:()=>false,
 empty:s=>'<p>'+D.esc(s)+'</p>',overviewRows:rows=>rows.map(([k,v])=>D.esc(k)+': '+D.esc(v??'N/D')).join(' | '),
 date:s=>s||'N/D',badge:D.esc,surface:s=>s,READINESS_DIMENSION_LABELS:{}});
vm.runInContext(app.slice(app.indexOf('function analysisEvidence('),app.indexOf('/* Readable reports')),ctx);
const unsafe={...match,p1:'<img src=x onerror=alert(1)>'};
assert(ctx.qualityPanel(unsafe).includes('&lt;img'));
assert(ctx.playerStatePanel(match,'p1').includes('Brak zgodnego raportu'));
assert(ctx.analysisTimeline(match).includes('Brak zapisanych zmian'));
assert(ctx.whyThisPick(match).includes('Czekamy na rekomendację'));
assert(ctx.historySupplyPanel().includes('niedostępny'));
const html=ctx.learningProgressPanel({model_id:'v2',prospective:{by_model:{v2:{settled_matches:1,
 production_comparison:{settled_matches:0},segments:{surface:{UNKNOWN:{production_comparison:{settled_matches:0}}}}}}}});
assert(html.includes('Bieżąca wersja'));assert(html.includes('Nie zapisana'));assert(html.includes('N/D'));
assert(html.includes('0 wspólnych meczów'),'An explicit observed zero must remain zero');
const missingComparison=ctx.learningProgressPanel({model_id:'v2',prospective:{by_model:{v2:{segments:{surface:{UNKNOWN:{}}}}}}});
assert(missingComparison.includes('N/D wspólnych meczów'),'Absent comparison evidence is not zero');
assert(!missingComparison.includes('<td>0</td>'),'Absent segment evidence is not zero');

// Synthetic fixtures live only in a temporary directory. Prove unchanged raw data,
// identity-bound journals, deterministic index and full-app routing without remote data.
const root=fs.mkdtempSync(path.join(os.tmpdir(),'tenis-analysis-test-'));
try{
 fs.mkdirSync(path.join(root,'data'));
 for(const name of fs.readdirSync('frontend').filter(x=>x.endsWith('.js')))fs.copyFileSync('frontend/'+name,path.join(root,name));
 const m={...match,scheduled_time:'2099-11-11T15:00:00Z',p1_stats:{matches:0},p2_stats:{},surface:'hard',tournament:'Test fixture'};
 const docs={'results.json':[m],'symphony2_current.json':{matches:[],generated_at:'2099-11-11T12:00:00Z'},
  'superbet_direct_current.json':{matches:[]},'player_dna_current_shadow.json':{matches:[]},'meta.json':{updated_at:'2099-11-11T12:00:00Z'},
  'symphony2_stats.json':{},'history_coverage_audit_v949.json':{},'history.json':[],
  'symphony2_history.json':{entries:[],analysis_observations:{1:{identity:{p1:m.p1,p2:m.p2,scheduled_time:m.scheduled_time},observations:[]}}}};
 for(const [name,value] of Object.entries(docs))fs.writeFileSync(path.join(root,'data',name),JSON.stringify(value));
 buildDelivery(root);
 const indexPath=path.join(root,'data/delivery/index.json'),bytes=fs.readFileSync(indexPath),index=JSON.parse(bytes);
 const detail=JSON.parse(fs.readFileSync(path.join(root,index.matches[0].detail_path)));
 assert.deepEqual(detail.match,m);assert(detail.analysis_journal);assert.equal(detail.analysis_evidence.shadow_available,false);
 assert.equal(detail.analysis_evidence.players.p1.matches,0);assert.equal(detail.analysis_evidence.players.p2.matches,null);
 buildDelivery(root);assert(bytes.equals(fs.readFileSync(indexPath)));
 const output=execFileSync(process.execPath,['tests/ui_runtime_smoke.mjs'],{encoding:'utf8',env:{...process.env,TENIS_UI_FIXTURES:path.join(root,'data')}});
 assert(output.includes('PASS: route runtime'));
 docs['symphony2_history.json'].analysis_observations[1].identity.p2='Other';
 fs.writeFileSync(path.join(root,'data/symphony2_history.json'),JSON.stringify(docs['symphony2_history.json']));
 buildDelivery(root);
 const changed=JSON.parse(fs.readFileSync(indexPath));
 assert.equal(JSON.parse(fs.readFileSync(path.join(root,changed.matches[0].detail_path))).analysis_journal,null);
}finally{fs.rmSync(root,{recursive:true,force:true})}
console.log('PASS analysis UI: quote freshness, no post-start EV, immutable review, missingness, escaping, identity, delivery, all routes and roles');
