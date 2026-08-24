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
    js=read("frontend/dynamic-weights-v84d1.js")
    css=read("frontend/dynamic-weights-v84d1.css")
    wf=read(".github/workflows/update-and-pages.yml")

    req(idx,'autolearn-v84.css?v=84a1&hf=84a3',"naruszono chroniony pin AutoLearn CSS")
    req(idx,'scenario-studio-v82a.js?v=82a6',"naruszono chroniony pin Scenario Studio")
    req(idx,'dynamic-weights-v84d1.css?v=84d1',"brak CSS v8.4D.1 w index.html")
    if not any(x in idx for x in (
        'dynamic-weights-v84d1.js?v=84d1',
        'dynamic-weights-v84d1.js?v=84d2',
        'dynamic-weights-v84d1.js?v=84e0',
    )):
        ERR.append("brak kompatybilnego JS v8.4D.1/v8.4D.2 w index.html")

    req(js,"DYNAMIC WEIGHTS ${VERSION}","brak nagłówka Dynamic Weights Audit")
    req(js,"local_weights","audit nie czyta lokalnych wag")
    req(js,"dynamic_weighting","audit nie czyta polityki dynamicznej")
    req(js,"GLOBAL","audit nie pokazuje global fallback")
    req(js,"DYNAMIC","audit nie pokazuje trybu dynamicznego")

    req(css,"@media(max-width:520px)","brak mobile layout")
    req(wf,"Dynamic Weights UI Audit Guard v8.4D.1","workflow nie uruchamia guarda v8.4D.1")

    if ERR:
        print("❌ Dynamic Weights UI Audit Guard v8.4D.1 — FAIL")
        for e in ERR:
            print("  -",e)
        return 1
    print("✅ Dynamic Weights UI Audit Guard v8.4D.1 — PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
