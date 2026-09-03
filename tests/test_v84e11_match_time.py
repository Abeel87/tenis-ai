from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_global_time_assets_and_protected_pins():
    idx=read("frontend/index.html")
    assert "match-time.css" in idx
    assert "match-time.js" in idx
    assert "match-time-v84e11.css" not in idx
    assert "match-time-v84e11.js" not in idx
    assert "app.js?v=84b1" in idx
    assert "symphony2.js?v=220" in idx
    assert "scenario-studio-v82a.js" not in idx

def test_no_network_or_mutation_observer_and_one_timer():
    js=read("frontend/match-time.js")
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js
    assert "new MutationObserver(" not in js
    assert js.count("setInterval(")==1

def test_time_logic_with_node():
    node=shutil.which("node")
    if not node:
        return
    script='\nconst t=require("./frontend/match-time.js");\nconst now=Date.parse("2026-08-24T11:00:00Z");\n\nfunction must(cond,msg){\n  if(!cond){console.error(msg);process.exit(13)}\n}\n\nlet x=t.compute({scheduled_time:"2026-08-24T16:17:00Z",feed_status:"upcoming"},now,"full");\nmust(x.kind==="scheduled","future must be scheduled");\nmust(x.text.includes("za 5 h 17 min"),x.text);\n\nx=t.compute({scheduled_time:"2026-08-24T10:47:00Z",feed_status:"upcoming"},now,"full");\nmust(x.kind==="scheduled","past clock cannot imply live");\nmust(x.text.includes("start planowany 13 min temu"),x.text);\nmust(!x.text.includes("TRWA"),"must never fake live");\n\nx=t.compute({scheduled_time:"2026-08-24T10:47:00Z",event_status:"Live"},now,"full");\nmust(x.kind==="live" && x.text.includes("TRWA"),x.text);\n\nx=t.compute({scheduled_time:"2026-08-24T16:17:00Z",event_status:"Cancelled"},now,"full");\nmust(x.kind==="cancelled" && x.text.includes("ANULOWANY"),x.text);\n\nx=t.compute({scheduled_time:"2026-08-24T16:17:00Z",event_status:"Postponed"},now,"full");\nmust(x.kind==="postponed" && x.text.includes("PRZEŁOŻONY"),x.text);\n\nx=t.compute({scheduled_time:"2026-08-24T08:00:00Z",status:"settled"},now,"history");\nmust(x.kind==="finished" && x.text.includes("ZAKOŃCZONY"),x.text);\n'
    subprocess.run([node,"-e",script],cwd=ROOT,check=True)

def test_integrations_are_present_without_retired_scenario_runtime():
    js=read("frontend/match-time.js")
    for token in ["renderMatchCard","decorateHistory"]:
        assert token in js
    for retired in ["decorateDraft","decorateSaved","decorateScenario","TENIS_AI_SCENARIOS","scenario-v82a-panel","tenis-ai-scenario-settlement"]:
        assert retired not in js


def test_current_match_selector_and_card_status_regression():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for frontend lifecycle regression tests")
    script = r'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const time=require('./frontend/match-time.js');
