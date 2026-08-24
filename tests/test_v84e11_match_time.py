from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_global_time_assets_and_protected_pins():
    idx=read("frontend/index.html")
    assert "match-time-v84e11.css?v=84e11" in idx
    assert "match-time-v84e11.js?v=84e11" in idx
    assert "app.js?v=84b1" in idx
    assert "scenario-studio-v82a.js?v=82a6&hf=84a1" in idx

def test_no_network_or_mutation_observer_and_one_timer():
    js=read("frontend/match-time-v84e11.js")
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js
    assert "new MutationObserver(" not in js
    assert js.count("setInterval(")==1

def test_time_logic_with_node():
    node=shutil.which("node")
    if not node:
        return
    script='\nconst t=require("./frontend/match-time-v84e11.js");\nconst now=Date.parse("2026-08-24T11:00:00Z");\n\nfunction must(cond,msg){\n  if(!cond){console.error(msg);process.exit(13)}\n}\n\nlet x=t.compute({scheduled_time:"2026-08-24T16:17:00Z",feed_status:"upcoming"},now,"full");\nmust(x.kind==="scheduled","future must be scheduled");\nmust(x.text.includes("za 5 h 17 min"),x.text);\n\nx=t.compute({scheduled_time:"2026-08-24T10:47:00Z",feed_status:"upcoming"},now,"full");\nmust(x.kind==="scheduled","past clock cannot imply live");\nmust(x.text.includes("start planowany 13 min temu"),x.text);\nmust(!x.text.includes("TRWA"),"must never fake live");\n\nx=t.compute({scheduled_time:"2026-08-24T10:47:00Z",event_status:"Live"},now,"full");\nmust(x.kind==="live" && x.text.includes("TRWA"),x.text);\n\nx=t.compute({scheduled_time:"2026-08-24T16:17:00Z",event_status:"Cancelled"},now,"full");\nmust(x.kind==="cancelled" && x.text.includes("ANULOWANY"),x.text);\n\nx=t.compute({scheduled_time:"2026-08-24T16:17:00Z",event_status:"Postponed"},now,"full");\nmust(x.kind==="postponed" && x.text.includes("PRZEŁOŻONY"),x.text);\n\nx=t.compute({scheduled_time:"2026-08-24T08:00:00Z",status:"settled"},now,"history");\nmust(x.kind==="finished" && x.text.includes("ZAKOŃCZONY"),x.text);\n'
    subprocess.run([node,"-e",script],cwd=ROOT,check=True)

def test_integrations_are_present():
    js=read("frontend/match-time-v84e11.js")
    for token in ["renderMatchCard","decorateHistory","decorateDraft","decorateSaved"]:
        assert token in js
