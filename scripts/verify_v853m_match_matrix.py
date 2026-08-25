from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
index=(ROOT/"frontend/index.html").read_text(encoding="utf-8")
ui=(ROOT/"frontend/ui-v751.js").read_text(encoding="utf-8")
mx=(ROOT/"frontend/model-guide.js").read_text(encoding="utf-8")

errors=[]
def need(text,needle,label):
    if needle not in text: errors.append("brak: "+label)
def forbid(text,needle,label):
    if needle in text: errors.append("nadal jest: "+label)

need(mx,"MACIERZ RYNKÓW × MODELI","macierz rynkow")
need(mx,"Po 2 / 4 / 6 gemach","3-way game-state group")
need(mx,"Current","Current")
need(mx,"CatBoost","CatBoost")
need(mx,"TabPFN","TabPFN")
need(mx,"Ensemble","Ensemble")
need(mx,"Learn SH","Adaptive Learning shadow")
need(mx,"Player SH","Player Intelligence shadow")
need(mx,"Market Lab","Market Lab") if False else None
need(mx,"joint_builder_v78b","Joint Builder data")
need(mx,"market_lab_v741","Market Lab data")
need(mx,"data-p751-lazy78e23=\"stats\"","preserved player stats")
need(mx,"data-p751-lazy78e23=\"analytics\"","preserved Player Analytics PRO")
need(mx,"data-p751-lazy78e23=\"serve\"","preserved aces/DF")
need(index,"model-guide.js?v=853m1","cache-busted matrix asset")
forbid(index,'id="model-switcher"',"Wybierz model")
forbid(ui,'data-p751-models aria-label="Modele"',"pink brain in detail header")
forbid(ui,'class="model" data-p751-models',"model button in Match Center")
forbid(ui,"function openModels()","dead model picker popup")
forbid(mx,"fetch(","network request in matrix")
forbid(mx,"setInterval(","polling in matrix")

if errors:
    print("v8.5.3M Match Matrix Guard: FAIL")
    for x in errors: print(" -",x)
    raise SystemExit(1)
print("v8.5.3M Match Matrix Guard: PASS")
