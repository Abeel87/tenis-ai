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
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)
