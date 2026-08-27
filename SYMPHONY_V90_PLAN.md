# Tenis AI — Symfonia Tenisowa v9.0

## Cel
Symfonia nie jest generatorem typów. Najpierw składa najbardziej prawdopodobne przebiegi meczu z istniejących danych i modeli, a dopiero potem mapuje je na spójne zestawy rynków.

## Kontrakt bezpieczeństwa
- nie zmienia `ensemble` ani `Adaptive final_score`;
- nie promuje automatycznie modeli SHADOW;
- PROD pozostaje źródłem prawdy;
- SHADOW jest dowodem pomocniczym i ma ograniczony wpływ na ranking scenariusza;
- joint probability jest pokazywane wyłącznie wtedy, gdy wszystkie nogi scenariusza są policzone na tym samym exact state tree;
- cała warstwa jest odwracalna i może zostać wyłączona bez naruszenia obecnego runtime.

## Pipeline
1. Evidence Adapter — zbiera istniejące sygnały PROD i odpowiadające im wyniki SHADOW.
2. Exact State/Path Engine — rozwija logiczne stany po 2/4/6 gemach, wynik seta i pełny wynik meczu.
3. Scenario Composer — beam-search wybiera spójne zestawy zdarzeń zamiast niezależnych najwyższych score.
4. Consistency Guard — blokuje kombinacje logicznie niemożliwe.
5. Fragile Leg Detector — wskazuje najsłabszy element multi i pokazuje, jak zmienia się joint po jego usunięciu.
6. Scenario Families — grupuje przebiegi m.in. `SERVE_WAR`, `BREAK_REBREAK`, `TIEBREAK_MAGNET`, `FAST_CONTROL`, `LONG_SET`, `ONE_SIDED`.
7. Market Compiler — mapuje pełny przebieg na obsługiwane rynki.
8. Settlement/Learning — kolejny etap: porównuje przewidywaną ścieżkę z prawdziwym PBP i wynikiem.

## SHADOW v8.9.x
Symfonia uwzględnia osobno:
- Player Intelligence;
- CatBoost + Player;
- Ensemble + Player Learning;
- CatBoost + Player + Surface Elo;
- Ensemble + Player + Surface Elo;
- TabPFN + Surface Elo.

SHADOW ma obecnie maksymalnie 20% udziału w pomocniczym evidence score Symfonii. Nie staje się przez to PROD i nie zmienia `final_score`.

## Stan implementacji
Branch: `feature/tennis-symphony-v90`
Draft PR: `#9`

### v9.0A — fundament — GOTOWY NA BRANCHU
- Evidence Adapter PROD/SHADOW;
- ranking zgodności i konfliktu modeli;
- Consistency Guard;
- Fragile Leg Detector;
- niezależny raport `frontend/data/symphony_v90.json`;
- osobne UI Symfonii;
- stary Generator AI przechwytywany i zastępowany wejściem do Symfonii, bez kasowania starego kodu przed testami regresji.

### v9.0B — exact state paths — IMPLEMENTOWANY
- exact game-path distribution po 2/4/6;
- wszystkie naturalne stany 2:0/1:1/0:2, 4:0/3:1/2:2/...;
- wyniki pierwszego seta 6:0..7:6;
- propagacja BO3/BO5 do wyniku meczu i łącznej liczby gemów;
- obsługa exact joint dla: game state, winner 1. seta, winner meczu, total 1. seta, total meczu, liczba setów, exact score meczu, exact score 1. seta, tie-break 1. seta;
- kompozycje po 2/3/4/5/6 zdarzeń;
- główna Symfonia + trzy kontrscenariusze;
- wyświetlanie top dokładnych ścieżek typu `1:1 → 2:2 → 3:3 → set 7:6 → mecz 2:1`.

### v9.0C — rozszerzenie rynku — NASTĘPNE
- handicap gemowy/setowy;
- dokładne mapowanie wszystkich aliasów rynków z API;
- asy / podwójne błędy / propsy serwisowe przez osobną warstwę probabilistyczną;
- dodatkowe zależności set-to-set i fatigue/momentum, jeśli dane historyczne potwierdzą wartość.

### v9.0D — uczenie całych scenariuszy — NASTĘPNE
- settlement całej ścieżki;
- calibration scenariuszy;
- trafność rodzin scenariuszy;
- analiza: gdzie Symfonia przewidziała dobry kierunek, ale zły moment breaka/rebreaka;
- ważenie warstw dopiero po odpowiedniej próbie i gate'ach.

## Runtime
`update-and-pages.yml` uruchamia Symfonię dopiero po `Shadow Signal Center v8.9.4`, więc ma dostęp zarówno do aktualnego PROD, jak i nowych modeli SHADOW. Raport jest następnie publikowany razem z pozostałymi danymi frontendu.
