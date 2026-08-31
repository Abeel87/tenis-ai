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

    req(js,"const VERSION='v8.4D.4'","audit UI nie jest aktualnym v8.4D.4")
    req(js,"poolRows=signalRows(results)","brak jawnej pełnej puli sygnałów")
    req(js,"activePool=poolRows.filter","brak licznika dynamicznej części puli")
    req(js,"globalPool=poolRows.filter","brak licznika GLOBAL/SAFE")
    req(js,"Wszystkie sygnały","brak licznika pełnej puli")
    req(js,"Audyt pełnej puli MODEL/RAW","brak jawnego zakresu MODEL/RAW")
    req(js,"Symfonia 2.0 korzysta z własnego operator-first pipeline","brak izolacji Symfonii 2.0")
    req(js,"nie steruje PLAYABLE","Dynamic Weights nie deklaruje izolacji od PLAYABLE")
    if "TENIS_AI_SCENARIOS" in js or "currentScenarioRows" in js:
        ERR.append("Dynamic Weights nadal zależy od wycofanego Scenario draftu")

    req(css,"v8.4D.2 scope label","brak stylu informacji o zakresie")
    req(idx,'autolearn-v84.css?v=84a1&hf=84a3',"naruszono chroniony pin AutoLearn CSS")
    req(idx,'dynamic-weights-v84d1.js?v=84e0',"brak aktywnego Dynamic Weights UI")
    req(idx,'symphony2.js?v=210',"brak aktywnej Symfonii 2.0")
    if 'scenario-studio-v82a.js' in idx:
        ERR.append("wycofany Scenario Studio nadal jest bootstrappowany")

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
