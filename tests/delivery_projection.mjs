import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
import {buildDelivery} from '../scripts/build_delivery.mjs';
const root='frontend',read=p=>JSON.parse(fs.readFileSync(root+'/'+p));
const before=read('data/results.json'),sym=read('data/symphony2_current.json');
const index=read('data/delivery/index.json');
assert.equal(index.matches.length,before.length);
assert(fs.statSync(root+'/data/delivery/index.json').size<1000000,'First render JSON budget: 1 MB');
const ctx={console,Date,Map,Set,URL,JSON,Math,Number,String,Object,Array,localStorage:{getItem(){return null}},document:{querySelector(){return null},getElementById(){return{}},addEventListener(){}},setInterval(){},setTimeout(){},addEventListener(){}};ctx.window=ctx;vm.createContext(ctx);
for(const name of ['multi-model.js','signal-mapping-v84d4.js','autolearn-v84.js','adaptive-prod-bridge.js','market-quality.js','model-guide.js','clean-core-v80.js','serve-props-v72.js','player-analytics.js','match-time.js','playable-ui.js','early-hold-paths.js','presentation-data.js'])vm.runInContext(fs.readFileSync(root+'/'+name,'utf8'),ctx);
const D=ctx.TenisPresentation;
let checks=0;
for(let i=0;i<before.length;i++){
 const raw=before[i],row=index.matches[i],bytes=fs.readFileSync(root+'/'+row.detail_path),detail=JSON.parse(bytes);
 assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),row.detail_path.split('/').at(-1).replace('.json',''));
 assert.deepEqual(detail.match,JSON.parse(JSON.stringify(raw)),'Full raw record must survive unchanged');
 const s=D.find(sym.matches,raw),events=D.allEvents(raw,s);
 assert.equal(row.ui_summary.has_data,events.some(x=>x.value!=null));
 // Re-evaluate before kickoff and after expiration with the same canonical guards.
 const generated=Date.parse(raw.superbet_market_v91?.source_generated_at);
 for(const now of [generated,Date.parse(raw.scheduled_time),generated+91*60000]){
  if(!Number.isFinite(now))continue;
  const RealDate=Date;ctx.Date=class extends RealDate{static now(){return now}};
  const expected=events.some(e=>D.availability(raw,e,s,sym.generated_at).playable);
  const actual=(row.symphony2_playable?.signals||[]).some(e=>D.availability(row,e,row.symphony_evidence,index.symphony_generated_at).playable);
  assert.equal(actual,expected,'Projection must preserve exact PLAYABLE authority: '+row.id);checks++;
 }
}
const first=fs.readFileSync(root+'/data/delivery/index.json');buildDelivery();assert(first.equals(fs.readFileSync(root+'/data/delivery/index.json')),'Same sources produce identical index');
console.log('PASS lossless details, source hashes, index budget, reproducible index, '+checks+' PLAYABLE equivalence checks');
