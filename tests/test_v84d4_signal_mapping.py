from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    return (ROOT/p).read_text(encoding="utf-8")

def test_bridge_is_loaded_before_scenario_studio():
    h=read("frontend/index.html")
    bridge=h.index("signal-mapping-v84d4.js?v=84d4")
    studio=h.index("scenario-studio-v82a.js?v=82a6&hf=84a1")
    assert bridge < studio

def test_bridge_does_not_replace_existing_model_files():
    h=read("frontend/index.html")
    assert "autolearn-v84.js?v=84a1&hf=84b1" in h
    assert any(x in h for x in (
        "dynamic-weights-v84d1.js?v=84d2",
        "dynamic-weights-v84d1.js?v=84e0",
    ))
    assert "scenario-studio-v82a.js?v=82a6&hf=84a1" in h

def test_scenario_audit_uses_mapping_bridge():
    s=read("frontend/scenario-dynamic-v84d3.js")
    assert "TENIS_AI_SIGNAL_MAPPING_V84D4" in s
    assert "aliasesFor" in s

def test_bridge_contains_strict_state_aliases():
    s=read("frontend/signal-mapping-v84d4.js")
    assert "sameStateSignal" in s
    assert "x.checkpoint===y.checkpoint" in s
    assert "x.pick===y.pick" in s
    assert "game_state|${cp}|${pick}" in s
    assert "state|${cp}|${pick}" in s

def test_real_alias_logic_with_node_when_available():
    node=shutil.which("node")
    if not node:
        return
    script=r'''
const b=require("./frontend/signal-mapping-v84d4.js");
const a=b.aliasesFor({key:"game_state|2|1:1",market:"game_state",checkpoint:2,pick:"1:1"});
if(!a.includes("state|2|1:1")) process.exit(11);
if(!b.sameStateSignal({key:"state|2|1:1"},{key:"game_state|2|1:1"})) process.exit(12);
if(b.sameStateSignal({key:"state|2|1:1"},{key:"game_state|4|1:1"})) process.exit(13);
if(b.sameStateSignal({key:"state|2|1:1"},{key:"game_state|2|2:0"})) process.exit(14);
'''
    subprocess.run([node,"-e",script],cwd=ROOT,check=True)
