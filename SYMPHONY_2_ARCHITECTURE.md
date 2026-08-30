# Symfonia 2.0 — operator-first architecture

## Cel

Symfonia 2.0 nie generuje własnych linii do PLAYABLE. Jej zadaniem jest ocenić **dokładne selekcje z aktualnej oferty Superbet** i z nich zbudować najbardziej spójne kompozycje 2–6 zdarzeń.

Stara Symfonia v9.x jest wycofywana. Jej raporty, UI, statystyki i workflow nie są źródłem Symfonii 2.0.

## Twardy podział warstw

### MODEL / RAW

- pozostaje niezależny od operatora;
- może liczyć pełne rozkłady, własne progi i własne linie diagnostyczne;
- nie jest źródłem kandydatów PLAYABLE;
- służy jako feature/evidence dla oceny realnej linii operatora.

### SUPERBET SNAPSHOT

Dla każdego fixture zapisujemy dokładny zbiór bieżących selekcji:

`fixture + market + pick + line + player/checkpoint`

Nie ma nearest-line, model-line ani catalogue/global fallback.

### TRAINING DATASET

Jednostką treningową jest konkretna historyczna selekcja operatora:

`match_features + market + pick + line + player/checkpoint + model/path features -> hit/miss`

Etykietą jest wynik zdarzenia, nie linia bukmachera. Uczymy prawdopodobieństwa trafienia **na zadanej realnej linii**.

Źródła historyczne:

- zamrożone `playable_signals_v912`;
- `playable_autolearn_signals_v912`;
- `playable_shadow_models_v912` jako evidence, nigdy jako automatyczny PROD;
- kolejne snapshoty Symfonii 2.0 będą zapisywane w osobnej warstwie `symphony2_*`.

Nie tworzymy sztucznych obserwacji dla linii, których operator nie wystawił.

## Scoring aktualnej oferty

Dla każdej aktualnej selekcji Superbet obliczamy niezależne komponenty:

1. `path_probability` — prawdopodobieństwo z jednej wspólnej dystrybucji przebiegu meczu, gdy dany rynek jest wspierany;
2. `operator_model_probability` — model uczony na historycznych realnych liniach;
3. `prod_evidence` — istniejące modele PROD ocenione dla dokładnej selekcji, jeśli dostępne;
4. `shadow_evidence` — pomocnicze, ograniczone wagą;
5. `calibration` — kalibracja per rodzina rynku / zakres linii;
6. `data_quality` i `sample_support` — jawna kara za małą próbkę lub brak danych.

Wynik końcowy `P_final` musi być kalibrowanym prawdopodobieństwem, nie prostą średnią procentów.

## Generator

Generator dostaje **wyłącznie aktualne, dokładne selekcje Superbet z P_final**.

Dla każdej kompozycji 2–6 nóg ocenia:

- joint probability z tej samej dystrybucji meczu;
- korelację i redundancję;
- konflikt logiczny;
- fragility;
- jakość danych / kalibracji;
- minimalną jakość pojedynczej nogi.

Nie wybiera zdarzeń tylko dlatego, że mają najwyższe marginalne P.

## Output

Nowe pliki runtime:

- `frontend/data/symphony2_current.json` — bieżące ocenione selekcje i kompozycje;
- `frontend/data/symphony2_stats.json` — wyłącznie statystyki Symfonii 2.0;
- `frontend/data/symphony2_history.json` — zamrożone predykcje operator-first do settlementu i nauki.

Stare `symphony_v90*.json`, stare statystyki Symfonii i stare komponenty UI nie są używane przez Symfonię 2.0.

## UI

W aplikacji istnieje jeden generator: **Symfonia 2.0**.

Ekran pokazuje:

- aktualność snapshotu Superbet;
- liczbę fixture/rynków/selekcji dostępnych do oceny;
- ocenę każdej wybranej nogi na dokładnej linii;
- joint probability kompozycji;
- źródła evidence i jakość danych;
- powód braku kompozycji, jeśli nie ma wystarczająco jakościowych realnych selekcji.

Nie pokazujemy statystyk starej Symfonii.

## Zasada bezpieczeństwa architektury

`DANE/MODELE RAW -> FEATURES/DYSTRYBUCJA -> AKTUALNA OFERTA SUPERBET -> SCORE DOKŁADNYCH SELEKCJI -> SYMFONIA 2.0 -> PLAYABLE`

Nigdy odwrotnie i nigdy przez dopasowanie własnej linii modelu do najbliższej linii operatora.
