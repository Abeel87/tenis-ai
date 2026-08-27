# Tenis AI — Symfonia Tenisowa v9.0

## Cel
Symfonia nie jest generatorem typów. Najpierw składa najbardziej prawdopodobne przebiegi meczu z istniejących danych i modeli, a dopiero potem mapuje je na spójne zestawy rynków.

## Kontrakt bezpieczeństwa
- nie zmienia `ensemble` ani `Adaptive final_score`;
- nie promuje automatycznie modeli SHADOW;
- PROD pozostaje źródłem prawdy;
- SHADOW jest dowodem pomocniczym i ma ograniczony wpływ na ranking scenariusza;
- joint probability jest pokazywane wyłącznie wtedy, gdy wszystkie nogi scenariusza są policzone na tym samym exact state tree;
- surowe prawdopodobieństwo rynku jest przechowywane oddzielnie od pomocniczej siły rankingowej;
- cała warstwa jest odwracalna i może zostać wyłączona bez naruszenia obecnego runtime.

## Pipeline
1. Evidence Adapter — zbiera istniejące sygnały PROD, pełny katalog z `results.json` i odpowiadające im wyniki SHADOW.
2. Exact State/Path Engine — rozwija logiczne stany po 2/4/6 gemach, wynik seta i pełny wynik meczu.
3. Scenario Composer — bounded beam-search wybiera spójne zestawy zdarzeń zamiast niezależnych najwyższych score.
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

SHADOW ma maksymalnie 20% udziału w pomocniczym evidence score Symfonii. Nie staje się przez to PROD i nie zmienia `final_score`.

## Stan implementacji
Branch: `feature/tennis-symphony-v90`
PR: `#9`

### v9.0A — fundament — GOTOWE
- Evidence Adapter PROD/SHADOW;
- ranking zgodności i konfliktu modeli;
- Consistency Guard;
- Fragile Leg Detector;
- niezależny raport `frontend/data/symphony_v90.json`;
- osobne UI Symfonii;
- stary Generator AI przechwytywany i zastępowany wejściem do Symfonii, bez kasowania starego kodu przed testami regresji.

### v9.0B — exact state paths — GOTOWE
- exact game-path distribution po 2/4/6;
- wszystkie naturalne stany 2:0/1:1/0:2, 4:0/3:1/2:2/...;
- wyniki pierwszego seta 6:0..7:6;
- propagacja BO3/BO5 do wyniku meczu i łącznej liczby gemów;
- exact joint dla: game state, winner 1. seta, winner meczu, total 1. seta, total meczu, liczba setów, exact score meczu, exact score 1. seta, tie-break 1. seta;
- kompozycje po 2/3/4/5/6 zdarzeń;
- główna Symfonia + trzy kontrscenariusze;
- top dokładne ścieżki typu `1:1 → 2:2 → 3:3 → set 7:6 → mecz 2:1`.

### v9.0C.3 — pełniejszy katalog i wydajność — GOTOWE NA BRANCHU
- pełny Market Evidence Adapter korzystający z danych, które Tenis AI już zapisuje;
- stany po 2/4/6;
- winner meczu oraz 1./2./3. seta;
- pełne istniejące drabinki O/U 1. seta i całego meczu;
- exact score 1. seta i całego meczu;
- liczba setów zamieniona na linie O/U;
- tie-break 1. seta wyprowadzony z rozkładu exact score;
- Serve Props: asy i podwójne błędy jako evidence-only, dopóki nie dostaną wspólnego joint modelu z przebiegiem meczu;
- dokładne BO3 joint dla winnera 2. i 3. seta tam, gdzie obecny stan końcowy jednoznacznie to rozstrzyga;
- semantyczne usuwanie duplikatów aliasów (`match_win`/`match_winner`, `state2`/`game_state` itd.);
- bounded one-pass beam: jeden przebieg dla głębokości 2–6 zamiast ponownego liczenia od zera dla każdej liczby nóg;
- UI pokazuje źródło rynku, surową wartość, coverage joint, konflikt modeli i kruchą nogę.

### Testy v9.0C
- dedykowany CI Symfonii: zielony;
- pełny Project Health całej aplikacji: zielony;
- po pierwszej wersji pełniejszego katalogu 13 testów trwało 207.29 s;
- po optymalizacji one-pass beam ten sam zestaw 13 testów trwał 44.85 s;
- po zmianach alias-dedupe wymagany jest ponowny zielony przebieg przed merge.

### Następne — v9.0C.x
- handicap gemowy i setowy;
- pełna mapa nazw/aliasów wszystkich rynków występujących u operatora/API;
- exact BO5 z zachowaniem pełnej sekwencji setów, nie tylko stanu końcowego;
- wspólny probabilistyczny model asów/DF z długością i przebiegiem meczu, aby serve props mogły wejść do prawdziwego joint probability;
- ewentualne fatigue/momentum tylko po walidacji na historii.

### v9.0D — uczenie całych scenariuszy
- settlement całej ścieżki;
- calibration scenariuszy;
- trafność rodzin scenariuszy;
- analiza: gdzie Symfonia przewidziała dobry kierunek, ale zły moment breaka/rebreaka;
- ważenie warstw dopiero po odpowiedniej próbie i gate'ach.

## Runtime
`update-and-pages.yml` uruchamia Symfonię po `Shadow Signal Center v8.9.4`, więc dostaje aktualny PROD i nowe modele SHADOW. Raport `symphony_v90.json` jest potem publikowany razem z pozostałymi danymi frontendu.
