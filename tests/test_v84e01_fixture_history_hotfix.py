from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_hotfix_loaded_after_runtime_before_symphony2():
    h=read("frontend/index.html")
    assert h.index("app.js") < h.index("runtime-health-v84e0.js?v=84e0")
    assert h.index("runtime-health-v84e0.js?v=84e0") < h.index("hotfix-v84e01.js?v=84e01")
    assert h.index("hotfix-v84e01.js?v=84e01") < h.index("symphony2.js?v=210")

def test_history_refresh_is_lightweight():
    s=read("frontend/hotfix-v84e01.js")
    assert "data/history.json" in s
    assert "data/history_stats.json" in s
    assert "data/results.json" not in s
    assert "cache:'no-store'" in s
    assert "data-view=\"history\"" in s

def test_status_filter_contract_with_node_when_available():
    node=shutil.which("node")
    if not node:
        return
    script=r'''
const h=require("./frontend/hotfix-v84e01.js");
const bad=[
  {event_status:"Cancelled"},
  {event_status:"Canceled"},
  {event_status:"Walkover"},
  {event_status:"Walk Over"},
  {event_status:"Abandoned"},
  {event_status:"Postponed"},
  {event_status:"Retired"},
  {event_status:"Completed"}
];
for(const m of bad){if(!h.isUnavailableFixture(m))process.exit(11);}
const good=[
  {event_status:null,feed_status:"upcoming"},
  {event_status:"Scheduled"},
  {feed_status:"upcoming"}
];
for(const m of good){if(h.isUnavailableFixture(m))process.exit(12);}
'''
    subprocess.run([node,"-e",script],cwd=ROOT,check=True)

def test_hotfix_does_not_modify_model_math_files():
    s=read("frontend/hotfix-v84e01.js")
    forbidden=["catboost","tabpfn","ensemble_single_model_cap","dynamic_weighting"]
    assert not any(x in s.lower() for x in forbidden)
