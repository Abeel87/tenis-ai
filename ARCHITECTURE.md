# Tenis AI — kanoniczna architektura

> **Zasady nadrzędne:** przed zmianą kodu obowiązkowo przeczytaj `AGENTS.md`, `TENIS_AI_LOGIC_CONSTITUTION.md`, `TENIS_AI_MODEL_DATA_REGISTRY.md` oraz `TENIS_AI_EXECUTION_CHECKLIST.md`. Ten plik opisuje bieżącą architekturę techniczną. Jeżeli bieżący runtime lub poniższa mapa jest sprzeczna z konstytucją/rejestrem, nie wolno zgadywać ani tworzyć obejścia — rozjazd jest bugiem dokumentacji/architektury i musi zostać jawnie zbadany. `TENIS_AI_EXECUTION_CHECKLIST.md` określa natomiast aktywny etap, checkpoint i dokładny punkt wznowienia pracy.

## 1. Produkcja danych

Główny workflow `update-and-pages.yml` buduje analizę i publikację w jednej kontrolowanej kolejności. Najpierw aktualizowane są dane i modele bazowe, następnie PBP/historia/settlement, AutoLearn Ensemble i Adaptive Learning, później telemetryka oraz warstwy SHADOW. Superbet jest nakładany jako osobna warstwa operatorowa, a Symfonia 2.0 pracuje wyłącznie na bieżącej, zweryfikowanej ofercie operatora.

Kontrakt przepływu:

`DANE / MODEL RAW -> uczenie i walidacja -> SYMFONIA 2.0 -> bieżąca oferta Superbet -> PLAYABLE`

Brak oferty lub linii Superbet nie może usuwać ani zastępować analizy MODEL / RAW.

## 2. Modele i uczenie

- **Current Engine** — kanoniczny silnik statystyczny w `backend/model_core.py`; nie jest przedstawiany jako samouczący ML.
- **Context Engine SHADOW** — canonical evidence owner `backend/match_context_shadow.py`; strict-as-of context/provenance only, bez probability i bez PROD wiring.
- **Opponent Adjustment SHADOW** — canonical evidence owner `backend/player_dna_opponent_adjustment_audit.py`; opponent-strength i adjusted serve/return/hold/break pozostają evaluation-only.
- **Player State SHADOW** — canonical evidence owner `backend/player_dna_player_state_shadow.py`; descriptive current-state evidence oddzielone od long-term Player DNA, bez probability/runtime ownership.
- **Readiness Engine SHADOW** — canonical semantics owner `backend/readiness_engine_shadow.py`; komponuje istniejące evidence do `READY / NOT_READY / UNKNOWN` + reason codes, zachowując legacy `model_ready` read-only i bez runtime gating.
- **AutoLearn** — rzeczywiste uczenie na rozliczonej historii z chronologicznym podziałem całymi meczami na TRAIN/CAL/VAL. Current/CatBoost/TabPFN/Ensemble zachowują osobne wyniki.
- **Adaptive PROD** — ograniczona meta-warstwa ucząca się z zamrożonych, rozliczonych prognoz. Nie nadpisuje RAW Ensemble.
- **Dynamic Weights** — używają poprzedniego snapshotu telemetryki i mają twarde limity przesunięć wag.
- **Early Hold / Serve / Form / Surface / Consensus** — specjalistyczne warstwy statystyczne lub agregujące; nie należy przedstawiać ich jako osobnych retrenowanych modeli ML, jeżeli nimi nie są.
- **Player / Ensemble learning / Surface Elo / Accuracy Lab / NEURO** — warstwy SHADOW pozostające odseparowane od PROD/PLAYABLE, dopóki ich własne bramki walidacyjne nie zostaną spełnione i świadomie zatwierdzone.
- **Symfonia 2.0** — supervised operator-line model z własną historią, exact-line probability i joint probability liczoną tylko na wspieranym wspólnym state-space.

Semantyczne granice modeli, sezonów, Player DNA/Player State, opponent context, probability ownership i readiness definiuje `TENIS_AI_LOGIC_CONSTITUTION.md`. Bieżące znane problemy i plan ich napraw definiuje `TENIS_AI_MODEL_DATA_REGISTRY.md`. Aktywny etap, checklisty i punkt wznowienia definiuje `TENIS_AI_EXECUTION_CHECKLIST.md`.

## 3. Superbet i PLAYABLE

