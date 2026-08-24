from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ERR=[]

def read(p):
    f=ROOT/p
    if not f.exists():
        ERR.append(f"brak pliku: {p}")
        return ""
    return f.read_text(encoding="utf-8")

def req(text, needle, msg):
    if needle not in text:
        ERR.append(msg)

def main():
    idx=read("frontend/index.html")
    js=read("frontend/scenario-dynamic-v84d3.js")
    css=read("frontend/scenario-dynamic-v84d3.css")
    wf=read(".github/workflows/update-and-pages.yml")

    req(js,"const VERSION='v8.4D.3'","moduł scenariusza nie jest v8.4D.3")
    req(js,"TENIS_AI_SCENARIOS","brak integracji z bieżącym draftem")
    req(js,"data-sc-remove","brak mapowania wpisu scenariusza")
    req(js,"dynamic_weighting","brak odczytu polityki dynamicznej")
    req(js,"effective_weights","brak odczytu lokalnych wag")
    req(js,"DYNAMIC","brak etykiety DYNAMIC")
    req(js,"GLOBAL","brak etykiety GLOBAL")
    req(js,"MAX SHIFT","brak podsumowania shift")

    req(css,"@media(max-width:520px)","brak mobile responsive dla audytu scenariusza")

    req(idx,'autolearn-v84.css?v=84a1&hf=84a3',"naruszono chroniony pin AutoLearn CSS")
    if not any(x in idx for x in (
        'dynamic-weights-v84d1.js?v=84d2',
        'dynamic-weights-v84d1.js?v=84e0',
    )):
        ERR.append("naruszono kompatybilny pin View Scope v8.4D.2/v8.4E0")
    req(idx,'scenario-studio-v82a.js?v=82a6&hf=84a1',"naruszono chroniony pin Scenario Studio")
    req(idx,'scenario-dynamic-v84d3.css?v=84d3',"brak CSS v8.4D.3 w index.html")
    if not any(x in idx for x in (
        'scenario-dynamic-v84d3.js?v=84d3',
        'scenario-dynamic-v84d3.js?v=84d4',
    )):
        ERR.append("brak kompatybilnego JS v8.4D.3/v8.4D.4 w index.html")

    req(wf,"Scenario Dynamic Audit Guard v8.4D.3","workflow nie uruchamia guarda v8.4D.3")

    if ERR:
        print("❌ Scenario Dynamic Audit Guard v8.4D.3 — FAIL")
        for e in ERR:
            print("  -",e)
        return 1

    print("✅ Scenario Dynamic Audit Guard v8.4D.3 — PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
