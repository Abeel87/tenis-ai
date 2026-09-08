# Tenis AI — Match Simulation Master Plan

## Status

**KANONICZNY PLAN ROZWOJU** dla warstwy profil zawodnika -> matchup -> point-by-point -> symulacja meczu -> shared state -> Symfonia 2.0.

Ten dokument jest jedynym punktem odniesienia dla tego kierunku. Nie tworzymy kolejnych planów `vXXX`, równoległych generatorów ani łatek nadpisujących tę architekturę. Każda przyszła rozmowa, audyt, branch i PR dotyczące Tenis AI w tym obszarze powinny zaczynać się od przeczytania tego pliku oraz aktualnego `SYMPHONY_2_ARCHITECTURE.md` na `main`.

## Nienaruszalne zasady

1. **Nie psujemy Symfonii 2.0.** Obecna architektura operator-first zostaje: RAW/MODELE -> FEATURES + SHARED STATE -> aktualna oferta Superbet -> P(hit) dokładnej selekcji -> EXACT JOINT -> Symfonia 2.0 -> PLAYABLE.
2. **Nowy silnik nie wybiera linii Superbet.** Produkuje lepszy wspólny rozkład meczu i cechy matchupowe; dopiero później Symfonia ocenia dokładne bieżące linie operatora.
3. **Nie tworzymy następnej Symfonii 3.0 ani kolejnych `vXXX` jako łat.** Nowe elementy mają wejść do jednego kanonicznego pipeline'u.
4. **Najpierw audyt i testy, potem kod.** Każdy etap ma własne kryteria wejścia/wyjścia.
5. **Brak look-ahead leakage.** W backtestach dla meczu wolno używać wyłącznie danych dostępnych przed jego startem.
6. **Mała próbka nie udaje pewności.** Używamy shrinkage/partial pooling, quality flag i uncertainty.
7. **Point-by-point jest źródłem prawdy dla dynamiki meczu, jeśli dane są kompletne.** Dane zagregowane są warstwą diagnostyczną/UI, nie substytutem pełnego profilu.
8. **Joint probability pochodzi ze wspólnej dystrybucji stanów/symulacji, nigdy z mnożenia marginalnych P.**
9. **Model musi być skalibrowany, nie tylko trafny.** Obowiązkowo Brier, log-loss, reliability/calibration, coverage i walk-forward.
10. **Sieć neuronowa pozostaje SHADOW dopóki nie pokona prostszych baseline'ów w walidacji out-of-sample.**

---

# Docelowa architektura

`HISTORIA + POINT-BY-POINT API`

-> `PLAYER DNA FEATURE STORE`

-> `OPPONENT / COMMON-OPPONENT ADJUSTMENT`

-> `MATCHUP ENGINE`

-> `POINT PROBABILITY ENGINE`

-> `GAME / SET / MATCH STATE ENGINE`

-> `EXACT DP / MARKOV + MONTE CARLO`

-> `MATCH DISTRIBUTION / SHARED STATE`

-> `SYMPHONY 2.0 STATE FEATURES`

-> `AKTUALNA OFERTA SUPERBET`

-> `SUPERVISED P(HIT) DOKŁADNEJ LINII`

-> `EXACT JOINT`

-> `SYMFONIA 2.0 / PLAYABLE`

---

# Faza 0 — Freeze i pełny audyt aktualnego main

## Cel

Zrozumieć, co już mamy i czego naprawdę brakuje, zanim powstanie jakikolwiek nowy model.

## Sprawdzić

- źródła point-by-point i ich kompletność;
- schemat danych historycznych;
- identyfikację zawodnika i deduplikację;
- nawierzchnię, tour, format BO3/BO5, datę, ranking;
- L5/L10/L20 i sposób ich wyliczania;
- hold, return, first-serve, second-serve, ace, DF, BP, tie-break, set profile;
- Player Intelligence / profile zawodników;
- obecne modele RAW;
- Neuro SHADOW;
- `symphony2_state.py` i bieżące shared state;
- sposób tworzenia `state_probability` i `joint_probability`;
- dane tracone podczas agregacji;
- które rynki Superbet można już rozliczać z jednego wspólnego rozkładu.

## Wynik

Tabela:

`CECHA | MAMY SUROWE | MAMY AGREGAT | JAKOŚĆ | BRAKUJE | MOŻNA WYLICZYĆ Z PBP | UŻYWANA PRZEZ SYMFONIĘ?`

## Gate

