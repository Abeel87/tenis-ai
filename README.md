# Tenis AI

Aktualny kierunek aplikacji: **v8.7 Decision Center + Adaptive PROD**.

Tenis AI analizuje mecze tenisowe, śledzi rynki meczowe i setowe, zapisuje rozliczone prognozy oraz prowadzi kontrolowaną pętlę Adaptive Learning w trybie ograniczonego PROD.

## Główne elementy

- `backend/model.py` — główna analiza meczów.
- `backend/pbp_*` — Early Hold / point-by-point.
- `backend/calibration_guard_v78d.py` — kalibracja bieżącej wersji.
- `backend/shadow_lab_v78e6.py` — odrzucone sygnały / Shadow Lab.
- `backend/specialist_learning_v79b.py` — learning-only dla Early, Serve/Return, Form, Surface i Consensus.
- `backend/adaptive_learning_v79.py` — Bayesian Online Meta-Learner i ograniczona korekta po surowym Ensemble.
- `frontend/model-guide.js` — Centrum Decyzji Meczu: Top / Wszystkie / PRO, filtry, wyszukiwarka i szczegóły modeli.
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

Adaptive Learning działa jako **kontrolowany PROD**: `COLLECTING` nie zmienia wyniku, `EARLY` może skorygować go maksymalnie o ±4 pp, a `STRONG` maksymalnie o ±8 pp. Oryginalny Ensemble pozostaje zapisany jako RAW, obok wyniku po Adaptive.

Player Intelligence oraz Accuracy Lab v8.6 pozostają w trybie **SHADOW** i nie zmieniają produkcyjnego wyniku.

Modele nie gwarantują wygranej ani zysku.
