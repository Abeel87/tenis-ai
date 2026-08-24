from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ERR=[]

def read(p):
    f=ROOT/p
    if not f.exists():
        ERR.append(f"brak pliku: {p}")
        return ""
    return f.read_text(encoding="utf-8")

def req(text,needle,msg):
    if needle not in text:
        ERR.append(msg)

def main():
    bridge=read("frontend/signal-mapping-v84d4.js")
    audit=read("frontend/scenario-dynamic-v84d3.js")
    idx=read("frontend/index.html")
    wf=read(".github/workflows/update-and-pages.yml")

    req(bridge,"const VERSION='v8.4D.4'","Signal Mapping Bridge nie jest v8.4D.4")
    req(bridge,"state|${cp}|${pick}","brak aliasu state")
    req(bridge,"game_state|${cp}|${pick}","brak aliasu game_state")
    req(bridge,"sameStateSignal","brak ścisłego porównania checkpoint + stan")
    req(bridge,"resolveFromMatch","brak resolvera aliasów")
    req(bridge,"auto.scoreFor=function","bridge nie podpina się pod AutoLearn scoreFor")
    req(bridge,"No fuzzy matching","brak deklaracji zakazu fuzzy matchingu")

    req(audit,"TENIS_AI_SIGNAL_MAPPING_V84D4","audyt scenariusza nie korzysta z bridge v8.4D.4")
    req(audit,"aliasesFor","audyt nie indeksuje aliasów równoważnych kluczy")

    req(idx,'autolearn-v84.js?v=84a1&hf=84b1',"naruszono chroniony AutoLearn JS")
    if not any(x in idx for x in (
        'dynamic-weights-v84d1.js?v=84d2',
        'dynamic-weights-v84d1.js?v=84e0',
    )):
        ERR.append("naruszono kompatybilny pin v8.4D.2/v8.4E0")
    req(idx,'signal-mapping-v84d4.js?v=84d4',"brak Signal Mapping Bridge w index.html")
    req(idx,'scenario-studio-v82a.js?v=82a6&hf=84a1',"naruszono Scenario Studio")
    req(idx,'scenario-dynamic-v84d3.js?v=84d4',"brak nowego cache-bust audytu scenariusza")

    req(wf,"Signal Mapping Bridge Guard v8.4D.4","workflow nie uruchamia guarda v8.4D.4")

    if ERR:
        print("❌ Signal Mapping Bridge Guard v8.4D.4 — FAIL")
        for e in ERR:
            print("  -",e)
        return 1

    print("✅ Signal Mapping Bridge Guard v8.4D.4 — PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