Brak kodu produkcyjnego, dopóki audyt nie odpowie na powyższe punkty.

---

# Faza 1 — Player DNA Feature Store

## Cel

Każdy zawodnik ma własny dynamiczny profil, a nie tylko kilka uśrednionych wskaźników.

## Minimalny profil

### Serwis

- service points won;
- 1st serve in;
- 1st serve points won;
- 2nd serve points won;
- ace rate na 100 service points / service games;
- double-fault rate;
- unreturned serve rate, jeśli źródło pozwala;
- hold rate;
- BP save;
- deuce/30:30 performance;
- serving for set / match;
- pierwszy gem serwisowy;
- 1./2./3. gem serwisowy seta.

### Return

- return points won;
- 1st serve return points won;
- 2nd serve return points won;
- break rate;
- BP conversion;
- return przy 30:30/deuce/BP;
- pierwszy return game;
- early return pressure.

### Set / match profile

- P(wygrania 1. seta);
- P(wygrania meczu po wygranym 1. secie);
- comeback po przegranym 1. secie;
- P(set do zera / przeciw setowi do zera);
- liczba gemów na set/mecz;
- rozkład 6:0..7:6;
- tie-break reach/win;
- liczba setów;
- early score 1:1 / 2:2 / 3:3;
- prowadzenie po 4/6 gemach.

### Trend i kontekst

Dla kluczowych cech przechowujemy:

- L5;
- L10;
- L20;
- dłuższe okno bazowe;
- trend L5 vs L10/L20;
- ta sama nawierzchnia;
- przeciwnicy o podobnym poziomie;
- sample size;
- uncertainty / quality.

## Gate

Profil zawodnika musi być możliwy do odtworzenia wyłącznie z danych sprzed wskazanego meczu.

---

# Faza 2 — Opponent adjustment / common-opponent strength

## Cel

Odpowiedzieć na pytanie: **przeciwko komu zawodnik zrobił te statystyki?**

## Mechanizm

Każda główna cecha jest korygowana względem jakości przeciwników, np.:

- hold zawodnika vs return strength przeciwników;
- ace rate vs return/contact profile przeciwników;
- break rate vs service strength przeciwników;
- 1st-set win vs poziom i typ przeciwnika;
- tie-break rate vs mocni serwujący / mocni returnerzy.

Wprowadzić:

- common-opponent adjustment;
- opponent-strength buckets;
- surface-specific adjustment;
- recency weighting;
- shrinkage przy małej próbce.

## Gate

Backtest musi pokazać, że opponent-adjusted feature poprawia out-of-sample Brier/log-loss względem surowej średniej. Jeśli nie — nie promujemy go tylko dlatego, że brzmi sensownie.

---

# Faza 3 — Matchup Engine

## Cel

Zbudować profil **konkretnego pojedynku**, nie dwóch osobnych zawodników.

Przykładowe interakcje:

- serve A <-> return B;
- 1st serve A <-> 1st return B;
- 2nd serve A <-> 2nd return B;
- ace tendency A <-> contact/return B;
- DF A <-> return pressure B;
- BP save A <-> BP conversion B;
- early hold A <-> early return B;
- TB A <-> TB B;
- after-break A <-> response B;
- first-set A <-> first-set B;
- stamina / long-match profile w BO5.

Wynik Matchup Engine ma zawierać bazowe prawdopodobieństwa punktowe i korekty kontekstowe z uncertainty.

## Stan realizacji / gate zamknięcia

Faza 3 jest uznana za domkniętą tylko wtedy, gdy CI wygeneruje
`frontend/data/player_dna_phase3_matchup_engine.json` z
`phase3_complete=true` i `phase4_ready=true`.

Kanoniczny builder to `backend/player_dna_matchup_engine.py`. Bieżący
`player_dna_current_shadow.py` pobiera z niego dokładnie ten sam pre-match
feature vector, więc konsolidacja nie może zmienić istniejących predykcji.

Aktualny zatwierdzony rdzeń Matchup Engine to osobne main effects:
serve/return overall + same-surface oraz ich raw support. Nie składamy na siłę
pełnego kompozytu z rodzin, które nie przeszły robust walk-forward. Nonlinear
serve-return, opponent-strength, pressure, TB, recent form, comeback i BO5
stamina pozostają nieaktywne. Small-sample shrinkage ma historyczny sygnał, ale
pozostaje zablokowany do świeżego confirmation gate.

