# Tenis AI — Symfonia Tenisowa v9.0

## Cel
Symfonia nie jest generatorem typów. Najpierw składa najbardziej prawdopodobne przebiegi meczu z istniejących danych i modeli, a dopiero potem mapuje je na spójne zestawy rynków.

## Kontrakt bezpieczeństwa
- nie zmienia `ensemble` ani `Adaptive final_score`;
- nie promuje automatycznie modeli SHADOW;
- PROD pozostaje źródłem prawdy;
- SHADOW jest dowodem pomocniczym i ma ograniczony wpływ na ranking scenariusza;
- cała warstwa jest odwracalna i może zostać wyłączona bez naruszenia obecnego runtime.

## Pipeline
1. Evidence Adapter — zbiera istniejące sygnały PROD i odpowiadające im wyniki SHADOW.
2. State/Path Engine — rozwija logiczne stany po 2/4/6 gemach oraz wynik seta/meczu.
3. Scenario Composer — wybiera spójne zestawy zdarzeń zamiast niezależnych najwyższych score.
4. Consistency Guard — blokuje kombinacje logicznie niemożliwe.
5. Fragile Leg Detector — wskazuje najsłabszy element multi.
6. Scenario Families — grupuje przebiegi m.in. `SERVE_WAR`, `BREAK_REBREAK`, `FAST_CONTROL`, `LONG_SET`.
7. Market Compiler — docelowo mapuje pełny przebieg na wszystkie obsługiwane rynki.
8. Settlement/Learning — porównuje przewidywaną ścieżkę z prawdziwym PBP i wynikiem.

## SHADOW v8.9.x
Symfonia musi uwzględniać osobno:
- Player Intelligence;
- CatBoost + Player;
- Ensemble + Player Learning;
- CatBoost + Player + Surface Elo;
- Ensemble + Player + Surface Elo;
- TabPFN + Surface Elo.

Nie są one traktowane jako PROD, dopóki nie przejdą własnych gate'ów.

## Etapy
### v9.0A — fundament
- bezpieczny Evidence Adapter;
- ranking zgodności PROD/SHADOW;
- pierwsze reguły logiczne;
- Fragile Leg Detector;
- niezależny raport `symphony_v90.json`;
- UI podglądowe.

### v9.0B — pełne ścieżki seta
- exact path distribution dla po 2/4/6;
- wszystkie stany 2:0/1:1/0:2, 4:0/3:1/2:2/...;
- dokładne wyniki seta 6:0..7:6;
- joint probabilities dla dowolnej kombinacji kompatybilnych rynków.

### v9.0C — pełny mecz
- przejścia między setami;
- BO3/BO5;
- dokładny wynik meczu;
- match totals, handicapy, liczba setów;
- dodatkowe propsy serwisowe przez warstwę probabilistyczną/Monte Carlo.

### v9.0D — uczenie scenariuszy
- settlement całej ścieżki;
- calibration scenariuszy;
- mierzenie trafności rodzin scenariuszy;
- automatyczne ważenie dowodów po odpowiedniej próbie.
