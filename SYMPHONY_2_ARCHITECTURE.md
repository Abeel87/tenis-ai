# Symfonia 2.0 — operator-first architecture

## Cel

Symfonia 2.0 nie generuje własnych linii do PLAYABLE. Jej zadaniem jest ocenić **dokładne selekcje z aktualnej oferty Superbet** i z nich zbudować najbardziej spójne kompozycje 2–6 zdarzeń.

Stara Symfonia v9.x została usunięta z aktywnego stosu. Jej raporty, UI, statystyki, trackery i workflow nie są źródłem Symfonii 2.0.

## Twardy podział warstw

### MODEL / RAW

- pozostaje niezależny od operatora;
- może liczyć pełne rozkłady, własne progi i własne linie diagnostyczne;
- nie jest źródłem kandydatów PLAYABLE;
- jego wyniki są wyłącznie cechami/evidence przy ocenie dokładnej linii operatora.

### SUPERBET SNAPSHOT

Dla każdego fixture zapisujemy dokładny zbiór bieżących selekcji:

`fixture + market + pick + line + player/checkpoint`

Nie ma nearest-line, model-line ani catalogue/global fallback. Rynek liniowy bez `fixture_line_verified=true` nie jest kandydatem Symfonii 2.0.

### TRAINING DATASET

Jednostką treningową jest konkretna historyczna selekcja operatora:

`match_features + market + pick + exact_line + player/checkpoint + state_probability + existing_model_features -> hit/miss`

Etykietą jest wynik zdarzenia, nie linia bukmachera. Uczymy bezpośrednio `P(hit)` **na zadanej realnej linii Superbet**.

Źródła historyczne:

- zamrożone `playable_autolearn_signals_v912` jako najbogatsza warstwa cech;
- `playable_signals_v912` jako fallback;
- wynik `hit/miss` dokładnie tej samej selekcji;
- historia Symfonii 2.0 jest osobna i nie importuje trafień/pudeł starej Symfonii.

Nie tworzymy sztucznych obserwacji dla linii, których operator nie wystawił.

## Model prawdopodobieństwa

`P_final` nie jest ręczną średnią procentów.

Model CatBoost jest uczony na chronologicznym time-split. Jako cechy dostaje m.in.:

- market, pick, surface, tour, player scope;
- dokładną linię i checkpoint;
- exact-state probability, jeśli rynek jest wspierany przez wspólną dystrybucję meczu;
- istniejące Current/CatBoost/TabPFN/Adaptive/PROD evidence dla tej samej dokładnej selekcji.

Następnie:

1. kalibracja Platt jest akceptowana tylko wtedy, gdy nie pogarsza Brier score;
2. przy wystarczającej próbce stosujemy kalibrację osobno dla rodziny rynku;
3. przy małej liczbie historycznych obserwacji danej rodziny wynik jest jawnie shrinkowany w stronę 50%, zamiast udawać wysoką pewność;
4. `operator_model_probability` jest końcowym nadzorowanym `P_final`, a nie ręcznie ustawioną wagą modeli.

## Exact shared-state

Czysty moduł `symphony2_state.py` buduje wspólną dystrybucję przebiegu meczu z modelu serwisowego i dostępnych targetów setowych.

Dla rynków obsługiwanych przez tę samą dystrybucję liczymy:

- marginalne `state_probability` jako cechę modelu `P_final`;
- prawdziwe `joint_probability` kompozycji przez sumowanie masy **tych samych stanów**, które spełniają wszystkie nogi jednocześnie.

Iloczyn marginalnych prawdopodobieństw nie jest pokazywany jako joint. Jeżeli którejś nogi nie umiemy osadzić w tym samym state-space, nie dostaje ona fałszywego joint i nie wchodzi do kompozycji exact-state.

## Generator

Generator dostaje **wyłącznie aktualne, dokładne selekcje Superbet z P_final**.

Dla każdej kompozycji 2–6 nóg ocenia:

- prawdziwy joint probability z tej samej dystrybucji meczu;
- konflikt i redundancję rynku;
- najsłabszą nogę;
- jakość wsparcia historycznego;
- karę za niepotrzebną złożoność.

Nie wybiera zdarzeń tylko dlatego, że mają najwyższe marginalne P i nie stackuje kilku progów z tej samej rodziny rynku.

## Historia, settlement i statystyki

Nowe pliki runtime:

- `frontend/data/symphony2_current.json` — bieżące ocenione realne selekcje i kompozycje;
- `frontend/data/symphony2_history.json` — predykcje Symfonii 2.0 od zera;
- `frontend/data/symphony2_stats.json` — wyłącznie statystyki Symfonii 2.0.

Settlement nogi wymaga dokładnej zgodności:

`match + market + pick + line + checkpoint + player`

Inna linia nigdy nie rozlicza predykcji. Statystyki starej Symfonii nie są importowane.

## UI

W aplikacji istnieje jeden generator: **Symfonia 2.0**.

Ekran pokazuje realne linie Superbet, `P_final`, joint probability, jakość/wsparcie i powód braku kompozycji. Nie pokazujemy statystyk starej Symfonii ani nie wracamy do niej jako fallback.

## Zasada bezpieczeństwa architektury

`DANE/MODELE RAW -> FEATURES + SHARED STATE -> AKTUALNA OFERTA SUPERBET -> SUPERVISED P(HIT) DOKŁADNYCH SELEKCJI -> EXACT JOINT -> SYMFONIA 2.0 -> PLAYABLE`

Nigdy odwrotnie i nigdy przez dopasowanie własnej linii modelu do najbliższej linii operatora.