Domknięcie Fazy 3 nie oznacza promocji do PROD, Symfonii ani PLAYABLE. Oznacza,
że Faza 4 może startować z jednym kanonicznym pre-match matchup contract i
zwalidowanym lean point-state baseline.

---

# Faza 4 — Point Probability Engine

## Baseline najpierw

Najpierw budujemy interpretowalny baseline:

- logistic/Bayesian hierarchical model;
- crossed server/returner effects;
- surface;
- recency;
- opponent adjustment;
- score-state tylko tam, gdzie dane potwierdzają efekt.

Dopiero potem porównujemy:

- CatBoost;
- istniejące modele;
- Neuro / NN SHADOW.

## Zasada

Nie zakładamy automatycznie „momentum”, presji czy zmęczenia. Efekt musi zostać potwierdzony historycznie i poprawiać walidację.

## Wyjście

`P(server wins next point | server, returner, surface, score_state, set_state, form, uncertainty)`

## Stan realizacji / gate zamknięcia

Kanoniczny baseline Fazy 4 to `backend/player_dna_point_probability_engine.py`.
Nie powstaje drugi równoległy scorer. Moduł konsoliduje już zwalidowany lean
logistic baseline i jest używany przez SHADOW dynamic backtest/current-card path.

Aktywny zestaw wejść SHADOW:

- Phase-3 serve/return main effects overall + same-surface;
- provider rank context;
- pre-point lean score state: point pressure + set/match state.

Świadomie wyłączone do osobnych gate'ów pozostają: tiebreak state, prior
momentum, recent form L5, opponent adjustment, nonlinear matchup, pressure/TB
profile interactions, comeback, BO5 stamina, first/second split scoring i NN.

Faza 4 jest zamknięta dopiero, gdy CI potwierdzi:

- dodatni holdout na Brier + match-equal Brier + log-loss;
- dodatnie 3/3 expanding walk-forward;
- lean state lepszy od pełnego stateful w 3/3 foldów;
- wyłącznie score-before, bez score-after/current-point leakage;
- dokładny feature contract;
- `phase4_complete=true` i `phase5_ready=true`.

Uncertainty nie dostaje arbitralnego confidence score. Publikujemy raw support i
flagi progów diagnostycznych. Historyczny small-sample shrinkage pozostaje OFF
do świeżego confirmation gate.

Domknięcie Fazy 4 nadal nie oznacza PROD/Symfonia/PLAYABLE.

---

# Faza 5 — Game / Set / Match Engine

## Cel

Z pojedynczego P punktu budujemy legalny tenisowy state machine:

- point;
- deuce/advantage;
- game;
- tie-break;
- set;
- BO3 / BO5 match;
- poprawna kolejność serwowania.

Testy muszą obejmować skrajne stany i brak stanów niemożliwych.

## Stan realizacji / gate zamknięcia

Kanoniczny moduł Fazy 5 to `backend/player_dna_tennis_state_engine.py`.
Jest probability-free: bierze legalny stan przed punktem + zwycięzcę jednego
punktu i zwraca dokładnie jeden legalny kolejny stan.

Kontrakt obejmuje:

- standardowe game z deuce/advantage;
- tie-break przy 6:6, pierwszy do 7 z przewagą 2;
- oficjalną kolejność serwowania w tie-breaku: 1 punkt + bloki po 2;
- ciągłość serwowania między game'ami i setami;
- BO3 / BO5 i terminalność meczu;
- jawne completed set scores;
- fail-closed dla stanów niemożliwych.

`player_dna_tennis_simulator.py` współdzieli z tym modułem kanoniczne
predykaty legalności seta / 6:6 oraz rotację zawodnika, więc nie utrzymujemy
drugiej równoległej definicji tych reguł.

Faza 5 zamyka się wyłącznie gdy CI potwierdzi skrajne stany, serve-order,
extended tie-break, BO3/BO5 terminality, brak nielegalnych set scores w exact DP
oraz `phase5_complete=true`, `phase6_ready=true`.

Domknięcie Fazy 5 nie oznacza PROD/Symfonia/PLAYABLE.

---

# Faza 6 — Exact DP / Markov + Monte Carlo

## Zasada

Nie symulujemy losowo tego, co możemy policzyć dokładnie.

- proste stany -> dynamic programming / Markov;
- dynamiczne efekty zależne od historii -> Monte Carlo;
- porównujemy oba podejścia na stałych P, aby symulator nie miał błędu implementacyjnego.

## Skala startowa

