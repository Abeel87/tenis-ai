#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ERR=[]

def read(path):
    p=ROOT/path
    if not p.exists():
        ERR.append(f"brak pliku: {path}")
        return ""
    return p.read_text(encoding="utf-8")

def req(text,needle,msg):
    if needle not in text:
        ERR.append(msg)

def main():
    js=read("frontend/match-time-v84e11.js")
    css=read("frontend/match-time-v84e11.css")
    idx=read("frontend/index.html")
    ui=read(".github/workflows/ui-smoke.yml")
    pages=read(".github/workflows/update-and-pages.yml")

    req(js,"const VERSION='v8.4E1.1'","brak wersji E1.1")
    req(js,"A passed scheduled time never implies LIVE","brak zasady no-fake-live")
    req(js,"start planowany","brak bezpiecznego stanu po planowanym starcie")
    req(js,"cancelled|canceled","brak statusu cancelled")
    req(js,"postponed","brak statusu postponed")
    req(js,"setInterval(refreshAll,TICK_MS)","brak jednego globalnego zegara")
    req(js,"decorateHistory","brak integracji Historia")
    req(js,"decorateDraft","brak integracji Scenario draft")
    req(js,"decorateSaved","brak integracji zapisanych scenariuszy")
    req(js,"renderMatchCard","brak integracji głównej listy")

    if "fetch(" in js or "XMLHttpRequest" in js:
        ERR.append("Global Match Time nie może wykonywać requestów")
    if "new MutationObserver(" in js:
        ERR.append("Global Match Time nie może dodawać MutationObservera")
    if js.count("setInterval(") != 1:
        ERR.append("Global Match Time ma mieć dokładnie jeden setInterval")

    req(css,".tai-match-time","brak stylu czasu")
    req(idx,'match-time-v84e11.css?v=84e11',"index nie ładuje CSS E1.1")
    req(idx,'match-time-v84e11.js?v=84e11',"index nie ładuje JS E1.1")
    req(idx,'app.js?v=84b1',"naruszono chroniony app.js pin")
    req(idx,'scenario-studio-v82a.js?v=82a6&hf=84a1',"naruszono chroniony Scenario Studio pin")
    req(ui,"Global Match Time Guard v8.4E1.1","UI smoke nie ma guarda")
    req(pages,"Global Match Time Guard v8.4E1.1","Pages workflow nie ma guarda")

    if ERR:
        print("❌ Global Match Time Guard v8.4E1.1 — FAIL")
        for e in ERR:
            print("  -",e)
        return 1
    print("✅ Global Match Time Guard v8.4E1.1 — PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
