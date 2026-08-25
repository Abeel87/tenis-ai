from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
mx=(ROOT/"frontend/model-guide.js").read_text(encoding="utf-8")
idx=(ROOT/"frontend/index.html").read_text(encoding="utf-8")
errors=[]
def need(s,m):
    if s not in mx: errors.append("brak: "+m)
def forbid(s,m):
    if s in mx: errors.append("nadal jest: "+m)
need("V853M3_MODEL_PICKER_START","picker")
need("MM853M3_MAX=5","limit 5")
need("AUTO 5","auto selector")
need("Pokaż rynki bez danych","empty rows toggle")
need("coverage","coverage counts")
need("installPicker(matrixEl,m)","picker mount")
need("position:static!important","no sticky overlap")
forbid("fetch(","network in matrix")
forbid("setInterval(","polling in matrix")
if "model-guide.js?v=853m3" not in idx: errors.append("brak cache bust 853m3")
if errors:
    print("v8.5.3M3 Model Picker Guard: FAIL")
    for x in errors: print(" -",x)
    raise SystemExit(1)
print("v8.5.3M3 Model Picker Guard: PASS")
