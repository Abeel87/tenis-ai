# Tenis AI — kanoniczna architektura

## 1. Produkcja danych

Główny workflow `update-and-pages.yml` buduje analizę i publikację w jednej kontrolowanej kolejności. Najpierw aktualizowane są dane i modele bazowe, następnie PBP/historia/settlement, AutoLearn Ensemble i Adaptive Learning, później telemetryka oraz warstwy SHADOW. Superbet jest nakładany jako osobna warstwa operatorowa, a Symfonia 2.0 pracuje wyłącznie na bieżącej, zweryfikowanej ofercie operatora.

Kontrakt przepływu:

`DANE / MODEL RAW -> uczenie i walidacja -> SYMFONIA 2.0 -> bieżąca oferta Superbet -> PLAYABLE`

Brak oferty lub linii Superbet nie może usuwać ani zastępować analizy MODEL / RAW.

## 2. Modele i uczenie

- **Current Engine** — kanoniczny silnik statystyczny w `backend/model_core.py`; nie jest przedstawiany jako samouczący ML.
- **AutoLearn** — rzeczywiste uczenie na rozliczonej historii z chronologicznym podziałem całymi meczami na TRAIN/CAL/VAL. Current/CatBoost/TabPFN/Ensemble zachowują osobne wyniki.
- **Adaptive PROD** — ograniczona meta-warstwa ucząca się z zamrożonych, rozliczonych prognoz. Nie nadpisuje RAW Ensemble.
- **Dynamic Weights** — używają poprzedniego snapshotu telemetryki i mają twarde limity przesunięć wag.
- **Early Hold / Serve / Form / Surface / Consensus** — specjalistyczne warstwy statystyczne lub agregujące; nie należy przedstawiać ich jako osobnych retrenowanych modeli ML, jeżeli nimi nie są.
- **Player / Ensemble learning / Surface Elo / Accuracy Lab / NEURO** — warstwy SHADOW pozostające odseparowane od PROD/PLAYABLE, dopóki ich własne bramki walidacyjne nie zostaną spełnione i świadomie zatwierdzone.
- **Symfonia 2.0** — supervised operator-line model z własną historią, exact-line probability i joint probability liczoną tylko na wspieranym wspólnym state-space.

## 3. Superbet i PLAYABLE

Kanoniczne backendowe wejścia operatora to:

- `backend/superbet_market_context.py`
- `backend/superbet_line_coverage.py`
- `backend/superbet_playable.py`

PLAYABLE jest warstwą fail-closed: brak zweryfikowanego operator context, brak dokładnej linii albo brak dopasowania selekcji oznacza brak PLAYABLE. Nie wolno używać najbliższej linii ani RAW jako operatorowego fallbacku.

`backend/superbet_playable.py` jest projekcją addytywną. Może dopisać osobne `superbet_playable_v912` i dedykowane warstwy historii PLAYABLE, ale nie może nadpisywać `match_win`, `first_set_win`, `over_under`, `match_over_under`, exact score, `autolearn_v84` ani źródłowych feedów SHADOW. MODEL / RAW pozostaje niezależny od tego, czy Superbet ma dany rynek lub dokładną linię.

Historia PLAYABLE przechowuje wyłącznie zamrożone selekcje operatorowo zweryfikowane. Brak score nie jest interpretowany jako `0`.

## 4. Frontend

Kanoniczne właściciele głównych ścieżek UI:

- lista i szczegół meczu: `frontend/project-ui.js`
- filtrowanie/sortowanie i zachowanie pozycji listy: `frontend/match-browser.js`
- jeden gate PLAYABLE: `frontend/playable-ui.js`
- szczegół architektury meczu: `frontend/match-detail.js`
- Symfonia 2.0: `frontend/symphony2.js`
- historia: `frontend/history-ui.js`

Top sygnały SUPERBET i główna lista muszą korzystać z tego samego zbioru widocznych meczów oraz tego samego `playableSignals()`.

Brak wartości numerycznej w UI ma być przedstawiany jako `N/D`/brak danych, a nie jako rzeczywiste zero.

## 5. Historia i settlement

`frontend/data/history.json` jest głównym źródłem rozliczonych predykcji. Prognozy są zamrażane przed startem meczu, a settlement wykorzystuje jednoznaczny, końcowy wynik. Przy niejednoznacznym dopasowaniu wynik pozostaje nierozliczony zamiast być zgadywany.

Osobne warstwy SHADOW i Symfonia 2.0 mogą mieć własne historie, ale nie wolno mieszać ich skuteczności z głównym PROD ani ze starą Symfonią.

## 6. Zasada konsolidacji

Nie tworzymy kolejnych plików/modułów `vXXX` jako łat na aktywny runtime. Naprawa trafia do jednego kanonicznego właściciela funkcji, a stara aktywna ścieżka jest usuwana po migracji i zabezpieczeniu testem.

Historyczne nazwy wersji mogą pozostać wyłącznie tam, gdzie są świadomie utrzymanym kontraktem danych, polityką albo odseparowanym eksperymentem. Nie są pretekstem do uruchamiania równoległych hotfixów.