- test: 10k symulacji/mecz;
- shadow: 50k;
- docelowo 100k+, jeśli stabilność i koszt na to pozwalają.

## Wyjście

Jedna wspólna dystrybucja scenariuszy meczu, z której liczymy:

- winner;
- set winner;
- exact sets;
- total games;
- set games;
- handicapy;
- 1:1 / 2:2 / 3:3;
- prowadzenie po 4/6;
- tie-break;
- clean set;
- dokładnie 1 wygrany set;
- dowolne wspierane kombinacje.

## Stan realizacji / gate zamknięcia

Faza 6 rozwija istniejący kanoniczny
`backend/player_dna_tennis_simulator.py`; nie powstaje drugi symulator.

Dla stałych prawdopodobieństw punktowych exact DP pozostaje preferowanym
źródłem prawdy. Monte Carlo jest niezależnym obliczeniowo cross-checkiem na tym
samym kontrakcie: używa tej samej transformacji point -> hold, tej samej
neutralnej polityki tie-breaku, tej samej kolejności serwowania oraz
kanonicznych predykatów legalności Fazy 5.

Gate porównuje DP i Monte Carlo na czterech scenariuszach BO3/BO5 przy
`10_000` symulacji na scenariusz. Sprawdzane są m.in. winner, first-set
winner, tie-break, over 10.5, 1:1/2:2/3:3 oraz rozkłady exact score.
Dodatkowo wymagamy pełnego zachowania masy prawdopodobieństwa i
deterministycznego replay przy stałym seedzie.

Raport CI:
`frontend/data/player_dna_phase6_exact_dp_monte_carlo.json`.

Skala pozostaje zgodna z planem: `10k` dla gate/test, `50k` jako target
SHADOW i `100k+` dopiero gdy koszt/runtime na to pozwala. History-dependent
Monte Carlo nie jest jeszcze aktywowane tylko dlatego, że mechanizm MC istnieje.

Faza 6 zamyka się wyłącznie gdy CI ustawi
`phase6_complete=true` i `phase7_ready=true`. Nie oznacza to żadnej
promocji do PROD, Symfonii 2.0 ani PLAYABLE.

---

# Faza 7 — Kalibracja i walk-forward backtest

## Obowiązkowe metryki

- Brier score;
- log-loss;
- calibration curve / reliability;
- ECE lub analogiczny błąd kalibracji;
- accuracy tylko pomocniczo;
- coverage;
- sample size per market/family;
- wyniki per surface / tour / BO3/BO5;
- wyniki per confidence bucket.

## Walk-forward

Dla każdego historycznego meczu:

1. odcinamy dane na moment przed startem;
2. budujemy Player DNA;
3. budujemy matchup;
4. generujemy rozkład;
5. zapisujemy predykcje;
6. dopiero po meczu settlement;
7. przechodzimy do kolejnego okresu.

Zakaz losowego train/test split dla danych czasowych jako głównej walidacji.

## Gate

Przykład kryterium promocji:

- brak pogorszenia Brier/log-loss vs obecny shared state;
- wyraźnie lepsza kalibracja w głównych rodzinach rynku;
- brak regresji w stabilności i coverage;
- wyniki potwierdzone na kilku kolejnych oknach czasowych.

## Stan realizacji / gate zamknięcia

Faza 7 rozwija kanoniczne `player_dna_market_backtest.py` oraz
`player_dna_market_walk_forward.py`; nie powstaje równoległy backtester.

Walidacja raportuje dla każdego binarnego rynku osobno:

- absolutne Brier i log-loss dla reference oraz dynamic lean candidate;
- reliability/calibration bins i ECE;
- coverage względem wszystkich settled labels dostępnych dla reference;
- sample size i stałe confidence buckets;
- istniejące diagnostyki tour / surface / tour+surface;
- osobne diagnostyki formatu BO3 i BO5, również gdy próbka któregoś formatu
  jest jeszcze niewystarczająca.

Walk-forward nadal używa tych samych trzech expanding chronological folds,
tych samych progów supportu i nigdy nie dzieli meczów o tym samym timestampie.
Dodanie metryk Fazy 7 nie obniża ani nie retunuje istniejących progów.

Raport CI zamknięcia:
`frontend/data/player_dna_phase7_calibration_walk_forward.json`.

**Zamknięcie Fazy 7 oznacza kompletność infrastruktury walidacyjnej, nie
promocję modelu.** Raport rozdziela `phase7_complete/phase8_ready` od
`promotion_evidence_sufficient`. Jeżeli istniejący walk-forward ma za mało
wspartych foldów albo mieszany wynik, werdykt pozostaje
`EVIDENCE_INSUFFICIENT_NO_PROMOTION`.

