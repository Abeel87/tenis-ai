from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "playable-ui.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-visibility.js").read_text(encoding="utf-8")


def test_v917_requires_fresh_verified_superbet_context():
    assert "operator_verified===true" in UI
    assert "x.status==='VERIFIED'" in UI
    assert "x.suspended!==true" in UI
    assert "if(!active(match)||!row||typeof row!=='object')return false" in UI
    assert "function preMatch(match,now=Date.now())" in UI
    assert "function fallbackNonPrematchStatus(match)" in UI
    assert "scheduled<=Number(now)" in UI


def test_v917_matches_exact_operator_selection_not_just_market_family():
    assert "availability(match).has(signature(row))" in UI
    assert "Number(line).toFixed(6)" in UI
    assert "rowCheckpoint" in UI
    assert "rowPlayer" in UI
    assert "canonical_selections" in UI


def test_v917_actionable_surfaces_share_one_gate_without_erasing_raw_detail():
    assert "playableSignals(match,60)" in UI
    assert "match?.superbet_playable_v912" in UI
    assert "projectionSignals(match" in UI
    assert "&&isPlayable(match,row)" in UI
    assert "decisionRows(match,api)" in UI
    assert "legs.every(leg=>isPlayable(match,leg))" in UI
    assert "Brak Superbet PLAYABLE" in UI
    assert "Brak świeżej oferty Superbet" in UI
    assert "MODEL / RAW oraz modelowy FINAL pozostają widoczne bez zmian" in UI
    assert "built=api.buildRows(match)||[]" in UI
    assert "if(!operatorRow)return {...row,operator_playable:false}" in UI
    assert "operator_playable:true" in UI


def test_v917_missing_score_is_nd_not_zero():
    assert "return finite(v)?`${Math.round(Number(v))}/100`:'N/D'" in UI
    assert "N/D · brak PLAYABLE" in UI


def test_match_visibility_does_not_boot_playable_runtime():
    assert "playable-ui-coherence-v917.js" not in LOADER
    assert "playable-ui.js" not in LOADER
    assert "setTimeout(loadSuperbetModelCoverage,0)" in LOADER
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
const selections=[{market:'set1_total',pick:'under',line:12.5,operator_available:true,operator_line_verified:true,fixture_line_verified:true},{market:'set1_tiebreak',pick:'no',operator_available:true}];
const match={id:1,scheduled_time:'2026-08-28T14:00:00Z',feed_status:'upcoming',
  superbet_market_v91:{operator_verified:true,status:'VERIFIED',suspended:false,
    source_generated_at:'2026-08-28T11:00:00Z',canonical_selections:selections}};
const rows=new Map([['1',match]]);
const win={TENIS_AI_MATCH_TIME:require('./frontend/match-time.js'),
  TENIS_AI_PROJECT_UI:{findMatch:key=>rows.get(key)},
  TENIS_AI_MODEL_API:{signals:()=>[{...selections[0],v:80},{...selections[1],v:null}]}};
const ctx=vm.createContext({window:win,Date:Clock,console,setTimeout:()=>0,
  document:{readyState:'loading',addEventListener(){}}});
vm.runInContext(fs.readFileSync('frontend/playable-ui.js','utf8'),ctx);
const api=win.TENIS_AI_PLAYABLE_UI_V917;
assert.equal(api.active(match),true);
assert.equal(api.findMatch('id:1'),match);
assert.equal(api.playableSignals(match).length,1,'null score must not become zero');
const staleProjection={...match,superbet_playable_v912:{signals:[{...selections[0],line:11.5,v:90,operator_playable:true}]}};
assert.equal(api.playableSignals(staleProjection).length,0,'backend PLAYABLE snapshot must be revalidated against exact current offer');
const alignedProjection={...match,superbet_playable_v912:{signals:[{...selections[0],v:90,operator_playable:true}]}};
assert.equal(api.playableSignals(alignedProjection).length,1,'exact current-offer projection remains PLAYABLE');
assert.equal(api.isPlayable(match,{...selections[0],line:11.5}),false);
assert.equal(api.compositionPlayable(match,{selection:selections}),true);
assert.equal(api.compositionPlayable(match,{selection:[selections[0]]}),false);
assert.equal(api.compositionPlayable(match,{selection:[selections[0],{...selections[1],pick:'yes'}]}),false);
const malformedMatch=canonical=>({...match,superbet_market_v91:{...match.superbet_market_v91,canonical_selections:canonical}});
assert.equal(api.isPlayable(malformedMatch([{...selections[0],operator_available:undefined}]),selections[0]),false,'missing operator_available must fail closed');
assert.equal(api.isPlayable(malformedMatch([{...selections[0],operator_available:false}]),selections[0]),false,'operator_available=false must fail closed');
assert.equal(api.isPlayable(malformedMatch([{...selections[0],operator_line_verified:undefined}]),selections[0]),false,'missing operator_line_verified must fail closed');
assert.equal(api.isPlayable(malformedMatch([{...selections[0],fixture_line_verified:undefined}]),selections[0]),false,'missing fixture_line_verified must fail closed');
assert.notEqual(api.signature({market:'set_handicap',pick:'Player A',line:-1.5}),api.signature({market:'set_handicap',pick:'Player A',line:-2.5}),'set handicap signature must keep exact line');
assert.notEqual(api.signature({market:'set3_game_handicap',pick:'Player A',line:-1.5}),api.signature({market:'set3_game_handicap',pick:'Player A',line:-2.5}),'set3 handicap signature must keep exact line');
for(const source_generated_at of [null,'','bad','2026-08-28T12:00:01Z','2026-08-28T09:00:00Z']){
 assert.equal(api.active({...match,superbet_market_v91:{...match.superbet_market_v91,source_generated_at}}),false);
}
for(const status of ['CACHE_STALE','NOT_FOUND']){
 assert.equal(api.active({...match,superbet_market_v91:{...match.superbet_market_v91,status}}),false);
}
assert.equal(api.active({...match,superbet_market_v91:{...match.superbet_market_v91,suspended:true}}),false);
assert.equal(api.active({...match,feed_status:'completed'}),false);
assert.equal(api.preMatch({...match,scheduled_time:'2026-08-28T12:00:00Z'}),false,'PLAYABLE expires exactly at scheduled start');
assert.equal(api.active({...match,scheduled_time:'2026-08-28T12:00:00Z'}),false,'no 30-minute PLAYABLE grace after scheduled start');
assert.equal(api.active({...match,scheduled_time:'2026-08-28T11:59:59Z'}),false);
assert.equal(api.active({...match,feed_status:'live'}),false,'known live status is never pre-match PLAYABLE');
const savedMatchTime=win.TENIS_AI_MATCH_TIME;
delete win.TENIS_AI_MATCH_TIME;
assert.equal(api.active({...match,feed_status:'live'}),false,'UI fallback must reject live even if match-time helper is unavailable');
assert.equal(api.active({...match,feed_status:'not_started'}),true,'UI fallback must preserve explicit not-started fixtures');
win.TENIS_AI_MATCH_TIME=savedMatchTime;
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
