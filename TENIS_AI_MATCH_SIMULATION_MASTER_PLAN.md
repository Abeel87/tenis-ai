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