Niezależnie od jakości historycznego wyniku ten gate nie może sam aktywować
PROD, Symfonii 2.0 ani PLAYABLE. Promocja pozostaje osobnym procesem z Fazy 14.

---

# Faza 8 — Neuro / NN jako challenger, nie król z automatu

## Cel

Sprawdzić, czy sieć neuronowa rzeczywiście dodaje sygnał ponad dobrze zbudowany baseline.

Porównanie na identycznym walk-forward:

- hierarchical/logistic baseline;
- CatBoost;
- NN;
- ensemble.

NN awansuje z SHADOW tylko wtedy, gdy poprawia kalibrację i log-loss/Brier out-of-sample. Jeśli nie — pozostaje challengerem.

## Stan realizacji / gate zamknięcia

Faza 8 rozwija istniejący kanoniczny `backend/neuro_shadow_training.py` oraz
korzysta z deterministycznej sieci z `backend/neuro_shadow_neural.py`.
Nie powstaje drugi trener ani nowy równoległy pipeline NEURO.

Porównanie model classes używa jednego wspólnego kontraktu danych i identycznych
okien czasowych:

- interpretowalny logistic baseline;
- CatBoost;
- obecny mały deterministyczny NN;
- nietunowany equal-weight ensemble logistic + CatBoost + NN.

Wszystkie trzy trenowane klasy dostają dokładnie ten sam feature vector, te same
rekordy train/evaluation i match-balanced weights. Istniejące
`catboost_probability` i `tabpfn_probability` są świadomie wyłączone z
wektora Fazy 8, aby challenger nie oceniał własnej wcześniejszej predykcji lub
innego modelu zamiast porównania klas na tych samych wejściach.

Feature snapshot nie może zawierać final result ani bookmaker price. Settlement
jest używany wyłącznie jako target po meczu. Braki prawdopodobieństw dostają
neutralne 0.5 wraz z jawnym missing-mask.

Walk-forward ma trzy expanding train windows 55/70/85%, rozłączne przyszłe
okna testowe, whole-match grouping i zakaz dzielenia tego samego timestampu.
Hyperparametry są zamrożone przed ewaluacją, a ensemble ma stałe wagi 1/3 i nie
jest dostrajany na holdoucie.

Każdy rynek osobno raportuje Brier, log-loss, ECE/calibration i pomocniczą
accuracy dla logistic/CatBoost/NN/ensemble na dokładnie tych samych rekordach.
NN może zostać oznaczony tylko jako **per-market review candidate**, jeśli
powtarzalnie i agregatowo pokonuje logistic oraz CatBoost na Brier/log-loss i
jednocześnie ma lepszy ECE. To nadal nie aktywuje runtime.

Raport CI:
`frontend/data/neuro_shadow_phase8_challenger_walk_forward.json`.

Faza 8 zamyka techniczną ocenę model classes, gdy co najmniej 6 rynków ma pełne
3/3 foldy na wspólnym kontrakcie. `phase8_complete=true / phase9_ready=true`
nie oznacza promocji NN ani ensemble. Globalna promocja jest zawsze zabroniona
w tym gate i pozostaje osobnym procesem Fazy 14.

---

# Faza 9 — Integracja z Symfonią 2.0

## Bez zmiany operator-first

Nowy engine zasila `shared state` i cechy wejściowe Symfonii.

Symfonia nadal:

1. pobiera **aktualne dokładne selekcje Superbet**;
2. ocenia P(hit) dla exact line;
3. wykorzystuje state probability z nowej dystrybucji;
4. joint liczy na tych samych wspólnych stanach/symulacjach;
5. odrzuca konflikt/redundancję;
6. buduje PLAYABLE.

Nie dopasowujemy model-line do nearest Superbet line.

## Stan realizacji / gate zamknięcia

Faza 9 nie zmienia operator-first ani obecnego runtime rankingu Symfonii 2.0.
Kanoniczny `backend/player_dna_tennis_simulator.py` publikuje teraz exact
whole-match sufficient state przez `shared_match_state_outcomes()`.

Wspólny stan:

- zachowuje dokładny set 1 i set 2;
- zachowuje wynik meczu, liczbę setów, P1/P2 total games i total games;
- zachowuje set-to-nil;
- respektuje legalny Phase-5 serve order między setami;
- dla pre-match używa jawnej neutralnej mieszaniny 50/50 pierwszego serwującego;
- ma pełną masę prawdopodobieństwa równą 1.