Kanoniczne backendowe wejścia operatora to:

- `backend/superbet_market_context.py`
- `backend/superbet_line_coverage.py`
- `backend/superbet_playable.py`

PLAYABLE jest warstwą fail-closed: brak zweryfikowanego operator context, brak dokładnej linii albo brak dopasowania selekcji oznacza brak PLAYABLE. Nie wolno używać najbliższej linii ani RAW jako operatorowego fallbacku.

`backend/superbet_playable.py` jest projekcją addytywną. Może dopisać osobne `superbet_playable_v912` i dedykowane warstwy historii PLAYABLE, ale nie może nadpisywać `match_win`, `first_set_win`, `over_under`, `match_over_under`, exact score, `autolearn_v84` ani źródłowych feedów SHADOW. MODEL / RAW pozostaje niezależny od tego, czy Superbet ma dany rynek lub dokładną linię.

Historia PLAYABLE przechowuje wyłącznie zamrożone selekcje operatorowo zweryfikowane. Brak score nie jest interpretowany jako `0`.

## 4. Frontend

> **UWAGA — ownership map pending LOGIC-11.** Poniższa lista pochodzi sprzed/ze starszej fazy przebudowy UI i nie może być używana jako jedyny dowód, że dany plik nadal jest faktycznym właścicielem funkcji. Przed zmianą UI należy prześledzić aktualny runtime/importy i ustalić kanonicznego właściciela. LOGIC-11 w `TENIS_AI_MODEL_DATA_REGISTRY.md` ma tę mapę zweryfikować i zaktualizować.

Historycznie wskazywani właściciele głównych ścieżek UI:

- lista i szczegół meczu: `frontend/project-ui.js`
- filtrowanie/sortowanie i zachowanie pozycji listy: `frontend/match-browser.js`
- jeden gate PLAYABLE: `frontend/playable-ui.js`
- szczegół architektury meczu: `frontend/match-detail.js`
- Symfonia 2.0: `frontend/symphony2.js`
- historia: `frontend/history-ui.js`

Top sygnały SUPERBET i główna lista muszą korzystać z tego samego zbioru widocznych meczów oraz tego samego kanonicznego PLAYABLE contract.

Brak wartości numerycznej w UI ma być przedstawiany jako `N/D`/brak danych, a nie jako rzeczywiste zero. Frontend nie może tworzyć probability, H2H, kursów ani innych danych, których backend nie dostarczył.

## 5. Historia i settlement

`frontend/data/history.json` jest głównym źródłem rozliczonych predykcji. Prognozy są zamrażane przed startem meczu, a settlement wykorzystuje jednoznaczny, końcowy wynik. Przy niejednoznacznym dopasowaniu wynik pozostaje nierozliczony zamiast być zgadywany.

Osobne warstwy SHADOW i Symfonia 2.0 mogą mieć własne historie, ale nie wolno mieszać ich skuteczności z głównym PROD ani ze starą Symfonią.

## 6. Zasada konsolidacji

Nie tworzymy kolejnych plików/modułów `vXXX` jako łat na aktywny runtime. Naprawa trafia do jednego kanonicznego właściciela funkcji, a stara aktywna ścieżka jest usuwana po migracji i zabezpieczeniu testem.

Historyczne nazwy wersji mogą pozostać wyłącznie tam, gdzie są świadomie utrzymanym kontraktem danych, polityką albo odseparowanym eksperymentem. Nie są pretekstem do uruchamiania równoległych hotfixów.

## 7. Kolejność autorytetu dokumentacji

W sprawach pracy agentów i zmiany kodu:

1. `AGENTS.md` — proces i zakazy pracy,
2. `TENIS_AI_LOGIC_CONSTITUTION.md` — znaczenie danych i niezmienne granice odpowiedzialności,
3. `TENIS_AI_MODEL_DATA_REGISTRY.md` — bieżący właściciel, status, known debt i kolejność napraw,
4. `TENIS_AI_EXECUTION_CHECKLIST.md` — aktywny etap, dowody ukończenia, `LIVE CHECKPOINT` i `NEXT EXACT ACTION`,
5. `ARCHITECTURE.md` — bieżąca mapa techniczna,
6. historyczne audyty/plany — materiał dowodowy, nie automatycznie obowiązujący runtime.

Każdy konflikt między dokumentami ma być jawnie rozwiązany w dokumentacji; nie wolno wybierać wygodniejszej wersji po cichu.
