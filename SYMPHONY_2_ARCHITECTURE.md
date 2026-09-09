# Symfonia 2.0 — operator-first architecture

## Cel

Symfonia 2.0 nie generuje własnych linii do PLAYABLE. Jej zadaniem jest ocenić **dokładne selekcje z aktualnej oferty Superbet** i z nich zbudować najbardziej spójne kompozycje 2–6 zdarzeń.

Stara Symfonia v9.x została usunięta z aktywnego stosu. Jej raporty, UI, statystyki, trackery i workflow nie są źródłem Symfonii 2.0.

## Twardy podział warstw

## Nazewnictwo authority

`superbet_playable_v912` jest historycznie nazwaną, kompatybilną warstwą **projekcji exact-line na zweryfikowaną bieżącą ofertę Superbet**. Może służyć do filtrowania MODEL/RAW, historii i diagnostyki pokrycia, ale **nie jest `P_final` Symfonii 2.0 i nie jest authority finalnych kompozycji PLAYABLE**.

Authority końcowej rekomendacji jest jednoznaczne:

`AKTUALNA OFERTA SUPERBET -> SUPERVISED P(HIT) -> EXACT JOINT -> SYMFONIA 2.0 -> PLAYABLE`.

UI nie może prezentować score z `superbet_playable_v912` jako supervised `P_final` Symfonii. Nazwa pliku/API pozostaje dla kompatybilności; semantyka użytkowa to **zweryfikowana oferta / projekcja exact-line**.

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
3. mała próbka nie zniekształca supervised probability: raportujemy niższe `learning_reliability`, a rodzina z zerowym supportem jest `N/D` / unscored zamiast dostawać sztuczne 50%;
4. `operator_model_probability` jest końcowym nadzorowanym `P_final`, a nie ręcznie ustawioną wagą modeli.

## Exact shared-state

Czysty moduł `symphony2_state.py` buduje wspólną dystrybucję przebiegu meczu z modelu serwisowego i dostępnych targetów setowych.

Dla rynków obsługiwanych przez tę samą dystrybucję liczymy:

- marginalne `state_probability` jako cechę modelu `P_final`;
- prawdziwe `joint_probability` kompozycji przez sumowanie masy **tych samych stanów**, które spełniają wszystkie nogi jednocześnie.

Iloczyn marginalnych prawdopodobieństw nie jest pokazywany jako joint. Jeżeli którejś nogi nie umiemy osadzić w tym samym state-space, nie dostaje ona fałszywego joint i nie wchodzi do kompozycji exact-state.

### Phase 9 — Player DNA whole-match shared state (SHADOW)

Player DNA udostępnia dodatkowy, kanoniczny whole-match sufficient state z
`player_dna_tennis_simulator.py`. Ten state zachowuje wspólnie set 1, set 2,
wynik meczu, liczbę setów, P1/P2 total games, total games i set-to-nil przy
legalnym serve order.

Na obecnym etapie jest to **SHADOW integration only**:

- może liczyć exact joint między rodzinami set1 / set2 / match;
- joint pochodzi z sumy jednej wspólnej dystrybucji Player DNA;
- nie jest używany jako iloczyn marginalnych P;
- nie zastępuje dotychczasowego runtime `joint_probability`;
- nie zmienia supervised `P_final`;
- nie zmienia rankingu kompozycji ani `recommended_leg_count`;
- nie wpływa na PLAYABLE.

Symfonia może publikować ten wynik jako diagnostykę i porównanie zależności,
ale jego ewentualna promocja do rankingu podlega osobnej polityce
OFFLINE -> SHADOW -> AUDYT -> CANARY -> PROD.

### Phase 10 — Bet Builder dependency diagnostics (SHADOW)

Na Phase-9 Player DNA whole-match shared state działa dodatkowa warstwa
diagnostyczna zależności Bet Builder. Nie jest to nowy generator i nie zmienia
obecnego rankingu.

Dla wspieranej kombinacji liczymy z tej samej exact state distribution:

- exact joint probability;
- conditional contribution każdej nogi;
- continuous redundancy score;
- continuous conflict score;
- weakest-leg impact na joint mass;
- marginal information gain;
- exact containment / exact conflict bez arbitralnego thresholdingu.

`redundancy_score = exact_pair_joint / min(pair_marginals)`.
Wartość 1 oznacza matematyczne zawieranie się jednego zdarzenia w drugim.
`conflict_score = 1 - redundancy_score`; wartość 1 oznacza zero wspólnej
masy stanów.

Te diagnostyki mają:
`ranking_influence=false`,
`operator_model_probability_influence=false`,
`recommended_leg_count_influence=false`,
`playable_influence=false`.

Nie mamy obecnie wiarygodnego historycznego zbioru exact Bet Builder
price-delta observations. Operator-price experiment jest więc jawnie
`NOT_AVAILABLE` i nie używa kursu bukmachera jako etykiety prawdy, targetu
treningowego ani sygnału rankingowego.

## Phase 14 — bezpieczny lifecycle promocji warstw SHADOW

Player DNA, simulator, Neuro oraz Player-DNA shared state z Faz 9–10 podlegają
jednemu kanonicznemu lifecycle:

`OFFLINE -> SHADOW -> AUDYT -> CANARY -> PROD`

Authority polityki:

`backend/player_dna_phase14_lifecycle.py`

Faza 14 **nie zmienia** bieżącego rankingu Symfonii 2.0, supervised
`P_final`, `recommended_leg_count` ani PLAYABLE. Może jedynie stwierdzić,
że konkretny lane ma komplet dowodów do **ręcznego bounded-canary review**.

`manual_canary_review_eligible=true` nie oznacza aktywnego CANARY.
Włączenie CANARY wymaga osobnej jawnej zmiany, bounded planu, fingerprintu
kandydata i rollbacku. PROD wymaga dodatkowo osobnych wyników z faktycznego
CANARY oraz ręcznej akceptacji.

Dla shared-state z Faz 9–10 techniczne zamknięcie diagnostyki nie jest
promocją. Do czasu osobnego out-of-sample ranking-impact/canary gate pozostaje:

- `ranking_influence=false`;
- `operator_model_probability_influence=false`;
- `recommended_leg_count_influence=false`;
- `playable_influence=false`.

Stary `shadow_promotion_gate_v942.py` nie jest authority tego lifecycle.
Nowe `vXXX` nie są tworzone.

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

<!-- CI revalidation: force fresh PR checks after legacy Symphony cleanup -->
