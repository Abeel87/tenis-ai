# Tenis AI

Aktualna wersja aplikacji: **v8.0 Clean Core**.

Tenis AI analizuje mecze tenisowe, śledzi rynki meczowe i setowe, zapisuje rozliczone prognozy oraz prowadzi kontrolowaną pętlę Adaptive Learning w trybie SHADOW.

## Główne elementy

- `backend/model.py` — główna analiza meczów.
- `backend/pbp_*` — Early Hold / point-by-point.
- `backend/calibration_guard_v78d.py` — kalibracja bieżącej wersji.
- `backend/shadow_lab_v78e6.py` — odrzucone sygnały / Shadow Lab.
- `backend/specialist_learning_v79b.py` — learning-only dla Early, Serve/Return, Form, Surface i Consensus.
- `backend/adaptive_learning_v79.py` — Bayesian Online Meta-Learner i analiza błędów po meczu.
- `frontend/clean-core-v80.js` — kanoniczna Historia v8.0 i Post-Match Center.
- `frontend/ui-v751.js` — aktywny Match Center / bridge starszego UI; będzie dalej konsolidowany w kolejnych wydaniach v8.x.

## Zasada v8.0

Interfejs pokazuje mało informacji na liście i więcej dopiero po wejściu w szczegóły. Historia nie rozwija już ściany typów. Kliknięcie rozliczonego meczu otwiera pełny raport: co weszło, co nie weszło, wynik każdego modelu oraz wnioski Adaptive Learning.

## Testy

```bash
python -m pytest -q
node tests/ui_static_smoke.mjs
python scripts/project_health.py
```

## Ważne

Adaptive Learning działa w trybie **SHADOW**: uczy się i pokazuje korekty, ale nie może automatycznie zmieniać produkcyjnych typów bez odpowiedniej próbki i walidacji.

Modele nie gwarantują wygranej ani zysku.
