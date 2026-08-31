from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "playable-ui-coherence-v917.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-list-visibility-v916.js").read_text(encoding="utf-8")


def test_v917_requires_fresh_verified_superbet_context():
    assert "operator_verified===true" in UI
    assert "x.status==='VERIFIED'" in UI
    assert "x.suspended!==true" in UI
    assert "if(!active(match)||!row||typeof row!=='object')return false" in UI


def test_v917_matches_exact_operator_selection_not_just_market_family():
    assert "availability(match).has(signature(row))" in UI
    assert "Number(line).toFixed(6)" in UI
    assert "rowCheckpoint" in UI
    assert "rowPlayer" in UI
    assert "canonical_selections" in UI


def test_v917_actionable_surfaces_share_one_gate():
    assert "playableSignals(match,60)" in UI
    assert "api.buildRows(match).filter(row=>isPlayable(match,row))" in UI
    assert "legs.every(leg=>isPlayable(match,leg))" in UI
    assert "Brak Superbet PLAYABLE" in UI
    assert "Brak świeżo zweryfikowanej oferty Superbet" in UI


def test_v917_missing_score_is_nd_not_zero():
    assert "return finite(v)?`${Math.round(Number(v))}/100`:'N/D'" in UI
    assert "N/D · brak PLAYABLE" in UI


def test_v917_loader_runs_after_existing_frontend_scripts():
    assert "playable-ui-coherence-v917.js?v=925&contract=raw-playable" in LOADER
    assert "setTimeout(loadPlayableUiV917,0)" in LOADER
    assert "raw-playable-separation-v921" not in LOADER


def test_runtime_expiry_keeps_exact_selection_gate():
    import shutil
    import subprocess
    import pytest

    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for runtime UI tests')
    subprocess.run([node, '-e', r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
let now=Date.parse('2026-08-28T12:00:00Z');
class Clock extends Date { static now(){return now;} }
const selections=[{market:'set1_total',pick:'under',line:12.5},{market:'set1_tiebreak',pick:'no'}];
const match={id:1,scheduled_time:'2026-08-28T14:00:00Z',feed_status:'upcoming',
  superbet_market_v91:{operator_verified:true,status:'VERIFIED',suspended:false,
    source_generated_at:'2026-08-28T11:00:00Z',canonical_selections:selections}};
const rows=new Map([['1',match]]);
const win={TENIS_AI_MATCH_TIME:require('./frontend/match-time-v84e11.js'),
  TENIS_AI_PROJECT_UI:{findMatch:key=>rows.get(key)},
  TENIS_AI_MODEL_API:{signals:()=>[{...selections[0],v:80},{...selections[1],v:null}]}};
const ctx=vm.createContext({window:win,Date:Clock,console,setTimeout:()=>0,
  document:{readyState:'loading',addEventListener(){}}});
vm.runInContext(fs.readFileSync('frontend/playable-ui-coherence-v917.js','utf8'),ctx);
const api=win.TENIS_AI_PLAYABLE_UI_V917;
assert.equal(api.active(match),true);
assert.equal(api.findMatch('id:1'),match);
assert.equal(api.playableSignals(match).length,1,'null score must not become zero');
assert.equal(api.isPlayable(match,{...selections[0],line:11.5}),false);
assert.equal(api.compositionPlayable(match,{selection:selections}),true);
assert.equal(api.compositionPlayable(match,{selection:[selections[0]]}),false);
assert.equal(api.compositionPlayable(match,{selection:[selections[0],{...selections[1],pick:'yes'}]}),false);
for(const source_generated_at of [null,'','bad','2026-08-28T12:00:01Z','2026-08-28T09:00:00Z']){
 assert.equal(api.active({...match,superbet_market_v91:{...match.superbet_market_v91,source_generated_at}}),false);
}
for(const status of ['CACHE_STALE','NOT_FOUND']){
 assert.equal(api.active({...match,superbet_market_v91:{...match.superbet_market_v91,status}}),false);
}
assert.equal(api.active({...match,superbet_market_v91:{...match.superbet_market_v91,suspended:true}}),false);
assert.equal(api.active({...match,feed_status:'completed'}),false);
assert.equal(api.active({...match,scheduled_time:'2026-08-28T10:00:00Z'}),false);
assert.equal(api.active({...match,superbet_market_v91:{...match.superbet_market_v91,source_max_age_hours:0}}),false);
const before=JSON.stringify(match);
now=Date.parse('2026-08-28T12:48:00Z');
assert.equal(api.active(match),true,'inclusive 108-minute backend boundary');
now+=1;
assert.equal(api.active(match),false,'expiry must use current clock, not frozen source_age_hours');
assert.equal(api.playableSignals(match).length,0);
assert.equal(JSON.stringify(match),before,'UI must not mutate stored inputs');
'''], cwd=ROOT, check=True)
