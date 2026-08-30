from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "frontend" / "index.html"
GUARD = ROOT / "frontend" / "symphony-playable-detail-guard-v915.js"


def test_guard_is_loaded_after_base_symphony_surface():
    html = INDEX.read_text(encoding="utf-8")
    base = 'symphony-surface-v90.js?v=90e1'
    guard = 'symphony-playable-detail-guard-v915.js?v=915'
    assert base in html
    assert guard in html
    assert html.index(base) < html.index(guard)


def test_guard_requires_verified_superbet_playable_reprojection():
    js = GUARD.read_text(encoding="utf-8")
    assert "operator_reprojection" in js
    assert "verified_operator_match" in js
    assert "PLAYABLE_SUPERBET_ONLY" in js
    assert "compositions" in js
    # The defensive UI must not resurrect the stale RAW shortcut that caused
    # player aces/double-faults to appear in match detail.
    assert "row.full_composition" not in js
    assert "Brak świeżo zweryfikowanej oferty Superbet" in js


def test_open_detail_rechecks_gate_without_rewriting_unchanged_panel():
    import shutil
    import subprocess
    import pytest
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for runtime detail tests')
    subprocess.run([node, '-e', r'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
let active=true,writes=0,html='';
const panel={dataset:{},get innerHTML(){return html;},set innerHTML(v){html=v;writes++;}};
const overlay={
 dataset:{matchKey:'1'},
 querySelector:(selector)=>selector==='[data-symphony-match-detail]'?panel:null
};
const comp={selection:[{label:'One',market:'set1_total',line:12.5},{label:'Two'}],symphony_score:80};
const report={matches:[{id:1,operator_reprojection:{active:true,verified_operator_match:true,status:'PLAYABLE_SUPERBET_ONLY'},compositions:{'2':comp}}]};
const win={TENIS_AI_PLAYABLE_UI_V917:{findMatch:()=>({id:1}),active:()=>active,compositionPlayable:(_m,c)=>active&&c===comp}};
const ctx=vm.createContext({window:win,console,setTimeout:()=>0,clearTimeout(){},
 fetch:async()=>({ok:true,json:async()=>report}),
 document:{querySelector:()=>overlay,addEventListener(){}}});
vm.runInContext(fs.readFileSync('frontend/symphony-playable-detail-guard-v915.js','utf8'),ctx);
const api=win.TENIS_AI_SYMPHONY_PLAYABLE_DETAIL_GUARD_V915;
(async()=>{
 assert.equal(await api.guardOpenMatch(),true);
 assert.ok(html.includes('80/100'));
 const initialWrites=writes;
 assert.equal(await api.guardOpenMatch(),true);
 assert.equal(writes,initialWrites,'unchanged panel must retain user state');
 active=false;
 assert.equal(await api.guardOpenMatch(),false);
 assert.ok(html.includes('Brak świeżo zweryfikowanej oferty'));
 assert.ok(!html.includes('80/100'),'old actionable score must disappear in open detail');
 assert.equal(writes,initialWrites+1);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''], cwd=ROOT, check=True)
