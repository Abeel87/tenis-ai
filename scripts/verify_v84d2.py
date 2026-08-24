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

    req(js,"const VERSION='v8.4D.2'","audit UI nie jest v8.4D.2")
    req(js,"TENIS_AI_SCENARIOS","audit nie korzysta z aktualnego draftu Scenariuszy AI")
    req(js,"currentScenarioRows","brak separacji aktualnego scenariusza od puli")
    req(js,"Aktualny scenariusz","brak licznika aktualnego scenariusza")
    req(js,"Cała pula","brak osobnego licznika całej puli")
    req(js,"signalCount","brak licznika sygnałów draftu")
    req(js,"matchCount","brak licznika spotkań draftu")

    req(css,"v8.4D.2 scope label","brak stylu informacji o zakresie")

    req(idx,'autolearn-v84.css?v=84a1&hf=84a3',"naruszono chroniony pin AutoLearn CSS")
    req(idx,'scenario-studio-v82a.js?v=82a6&hf=84a1',"naruszono chroniony pin Scenario Studio")
    req(idx,'dynamic-weights-v84d1.js?v=84d2',"brak cache-bust v8.4D.2")

    req(wf,"Dynamic Weights View Scope Guard v8.4D.2","workflow nie uruchamia guarda v8.4D.2")

    if ERR:
        print("❌ Dynamic Weights View Scope Guard v8.4D.2 — FAIL")
        for e in ERR:
            print("  -",e)
        return 1

    print("✅ Dynamic Weights View Scope Guard v8.4D.2 — PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