`backend/symphony2_state.py` wystawia osobne Phase-9 SHADOW API:

- `build_player_dna_shared_outcomes`;
- `player_dna_marginal_probability`;
- `player_dna_joint_probability`.

Dzięki temu set1 + set2 + match mogą być liczone z **jednego tego samego state-space**.
Cross-family joint jest sumą masy wspólnych stanów spełniających wszystkie nogi,
nigdy iloczynem marginalnych P.

Istniejące `joint_probability()` pozostaje bez zmian i nadal fail-closed zwraca
brak joint dla cross-family, dopóki Phase-9 state nie przejdzie późniejszej
polityki promocji. To świadomie chroni aktualny ranking.

`backend/symphony2_engine.py` pokazuje Phase-9 state wyłącznie jako SHADOW
diagnostykę:

- `player_dna_shared_state_probability_shadow` per dokładna selekcja;
- exact cross-family pair joint z jednego Player DNA state-space;
- jawne porównanie exact joint vs independence product;
- `ranking_influence=false`;
- `operator_model_probability_influence=false`;
- `recommended_leg_count_influence=false`;
- brak wpływu na PROD i PLAYABLE.

Raport CI:
`frontend/data/symphony2_phase9_player_dna_shared_state.json`.

Faza 9 zamyka się dopiero, gdy CI potwierdzi:

- Phase 8 jako prerequisite;
- normalizację shared state;
- exact cross-family joint dla set1 + set2 + match;
- różnicę joint vs independence product;
- niezmienione fail-closed zachowanie obecnego runtime;
- brak wpływu na `P_final`, ranking i PLAYABLE;
- `phase9_complete=true / phase10_ready=true`.

---

# Faza 10 — Bet Builder correlation / redundancy

## Cel

Wspólna dystrybucja ma identyfikować nogi, które są niemal tym samym zdarzeniem.

Dla kombinacji liczymy:

- exact joint P;
- conditional contribution każdej nogi;
- redundancy score;
- conflict score;
- weakest-leg impact;
- marginal information gain.

Dodatkowy eksperyment SHADOW: jeśli mamy obserwacje zmiany kursu Bet Builder przy dokładaniu nóg, porównać reakcję operatora z naszą zależnością. Nie używać kursu operatora jako etykiety prawdy o wyniku.

## Stan realizacji / gate zamknięcia

Faza 10 rozwija istniejący kanoniczny `backend/symphony2_engine.py`.
Nie powstaje osobny generator Bet Builder ani nowa Symfonia.

Diagnostyka zależności używa wyłącznie Phase-9 Player DNA whole-match shared
state. Dla dowolnej wspieranej kombinacji 2+ nóg raportuje:

- exact joint P z jednej wspólnej dystrybucji;
- `P(leg | wszystkie pozostałe nogi)` jako conditional contribution;
- continuous redundancy score = exact pair joint / mniejszy marginal;
- continuous conflict score = 1 - redundancy score;
- weakest-state-leg oraz jego wpływ na usuwaną joint mass;
- marginal information gain `-log(P(leg | pozostałe nogi))`;
- exact containment i exact conflict jako własności matematyczne, bez ręcznych progów.

Żaden z tych score'ów nie zmienia obecnego `_best_compositions()`, utility,
`P_final`, rankingu ani `recommended_leg_count`. Phase-10 output pozostaje
SHADOW i jest publikowany jako diagnostyka bieżącej dokładnej oferty Superbet.

Nie znaleziono wiarygodnego historycznego zbioru obserwacji zmian kursu Bet
Builder przy dokładaniu nóg. Eksperyment operator-price ma więc jawny status
`NOT_AVAILABLE_NO_OBSERVED_BUILDER_PRICE_DELTAS`. Nie tworzymy syntetycznych
kursów ani nie używamy kursu operatora jako targetu, etykiety prawdy lub sygnału
rankingowego.

Raport CI:
`frontend/data/symphony2_phase10_bet_builder_dependency.json`.

Faza 10 zamyka się dopiero, gdy CI potwierdzi:

