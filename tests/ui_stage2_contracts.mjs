import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const c={window:{}};vm.createContext(c);
for(const p of ['presentation-data.js','match-detail-data.js'])vm.runInContext(fs.readFileSync('frontend/'+p,'utf8'),c);
const d=c.window.TenisMatchDetail;
const fixture={p1:'Łukasz Żuk',p2:'João Silva',p1_id:10,p2_id:20,scheduled_time:'2099-01-01'};
const past={p1:'SILVA, JOAO',p2:'Zuk, Lukasz',scheduled_time:'2020-01-01',result:{winner:'Łukasz Żuk',score_text:'4-6 4-6'}};
assert.equal(d.historyRows([past],fixture,'p1',true).length,1);
assert.equal(d.winnerSide(past),'p2');
assert.equal(d.historyRows([{...past,p1_id:99,p2_id:10}],fixture,'p1',true).length,0,'Conflicting IDs override similar names');
assert.equal(d.historyRows([{...past,p1:'J. Silva'}],fixture,'p1',true).length,0,'No guesses based on initials');
assert.equal(d.historyRows([{...past,scheduled_time:'2100-01-01'}],fixture,'p1',true).length,0);
assert.equal(d.historyRows([past,past],fixture,'p1',true).length,1);
assert.equal(d.historyRows([{...past,result:null}],fixture,'p1',true).length,0);
assert.equal(d.assessment({...fixture,match_win:{'Łukasz Żuk':60}}).p,null,'Never generate missing complement');
assert.equal(d.assessment({...fixture,match_win:{'Łukasz Żuk':60,'João Silva':40}}).winner,'p1');
assert.equal(d.comparison({...fixture,p1_rank:150,p2_rank:100})[0].winner,'p2');
assert.equal(d.comparison({...fixture,p1_rank:null,p2_rank:100})[0].winner,null);
for(const [values,trend] of [[[.3,.5,.6],'rosnący'],[[.6,.5,.3],'spadkowy'],[[.5,.5,.5],'stabilny'],[[.3,.6,.5],'zmienny'],[[null,.5,.6],'N/D']]){
 const m={player_intelligence_v85:{profiles:{p1:{windows:Object.fromEntries([20,10,5].map((n,i)=>[n,{metrics:{won:{adjusted:values[i]}}}]))}}}};
 assert.equal(d.form(m,'p1').trend,trend);
}
const fixtures=JSON.parse(fs.readFileSync('frontend/data/results.json')),history=JSON.parse(fs.readFileSync('frontend/data/history.json'));
let found=0;for(const m of fixtures){const rows=d.historyRows(history,m,'p1',true);found+=rows.length;assert(rows.every(r=>Date.parse(r.scheduled_time)<Date.parse(m.scheduled_time)))}
console.log('PASS Stage 2: identity, missing values, published probabilities, trends; real prior H2H rows:',found);
