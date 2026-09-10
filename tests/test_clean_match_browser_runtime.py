"""Exercise filters on the clean renderer's group/card contract."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_clean_browser_filters_rerenders_and_preserves_raw():
    node = shutil.which("node")
    assert node, "Node is required by the UI workflow"
    subprocess.run([node, "-e", r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const renderer=fs.readFileSync('frontend/project-ui.js','utf8');
for(const cls of ['match-groups','match-group','match-grid','signal-spotlight','match-browser-head'])
  assert(renderer.includes(`class="${cls}"`),`fixture class ${cls} must exist in actual renderer`);
const rows=[{id:1,p1:'A',p2:'B',surface:'Hard',model_confidence:85,scheduled_time:new Date(Date.now()+3600000).toISOString()},
 {id:2,p1:'C',p2:'D',surface:'Clay',model_confidence:90,scheduled_time:new Date(Date.now()+10800000).toISOString()}];
const original=JSON.stringify(rows),handlers={},microtasks=[];
let list=true,patches=0,tools=0;
const cards=rows.map(m=>({hidden:false,dataset:{p751Open:String(m.id)},getAttribute(){return this.dataset.p751Open}}));
const topButtons=cards.map(c=>({...c}));
const top={hidden:false,querySelectorAll:()=>topButtons,querySelector:()=>({})};
const group={hidden:false,dataset:{},querySelector(sel){
 if(sel==='.p751-match-card')return cards[0];
 if(sel==='.match-grid')return {appendChild(){}};
 return null;
},querySelectorAll(sel){return sel.includes(':not([hidden])')?cards.filter(c=>!c.hidden):cards}};
let empty=null;
const groups={querySelectorAll:s=>s==='.match-group'?[group]:[],appendChild(el){if(el!==group)empty=el},querySelector:()=>empty};
const app={querySelector(){return tools?{set outerHTML(v){}}:null},insertAdjacentHTML(){tools++}};
const doc={addEventListener(n,fn){handlers[n]=fn},createElement(){return {remove(){empty=null}}},
 querySelector(sel){
  if(sel==='#app')return app;
  if(sel==='#app .match-browser-head')return list?{}:null;
  if(sel==='#app .match-groups')return list?groups:null;
  if(sel==='#app .signal-spotlight:not([data-playable-top-v917])')return top;
  return null;
 },querySelectorAll(sel){
  if(sel==='#app .match-group:not([hidden]) .p751-match-card[data-p751-open]:not([hidden])')return group.hidden?[]:cards.filter(c=>!c.hidden);
  return [];
 }};
const win={all:rows,addEventListener(){},TENIS_AI_MODEL_API:{allSignals:m=>[{v:m.model_confidence,label:'RAW'}]},
 TENIS_AI_PLAYABLE_UI_V917:{playableSignals:m=>m.id===1?[{v:88}]:[],patchHome(){patches++}}};
vm.runInNewContext(fs.readFileSync('frontend/match-browser.js','utf8'),{window:win,document:doc,sessionStorage:{getItem(){return null},setItem(){}},setTimeout(){},requestAnimationFrame(){},queueMicrotask:fn=>microtasks.push(fn),Date,console});
const api=win.TENIS_AI_MATCH_BROWSER_V945;
const click=mode=>handlers.click({preventDefault(){},target:{closest:s=>s==='[data-v945-mode]'?{dataset:{v945Mode:mode}}:null}});
api.enhance();assert.deepEqual(cards.map(c=>c.hidden),[false,false]);
click('playable');assert.deepEqual(cards.map(c=>c.hidden),[false,true]);assert.deepEqual(topButtons.map(c=>c.hidden),[false,true]);
cards.forEach(c=>c.hidden=false);handlers['tenis-ai:matches-rendered']();assert.equal(cards[1].hidden,true,'filter reapplies after canonical render');
click('2h');assert.deepEqual(cards.map(c=>c.hidden),[false,true]);
click('all');assert.deepEqual(cards.map(c=>c.hidden),[false,false]);assert.equal(topButtons[1].hidden,false,'RAW top restores');
handlers.change({target:{matches:()=>true,value:'Grass'}});assert.equal(group.hidden,true);assert.equal(top.hidden,true);assert(empty);
handlers.change({target:{matches:()=>true,value:'all'}});assert.equal(group.hidden,false);assert.equal(top.hidden,false);assert.equal(empty,null);
while(microtasks.length)microtasks.shift()();assert(patches>0,'resync PLAYABLE after filters');
list=false;tools=0;api.enhance();assert.equal(tools,0,'never insert list controls in another view');
assert.equal(JSON.stringify(rows),original,'presentation cannot mutate model data');
'''], cwd=ROOT, check=True)