const now=Date.parse('2026-08-28T12:15:00Z');
const future={id:'future',scheduled_time:'2026-08-28T15:00:00+02:00',feed_status:'upcoming',model_ready:false};
const old={id:'old',scheduled_time:'2026-08-28T10:15:00Z',feed_status:'upcoming',model_ready:true};
const waiting={id:'waiting',scheduled_time:'2026-08-28T12:00:00Z',feed_status:'upcoming'};
const atStart={...future,scheduled_time:'2026-08-28T12:15:00Z'};
const boundary={...future,scheduled_time:'2026-08-28T11:45:00Z'};
assert.equal(time.isCurrent(old,now),false);
assert.equal(time.isCurrent({...old,scheduled_time:'2026-08-28T10:45:00Z'},now),false);
assert.equal(time.isCurrent(future,now),true);
assert.equal(time.isCurrent(waiting,now),true);
assert.equal(time.isCurrent(boundary,now),true);
assert.equal(time.isCurrent(boundary,now+1),false);
assert.equal(time.cardStatus(future,now).txt,'PRZED MECZEM');
assert.equal(time.cardStatus(waiting,now).txt,'OCZEKUJE NA STATUS');
assert.equal(time.cardStatus(atStart,now).cls,'waiting');
assert.equal(time.cardStatus(old,now).cls,'waiting');
for(const scheduled_time of [null,'','invalid']){
  assert.equal(time.isCurrent({...future,scheduled_time},now),true);
  assert.equal(time.cardStatus({...future,scheduled_time},now).txt,'CZAS N/D');
}
for(const event_status of ['not started','not_started','not-started','notstarted']) assert.equal(time.cardStatus({...future,event_status},now).cls,'upcoming');
for(const event_status of ['Live','in_progress','Started']) assert.equal(time.cardStatus({...waiting,event_status},now).cls,'live');
for(const event_status of ['Cancelled','Postponed','Abandoned','Walkover','Retired','Completed','Ended','void']) assert.equal(time.isCurrent({...future,event_status},now),false,event_status);
assert.equal(time.statusKind({feed_status:'live',status:'settled'}),'finished');
assert.equal(time.statusKind({feed_status:'live',result:{status:'completed'}}),'finished');
assert.equal(time.statusKind({event_status:'Suspended',feed_status:'live'}),'suspended');
assert.equal(time.statusKind({event_status:'Interrupted',feed_status:'live'}),'interrupted');
assert.equal(time.compute({...waiting,event_status:'Suspended'},now).text.includes('ZAWIESZONY'),true);
assert.equal(time.cardStatus({...future,scheduled_time:'2026-08-28T14:15:00+02:00'},now).cls,'waiting');
assert.equal(time.cardStatus({...future,scheduled_time:'2026-01-28T13:15:00+01:00'},Date.parse('2026-01-28T12:15:00Z')).cls,'waiting');
class Clock extends Date {static now(){return now}}
const elements=['old','future','old','waiting'].map(id=>({dataset:{p751Open:encodeURIComponent(id)},removed:false,remove(){this.removed=true}}));
let counts=0, renders=0;
const ctx=vm.createContext({Date:Clock,all:[],filteredReady:()=>[future,old],setTimeout:()=>0,queueMicrotask:()=>{},updateCounts:()=>counts++,renderMatches:()=>renders++,document:{querySelectorAll:selector=>selector.includes('[data-p751-open]')?elements:[],querySelector:()=>null,createElement:()=>({dataset:{},addEventListener:()=>{}}),head:{appendChild:()=>{}}}});
ctx.window=ctx;ctx.TENIS_AI_MATCH_TIME=time;
vm.runInContext(fs.readFileSync('frontend/match-visibility.js','utf8'),ctx);
ctx.all=[future,old,waiting,{...future,id:'cancelled',event_status:'Cancelled'},null];
const api=ctx.TENIS_AI_MATCH_VISIBILITY_V916;
assert.equal(JSON.stringify(ctx.filteredReady().map(m=>m.id)),JSON.stringify(['future','waiting']));
assert.equal(api.analysisReadyMatches().length,2);
assert.equal(api.visibleMatches(now+3600000).some(m=>m.id==='waiting'),false);
api.refreshClock();
assert.deepEqual(elements.map(x=>x.removed),[true,false,true,false]);
assert.equal(counts,1);assert.equal(renders,0);assert.equal(ctx.all.length,5);
let tick, refreshes=0;const listeners={};
const badge={dataset:{scheduledTime:waiting.scheduled_time,matchStatus:'upcoming'},className:'p751-status upcoming',textContent:'PRZED MECZEM'};
const clockCtx=vm.createContext({Date:Clock,setTimeout:()=>0,setInterval:(fn,ms)=>{assert.equal(ms,15000);tick=fn;return 1},document:{hidden:false,querySelectorAll:s=>s==='[data-tai-match-status="1"]'?[badge]:[],addEventListener:(type,fn)=>listeners[type]=fn},TENIS_AI_MATCH_VISIBILITY_V916:{refreshClock:()=>refreshes++}});
clockCtx.window=clockCtx;
vm.runInContext(fs.readFileSync('frontend/match-time.js','utf8'),clockCtx);
tick();assert.equal(badge.textContent,'OCZEKUJE NA STATUS');assert.equal(refreshes,1);
clockCtx.document.hidden=true;tick();assert.equal(refreshes,1);
clockCtx.document.hidden=false;listeners.visibilitychange();assert.equal(refreshes,2);
console.log('Match lifecycle regression: PASS');
'''
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)
