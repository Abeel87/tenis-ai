import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const stamp='2026-09-10T19:45:00Z';let now=Date.parse(stamp);
class Clock extends Date{constructor(...a){super(...(a.length?a:[now]))}static now(){return now}}
const ctx={console,Date:Clock,URL,Map,Set};ctx.window=ctx;vm.createContext(ctx);
for(const f of ['playable-ui.js','presentation-data.js'])vm.runInContext(fs.readFileSync('frontend/'+f,'utf8'),ctx);
const D=ctx.TenisPresentation,P=ctx.TENIS_AI_PLAYABLE_UI_V917;
const signal={market:'set1_total',pick:'over',line:8.5,operator_available:true,operator_line_verified:true,fixture_line_verified:true};
const m={id:1,p1:'Alpha One',p2:'Beta Two',scheduled_time:'2026-09-10T23:00:00Z',superbet_market_v91:{operator:'superbet.pl',operator_verified:true,status:'VERIFIED',source_generated_at:stamp,canonical_selections:[signal]}};
const feed={operator:'superbet.pl',status:'OK',prices_used:false,generated_at:stamp,matches:[{match_id:1,p1:'One, Alpha',p2:'Two, Beta',operator_start_time:m.scheduled_time,event_url:'https://superbet.pl/kursy/tenis/test-123',direct_match_verified:true,canonical_selections:[{...signal,set_no:1,operator:'superbet.pl',operator_price:1.82,operator_price_verified:true,operator_selection_status:'active',prices_used:false}]}]};
const before=JSON.stringify({m,feed});
assert.equal(D.operatorPrice(m,signal,feed).odds,1.82);
assert.equal(D.operatorPrice(m,{...signal,line:9.5},feed),null);
for(const mutate of [f=>f.generated_at='2026-09-09T00:00:00Z',f=>f.operator='superbet.ro',f=>f.matches[0].match_id=2,f=>f.matches[0].p1='Other',f=>f.matches[0].operator_start_time='2026-09-11T23:00:00Z',f=>f.matches[0].canonical_selections[0].operator_price_verified=false,f=>f.matches[0].canonical_selections[0].operator_selection_status='suspended',f=>f.matches[0].canonical_selections[0].set_no=2,f=>f.matches.push(f.matches[0]),f=>f.matches[0].canonical_selections.push({...f.matches[0].canonical_selections[0],operator_price:2})]){const f=structuredClone(feed);mutate(f);assert.equal(D.operatorPrice(m,signal,f),null)}
assert.equal(D.availability(m,signal,null,null).playable,false,'Price metadata cannot grant PLAYABLE');
assert.equal(D.operatorPrice({...m,superbet_market_v91:{...m.superbet_market_v91,canonical_selections:[]}},signal,feed),null);
assert.equal(JSON.stringify({m,feed}),before);
const rows=[{source:'Symfonia 2.0',market:'p2_wins_a_set',pick:'yes',value:57.8},{source:'Symfonia 2.0',market:'p2_wins_a_set',pick:'no',value:62.9},{source:'Symfonia 2.0',...signal,value:68},{source:'Symfonia 2.0',...signal,line:9.5,value:55}];
const original=JSON.stringify(rows),groups=D.groupEvents(rows);assert.equal(groups.length,3);assert.equal(groups[0][0].s.pick,'no');assert.equal(groups[0][0].index,1);assert.equal(JSON.stringify(rows),original);
assert.equal(D.marketChoice({market:'state4',pick:'2:2'}),'game_state:4:draw');
const tournaments=D.tournamentGroups([{id:1,tour:'atp',tournament:'A',surface:'hard'},{id:2,tour:'wta',tournament:'A',surface:'hard'},{id:3,tour:'atp',tournament:'A',surface:'hard'}]);assert.equal(tournaments.length,2);assert.equal(tournaments[0].matches.length,2);
if(fs.existsSync('frontend/data/superbet_direct_current.json')){
 const raw=JSON.parse(fs.readFileSync('frontend/data/results.json')),direct=JSON.parse(fs.readFileSync('frontend/data/superbet_direct_current.json')),sym=JSON.parse(fs.readFileSync('frontend/data/symphony2_current.json'));
 now=Date.parse(sym.generated_at)+1000;let joined=0;for(const sm of sym.matches){const rm=D.find(raw,sm);if(!rm)continue;for(const s of sm.scored_selections||[]){const price=D.operatorPrice(rm,s,direct);if(price){joined++;assert(P.isPlayable(rm,s));assert(price.odds>1)}}}
 console.log('Verified real Symphony price joins:',joined);
}
console.log('PASS: exact price, expiry, identity, line/set matching, no PLAYABLE promotion, grouped original probabilities, tournament preservation');
