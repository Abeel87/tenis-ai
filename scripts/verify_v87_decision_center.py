from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "model-guide.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "model-guide.css").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

errors: list[str] = []


def need(text: str, marker: str, label: str) -> None:
    if marker not in text:
        errors.append("brak: " + label)


def forbid(text: str, marker: str, label: str) -> None:
    if marker in text:
        errors.append("nadal jest: " + label)


need(UI, "Centrum Decyzji Meczu", "nazwa nowego centrum")
for marker, label in [
    ('data-dc-mode="top"', "domyślny tryb Top"),
    ('data-dc-mode="all"', "tryb Wszystkie"),
    ('data-dc-mode="pro"', "tryb PRO"),
    ("['all','Wszystkie']", "reset filtrów"),
    ("['result','Wynik']", "filtr Wynik"),
    ("['games','Gemy']", "filtr Gemy"),
    ("['checkpoints','Po 2/4/6']", "filtr Po 2/4/6"),
    ("['special','Specjalne']", "filtr Specjalne"),
    ('type="search"', "wyszukiwarka"),
    ("Pełne szczegóły modeli", "rozwijane szczegóły"),
    ("mode==='pro'?'open':''", "automatycznie otwarte modele w PRO"),
]:
    need(UI, marker, label)

for marker in [
    "Current",
    "CatBoost",
    "TabPFN",
    "Ensemble",
    "Adaptive",
    "Player SH",
    "Market Lab",
    "Joint",
]:
    need(UI, marker, "model " + marker)

need(UI, "Player SH i Market Lab działają wyłącznie w SHADOW", "jawny status shadow")
need(UI, "Accuracy Lab v8.6 pozostaje osobnym raportem SHADOW", "Accuracy Lab bez wyniku live")
need(UI, "auto?.final_score", "FINAL z backendowego Adaptive")
need(UI, "auto?.ensemble_raw", "RAW Ensemble")
need(UI, "adaptive_delta_pp", "backendowa delta Adaptive")
need(UI, "declaredMode!=='PROD'", "fail-safe dla starych rekordów Adaptive")
need(UI, "Adaptive '+esc(mode)+' · '+esc(status)+(legacyMode?' · SYNC':'')", "badge kontrolowanego PROD")
need(UI, "UI niczego nie przelicza", "informacja o braku obliczeń UI")
need(UI, 'data-p751-lazy78e23="stats"', "zachowane statystyki graczy")
need(UI, 'data-p751-lazy78e23="analytics"', "zachowane Player Analytics PRO")
need(UI, 'data-p751-lazy78e23="serve"', "zachowane asy i DF")
need(INDEX, "model-guide.js?v=87dc1", "cache bust nowego UI")
need(INDEX, "model-guide.css?v=87dc1", "arkusz nowego UI")

for marker, label in [
    ("<table", "szeroka tabela modeli"),
    ("MACIERZ RYNKÓW", "stara nazwa macierzy"),
    ("fetch(", "pobranie sieciowe w warstwie prezentacji"),
    ("setInterval(", "polling w warstwie prezentacji"),
    ("final-raw", "lokalne przeliczenie korekty"),
]:
    forbid(UI, marker, label)

for marker, label in [
    ("min-width: 1240px", "wymuszona szerokość mobilna"),
    ("min-width: 1360px", "wymuszona szerokość desktop"),
    ("overflow-x: auto", "poziomy przewijany kontener"),
]:
    forbid(CSS, marker, label)

if errors:
    print("v8.7 Decision Center Guard: FAIL")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)

print("v8.7 Decision Center Guard: PASS")