- Phase 9 jako prerequisite;
- kompletną diagnostykę exact joint/conditional/redundancy/conflict/weakest-leg/information gain;
- przypadek matematycznej redundancji o score 1;
- przypadek matematycznego konfliktu o conflict score 1;
- różnicę exact joint od independence product;
- brak arbitralnych progów klasyfikacyjnych;
- brak wpływu na `P_final`, ranking, `recommended_leg_count`, PROD i PLAYABLE;
- `phase10_complete=true / phase11_ready=true`.

---

# Faza 11 — UI diagnostyczne

Obecne pola typu `hold 84.9%`, `return 38.2%`, `forma 62` zostają jako skrót, ale użytkownik musi móc rozwinąć profil.

Plan UI:

- L5/L10/L20;
- trend;
- sample;
- surface;
- opponent-adjusted value;
- raw value;
- matchup-adjusted value;
- uncertainty;
- „dlaczego” dla najważniejszych przewag;
- top scenariusze meczu;
- rozkład wyników seta/meczu;
- prawdopodobieństwo rynków z tej samej dystrybucji.

## Stan realizacji / gate zamknięcia

Faza 11 nie tworzy nowej matematyki Player DNA. UI odczytuje istniejący
`player_intelligence_v85` oraz istniejącą trajektorię
`player_dna_current_simulation`.

Warstwa prezentacji ma dwa poziomy:

- **Prosty** — domyślny dla każdego konta; pokazuje wniosek, trend, próbkę,
  nawierzchnię, jakość danych, najważniejsze przewagi oraz scenariusze w
  normalnym języku;
- **Techniczny** — dostępny wyłącznie dla roli `admin`; pokazuje dodatkowo
  RAW, adjusted, volatility, coverage, n, dokładne matchup edges oraz techniczne
  oznaczenia SHADOW.

Istniejący kontrakt ról pozostaje jeden:
`admin / moderator / user`.
Moderator i user nie mogą przełączyć aplikacji na tryb techniczny. Wylogowanie
lub brak potwierdzonej roli zawsze sprowadza widok do prostego.

Techniczny profil pokazuje bez nowych obliczeń:

- `raw` z historycznego okna;
- `adjusted` z backendu = recency weighting + siła przeciwników + shrinkage
  do priory nawierzchni;
- `volatility`, `n`, `coverage` i quality jako jawny evidence uncertainty;
- matchup edge osobno dla overall, serve↔return, return↔serve i form;
- trend L5 vs poprzednie 5 z backendu.

UI nie produkuje własnego confidence score ani własnego probability model.
Scenariusze nadal pochodzą z tej samej symulacji Player DNA i zachowują
prawdopodobieństwo oraz warunek pierwszego serwującego.

Gate Fazy 11 jest statyczno-regresyjny w
`tests/test_phase11_readable_ui.py` i pełnym `Tenis AI UI & Project Health`.
Zamknięcie wymaga:

- domyślnego trybu prostego;
- admin-only przełącznika Prosty ↔ Techniczny;
- braku technicznego przełącznika dla moderator/user;
- trendu, L5/L10/L20, sample, surface, reasons;
- RAW → adjusted → matchup diagnostics w trybie technicznym;
- uncertainty opartego wyłącznie o opublikowane volatility/sample/coverage;
- top scenariuszy i checkpointów 2/4/6 gemów z istniejącej trajektorii;
- braku wpływu UI na modele, Symfonię 2.0 i PLAYABLE;
- `phase11_complete=true` i `phase12_ready=true` po zielonym CI.

---

# Faza 12 — Test cases obowiązkowe

Każda większa zmiana engine'u musi przejść stałe scenariusze regresyjne:

1. mocny serwer vs słaby return;
2. mocny serwer vs elitarny return;
3. podobni zawodnicy -> wysoki TB / długie sety;
4. faworyt z wysokim first-set win, ale słabym comeback profile;
5. BO5 z przewagą stamina;
6. mała próbka zawodnika -> shrinkage;
7. rosnący L5 przy słabszym L20;
8. spadający L5 przy mocnym L20;
9. wysoka średnia asów zrobiona przeciw słabym returnerom;
10. Bet Builder z nogami silnie skorelowanymi;
11. dokładny przypadek typu Felix: winner + over 8.5 + under 12.5 -> joint liczony ze wspólnej dystrybucji, nie z iloczynu;
12. realna linia Superbet musi istnieć i być zweryfikowana, zanim stanie się PLAYABLE.

## Stan realizacji / gate zamknięcia

Faza 12 jest formalnym **master regression gate** i nie tworzy nowego modelu,
symulatora ani alternatywnej ścieżki runtime. Tam, gdzie scenariusz był już
pokryty przez kanoniczny test, gate uruchamia właśnie ten istniejący test.

