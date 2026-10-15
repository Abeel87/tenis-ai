from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "ineed.js"


def test_latest_decision_summary_uses_complete_immutable_batch():
    source = JS.read_text(encoding="utf-8")
    assert ".from('ineed_decision_snapshots')" in source
    assert ".eq('experiment_id',exp.id)" in source
    assert ".lte('evaluated_at',new Date(last).toISOString())" in source
    assert "result.count===decisions.length" in source
    assert "const evaluation=currentEvaluation(d.decisions,d.health,d.decisionsComplete)" in source
    assert "latestRejected.slice(0,5).map(compactDecision)" in source


def test_latest_decision_counts_fail_closed_on_partial_or_mismatched_batch():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('frontend/ineed.js','utf8');
const start=source.indexOf('function currentEvaluation(');
const end=source.indexOf('function milestones(',start);
assert(start>=0 && end>start);
const evaluate=vm.runInNewContext(source.slice(start,end)+';currentEvaluation');
const rows=[
  {status:'REJECTED',reason_code:'LOW_EV'},
  {status:'REJECTED',reason_code:'CORRELATION_LIMIT'},
  {status:'QUALIFIED',reason_code:null}
];
const health={detail:{evaluations:3}};
const full=evaluate(rows,health,true);
assert.equal(full.complete,true);
assert.equal(full.evaluated,3);
assert.equal(full.rows.length,3);
assert.deepEqual(Object.fromEntries(full.reasons),{LOW_EV:1,CORRELATION_LIMIT:1});
for(const partial of [evaluate(rows.slice(0,2),health,true),evaluate(rows,health,false),evaluate(null,health,false)]){
  assert.equal(partial.complete,false);
  assert.equal(partial.rows.length,0);
  assert.equal(partial.evaluated,3);
}
for(const missing of [null,undefined,'',false,-1]){
  const result=evaluate([],{detail:{evaluations:missing}},true);
  assert.equal(result.complete,false,'Missing counter must not be presented as zero evaluated');
  assert.equal(result.evaluated,null);
}
assert.equal(evaluate([],{detail:{evaluations:0}},true).complete,true);
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)


def test_zero_candidate_message_uses_published_intake_evidence():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('frontend/ineed.js','utf8');
const start=source.indexOf('function evaluationIntakeMessage(');
const end=source.indexOf('function milestones(',start);
assert(start>=0 && end>start);
const message=vm.runInNewContext(source.slice(start,end)+';evaluationIntakeMessage');
assert.equal(message(null),null);
assert.equal(message({detail:{evaluations:0}}),null,'No invented reason');
const detail={evaluations:0,results_rows:221,market_scope:{contract:'INEED_SCOPE_MATCH_WINNER_ONLY',signals_kept:0}};
assert(message({detail}).includes('zwycięzcę meczu'));
assert.equal(message({detail:{...detail,evaluations:2}}),null);
assert.equal(message({detail:{...detail,market_scope:{...detail.market_scope,signals_kept:null}}}),null);
assert(message({detail:{evaluations:0,results_rows:0}}).includes('Brak danych meczowych'));
assert(source.includes('const evaluationMessage=evaluationIntakeMessage(d.health)'));
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)


def test_bankroll_view_uses_latest_ledger_entries_after_pagination_limit():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('frontend/ineed.js','utf8');
const start=source.indexOf('async function load('),end=source.indexOf('function chart(',start);
const ledger=Array.from({length:600},(_,i)=>({id:i,created_at:i,bankroll_after:200+i}));
const client={rpc:async()=>({data:{}}),from(table){
  let ascending=true,limit=1000;
  const query={select(){return this},eq(){return this},order(k,o){ascending=o.ascending;return this},limit(n){limit=n;return this},
    maybeSingle(){return Promise.resolve({data:table==='ineed_experiments'?{id:'test'}:null})},
    then(resolve){let rows=table==='ineed_bankroll_ledger'?[...ledger]:[];
      if(!ascending)rows.reverse();return Promise.resolve({data:rows.slice(0,limit)}).then(resolve)}};
  return query;
}};
const load=vm.runInNewContext(source.slice(start,end)+';load',{A:()=>({client}),n:v=>Number(v)||0});
load().then(data=>{
  assert.equal(data.ledger.length,500);
  assert.equal(data.ledger.at(-1).bankroll_after,799,'Current balance must not freeze at entry 500');
  assert.equal(data.ledger[0].id,100,'Chart keeps latest bounded window in chronological order');
}).catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)
