# Tenis AI — architektura v8.0

## 1. Produkcja danych

Workflow `update-and-pages.yml` aktualizuje dane, wykonuje modele, PBP, Integrity Guard, historię, specialist learning, Shadow Lab i settlement. Następnie wylicza AutoLearn Ensemble, a dopiero po nim nakłada Adaptive Learning jako ograniczoną warstwę końcową. Ta kolejność jest częścią kontraktu systemu.

## 2. Modele

- Adaptive / model bazowy — oficjalne sygnały.
- Early Hold PBP — początek 1. seta z game-by-game, gdy dane są dostępne.
- Consensus, Early, Serve/Return, Form, Surface — dodatkowe modele śledzone learning-only.
- Calibration Guard — mierzy rzeczywistą skuteczność i nie pozwala mylić score z probability.
- Adaptive Learning — meta-warstwa Bayesowska ucząca się z rozliczonych błędów; zachowuje surowe Current/CatBoost/TabPFN/Ensemble i dopisuje osobny `final_score`.
- Player Intelligence i Accuracy Lab v8.6 — warstwy SHADOW bez wpływu na produkcyjny wynik.

## 3. Frontend

### Kanoniczne widoki v8

- Match Center: obecny `ui-v751.js` + Centrum Decyzji Meczu w `model-guide.js`.
- History / Post-Match Center: wyłącznie `clean-core-v80.js`.
- Status Adaptive: `adaptive-learning-v79.js`, wizualnie kompresowany przez Clean Core.

### Zasada konsolidacji

Pliki z historycznymi numerami wersji mogą pozostać tylko wtedy, gdy są nadal aktywną częścią runtime. Same stare instalatory, paczki i wersyjne README nie są runtime i zostały usunięte.

## 4. Historia

`history.json` jest źródłem prawdy dla rozliczonego meczu. Post-Match Center korzysta bezpośrednio z:

- `signals` — oficjalne prognozy;
- `learning_signals_v79b` — modele specjalistyczne learning-only;
- `adaptive_review_v79` — przyczyna błędu, korekta score i lekcja modelu;
- `result` — wynik końcowy i sety.

Adaptive PROD stosuje limity per komórka dowodowa: `COLLECTING = 0 pp`, `EARLY = ±4 pp`, `STRONG = ±8 pp`. Pole `ensemble` jest kontraktem RAW i nie jest nadpisywane.

Nie dopasowujemy już analizy pomeczowej do kart po indeksach DOM.

## 5. Dalsza konsolidacja

`ui-v75`, `ui-v751`, `restore-v762` i część starszych aktywnych modułów nadal tworzą most kompatybilności. Nie są usuwane w v8.0 bez migracji funkcji i testów. Kolejne wydania v8.x mogą je scalać stopniowo.