Obowiązkowy pakiet CI pokrywa wszystkie 12 przypadków z tej sekcji.
W szczególności:

- strong server vs weak/elite return korzysta z kanonicznego nonlinear
  serve-return matchup challengera;
- TB/long-set, comeback i BO5 stamina korzystają z kanonicznego simulatora;
- small-sample korzysta z istniejącego shrinkage challengera;
- rising/falling L5 korzysta z leakage-safe rolling Player DNA;
- silnie skorelowane nogi i Felix-style joint korzystają z exact shared state,
  nigdy z iloczynu marginalnych P;
- exact current Superbet line jest wymagane przed PLAYABLE, a własne sąsiednie
  linie modelu pozostają wyłącznie RAW.

Przypadek asów jest świadomie **fail-closed**. Historyczne ace tendency jest
mierzalne, ale obecny source audit nie potwierdza bezpośredniego
`ace_vs_contact_return`. Dlatego wysoka średnia asów przeciw słabym
returnerom nie może zostać nazwana opponent-adjusted tylko na podstawie
surowych ace counts. Gate wymaga statusu źródła `source_ready=false`, dopóki
bezpośredni contact/unreturned-return source nie zostanie potwierdzony osobnym
gate'em.

Raport CI:
`frontend/data/player_dna_phase12_master_regression.json`.

Faza 12 zamyka się dopiero, gdy:

- test kontraktu Fazy 11 nadal przechodzi;
- wszystkie 12 scenariuszy mają status PASS;
- ace/contact-return pozostaje fail-closed przy braku źródła;
- exact-line Superbet gate zachowuje RAW, ale nie tworzy PLAYABLE z
  niezweryfikowanej lub sąsiedniej linii;
- brak wpływu tego gate'u na PROD, scoring runtime, ranking Symfonii 2.0 i
  PLAYABLE;
- `phase12_complete=true / phase13_ready=true`.

---

# Faza 13 — Wydajność

Mierzymy:

- czas budowy Player DNA;
- cache hit rate;
- czas matchupu;
- czas 10k/50k/100k symulacji;
- pamięć;
- koszt CI/runtime;
- deterministyczność przy stałym seedzie.

Profile historyczne powinny być cache'owane/precomputed, a przed meczem liczymy przede wszystkim matchup i dystrybucję.

---

# Faza 14 — Promotion policy

Każda nowa warstwa przechodzi:

`OFFLINE -> SHADOW -> AUDYT -> CANARY -> PROD`

Brak promocji tylko dlatego, że pojedynczy kupon wygląda dobrze.

Minimalne wymagania promocji:

- testy unit/integration zielone;
- walk-forward bez leakage;
- brak regresji kalibracji;
- wystarczający sample;
- reproducibility;
- observability;
- rollback path;
- brak równoległego starego aktywnego pipeline'u po migracji.

---

# Protokół każdej przyszłej rozmowy o Tenis AI

Każdy nowy chat dotyczący Tenis AI powinien rozpocząć pracę od:

1. przeczytania tego pliku z aktualnego `main`;
2. przeczytania `SYMPHONY_2_ARCHITECTURE.md`;
3. sprawdzenia aktualnego `main`, otwartych PR i statusu CI;
4. ustalenia, w której fazie planu jesteśmy;
5. kontynuowania od ostatniego ukończonego gate'u, bez zakładania stanu z pamięci;
6. niepisania kodu, jeżeli bieżąca faza wymaga audytu/eksperymentu;
7. aktualizacji tego dokumentu lub jednego master trackera po istotnym kamieniu milowym.

## Startowa komenda dla nowego chatu

`Kontynuujemy Tenis AI według TENIS_AI_MATCH_SIMULATION_MASTER_PLAN.md z aktualnego main. Najpierw przeczytaj master plan, SYMPHONY_2_ARCHITECTURE.md, sprawdź main/PR/CI i ustal ostatni ukończony gate. Nie twórz nowych vXXX i nie zmieniaj kodu przed wymaganym audytem.`

---

# Pierwsze zadanie po zatwierdzeniu planu

**Faza 0: pełny audyt danych i istniejących modeli względem tego planu.**

Nie wdrażamy jeszcze Player DNA ani symulatora. Najpierw tworzymy mapę tego, co już istnieje i czego brakuje, oraz sprawdzamy jakość point-by-point i możliwość historycznego walk-forward bez leakage.
