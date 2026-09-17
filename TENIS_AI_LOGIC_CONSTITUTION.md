# Tenis AI — konstytucja logiki, danych i komunikacji modułów

Status: **KANONICZNY KONTRAKT PROJEKTU**

Ten dokument definiuje znaczenie danych i granice odpowiedzialności. Nie opisuje chwilowej implementacji; opisuje **jak system ma logicznie działać**. Jeżeli runtime jest z nim sprzeczny, sprzeczność jest bugiem albo legacy debt i wymaga audytu.

---

## 1. Cel systemu

Tenis AI nie ma być kalkulatorem średnich. Ma estymować prawdopodobieństwa tenisowe na podstawie danych osadzonych w kontekście:

- kiedy mecz był rozegrany,
- w jakim sezonie,
- na jakiej nawierzchni,
- przeciw komu,
- jak silny był przeciwnik,
- jaki był poziom rozgrywek,
- jaki był ranking obu zawodników,
- czy zawodnik jest w trendzie wzrostowym/spadkowym,
- czy wraca po długiej przerwie,
- czy jego serwis/return działa lepiej lub gorzej niż oczekiwano względem jakości rywali.

**Surowa statystyka bez kontekstu jest obserwacją, nie wiedzą.**

---

## 2. Hierarchia czasu: season != form != career

### 2.1 Current Season — 2026

Bieżący sezon opisuje **aktualny poziom i stan konkurencyjny** zawodnika. Dane z 2026 są podstawową populacją do oceny aktualnego sezonu.

W ramach 2026 należy rozróżniać co najmniej:

- recent: bardzo świeże mecze,
- medium-term: bieżąca forma średnioterminowa,
- season-to-date: cały bieżący sezon.

Dokładnych okien czasowych ani wag nie wolno ustalać „na oko”; mają być wybrane przez audyt/counterfactual/backtest.

### 2.2 Previous Season — 2025

2025 nie jest „drugą połową aktualnej formy”. Jest **bazą odniesienia poprzedniego sezonu**.

Dane 2025 służą do odpowiedzi na pytania:

- jaki był wcześniejszy poziom,
- czy 2026 jest poprawą czy pogorszeniem,
- czy zmiana rankingowa/statystyczna jest trwała,
- czy zawodnik utrzymuje historyczne cechy.

### 2.3 Starsze sezony

2024 i starsze dane mogą służyć jako:

- career prior,
- długoterminowy profil nawierzchni,
- stabilne cechy stylu,
- kontekst rozwoju/regresji.

Nie mogą automatycznie wypełniać braków „aktualnej formy” tylko po to, by przekroczyć `minimum matches`.

### 2.4 Zakaz mylenia recency z pozycją

„Ostatni 5. rekord na liście” nie oznacza „świeży rekord”. Każda obserwacja używana przez model musi mieć jawny `days_old`/wiek oraz `season`.

---

## 3. Wynik meczu jest niepełny bez jakości przeciwnika

### 3.1 Podstawowa zasada

Te dwa wyniki nie są równoważne:

- porażka #120 z #15,
- porażka #120 z #520.

Tak samo:

- wygrana z #600,
- wygrana z #40.

`WIN/LOSS` jest etykietą wyniku, a nie pełną oceną performance.

### 3.2 Context zawodnika i rywala

Każdy historyczny mecz powinien docelowo posiadać, jeśli źródło na to pozwala:

- player ranking at match,
- opponent ranking at match,
- ranking difference,
- opponent tier,
- tour/event level,
- surface,
- season,
- age of observation,
- wynik,
- podstawowe statystyki,
- provenance źródła,
- confidence/coverage.

### 3.3 Ranking

Ranking ma znaczenie, ale nie jest prawdopodobieństwem i nie może samodzielnie przesądzać wyniku.

Ranking może opisywać:

- poziom konkurencyjny,
- jakość przeciwników,
- momentum rankingowe,
- zmianę klasy zawodnika między sezonami.

**Aktualny ranking fixture'u i historyczny ranking w dacie meczu to dwa różne fakty i nie wolno ich zamieniać.**

---

## 4. Opponent-Adjusted Performance

Docelową jednostką informacji nie jest wyłącznie surowa wartość statystyki, ale również jej wynik względem trudności kontekstu.

Przykład:

- actual serve points won = 66%, expected vs opponent = 61% -> residual +5 pp,
- actual serve points won = 71%, expected vs opponent = 69% -> residual +2 pp.

Surowo 71% > 66%, ale pierwszy występ może być mocniejszym dowodem jakości serwisu.

Ta sama zasada dotyczy m.in.:

- serve points won,
- return points won,
- hold rate,
- break rate,
- first/second serve,
- set performance,
- tie-break/pressure behaviour, o ile sample size pozwala.

Opponent adjustment ma być budowany i walidowany w SHADOW przed wpływem na PROD.

---

## 5. Player DNA i Player State to różne byty

### 5.1 Player DNA

Player DNA opisuje względnie trwałe cechy zawodnika:

- serve strength,
- return strength,
- hold/break ability,
- first/second serve profile,
- surface profile,
- pressure/tie-break profile,
- charakterystyczne wzorce gry.

Player DNA **nie jest aktualną formą**.

### 5.2 Player State

Player State jest osobną warstwą planowaną/SHADOW do czasu zatwierdzenia i opisuje „jaki ten zawodnik jest teraz”:

- current-season level,
- recent form,
- medium-term form,
- season trend,
- ranking momentum,
- serve trend,
- return trend,
- surface state,
- inactivity/comeback state,
- confidence.

Przykład:

- DNA wysokie + State słaby = dobry gracz w słabym okresie,
- DNA średnie + State wysoki = zawodnik robiący progres.

Nie wolno mieszać obu pojęć w jednym polu bez jawnej definicji.

---

## 6. Długa przerwa i powrót

Brak meczów przez długi okres jest obserwacją `inactivity_gap`.

Bez zewnętrznego, twardego źródła nie wolno wnioskować, że przyczyną była kontuzja.

System powinien docelowo umieć rozpoznać:

- długość przerwy,
- liczbę meczów od powrotu,
- trend performance po powrocie,
- wzrost niepewności przy małej próbce po przerwie.

Powrót nie oznacza automatycznie spadku formy; ma podnosić uncertainty do czasu nowych obserwacji.

---

## 7. Nawierzchnia i poziom rozgrywek

### 7.1 Surface

Surface jest kontekstem pierwszej klasy. System musi odróżniać:

- bieżącą formę ogólną,
- bieżącą formę na surface,
- długoterminowe surface DNA.

`model_ready` nie może być interpretowane jako „silna wiedza o tej nawierzchni”, jeżeli takiej wiedzy brak.

### 7.2 Tour / event level

ATP, Challenger, kwalifikacje i WTA nie mogą być traktowane jako jedna anonimowa populacja, gdy parametr zależy od poziomu gry/populacji.

Globalne priory wymagają jawnej segmentacji albo udowodnionego powodu, dlaczego wspólna populacja jest poprawna.

Historyczne `source_tour`/event level nie może być tylko metadanym, jeśli wpływa na trudność osiągnięcia statystyki.

---

## 8. Kanoniczny przepływ informacji

Docelowy logiczny przepływ:

`RAW SOURCES`

→ `IDENTITY + HYGIENE + PROVENANCE`

→ `CONTEXT (season/age/rank/opponent/tour/surface/inactivity)`

→ równolegle:

- `PLAYER DNA`
- `PLAYER STATE`
- `SURFACE`
- `SERVE`
- `RETURN`
- `EARLY/PBP`
- inne wyspecjalizowane cechy

→ `CURRENT ENGINE / ML MODELS`

→ `CALIBRATION / VALIDATED ENSEMBLE`

→ `SYMFONIA 2.0`

→ `EXACT CURRENT SUPERBET OFFER`

→ `PLAYABLE`

→ `iNeed$`

→ `UI / HISTORY / SETTLEMENT`

Każda strzałka jest kontraktem. Downstream nie może „naprawiać” znaczenia danych upstream.

---

## 9. Własność probability

Probability ma konkretnego właściciela.

- RAW model tworzy probability.
- Kalibracja może przekształcić probability zgodnie z własnym kontraktem i historią.
- Ensemble może łączyć jawnie wskazane modele.
- Symfonia może tworzyć joint probability wyłącznie dla wspieranego state-space.
- Superbet dostarcza ofertę/odds, nie model probability.
- PLAYABLE decyduje, czy wybór spełnia warunki publikacji/operatora.
- iNeed$ konsumuje finalne probability i odds do risk/EV/stake; nie wymyśla nowych probability.
- frontend tylko prezentuje.

Żadna warstwa nie może po cichu nadpisywać probability poprzedniej warstwy pod tą samą nazwą pola.

---

## 10. Readiness ma być semantyczne, nie tylko techniczne

Obecne pojedyncze `model_ready` nie może być interpretowane jako pełna gwarancja jakości wszystkich rynków.

Docelowo readiness powinno mieć reason codes/dimensions, np.:

- identity_ready,
- freshness_ready,
- current_season_ready,
- surface_ready,
- rank_context_ready,
- opponent_context_ready,
- serve_ready,
- return_ready,
- pbp_ready,
- market-specific-ready.

Nie należy wdrażać tego do PROD bez audytu wpływu. Jest to kontrakt kierunku reorganizacji.

---

## 11. Learning: model ma uczyć się na prawidłowej próbce

### 11.1 Prediction Ledger

Docelowo przed startem meczu należy zamrozić dla każdego wspieranego przewidywania:

- model/version/owner,
- feature/context snapshot,
- probability,
- readiness,
- czy było PLAYABLE,
- czy wybrała je Symfonia,
- czy zaakceptował je iNeed$,
- timestamp i provenance.

Po rozliczeniu dopisywany jest outcome.

### 11.2 Oddzielne metryki

Nie mieszać:

- ALL MODEL PREDICTIONS,
- PLAYABLE PREDICTIONS,
- SELECTED/EXECUTION-SIMULATOR BETS.

Accuracy/Brier/ROI jednej populacji nie może być przedstawiane jako wynik innej.

### 11.3 Common test set

Current/CatBoost/TabPFN/inni challengerzy muszą być porównywani również na wspólnym intersection set. Różne sample sizes są dozwolone diagnostycznie, ale nie mogą tworzyć fałszywego rankingu modeli.

Walk-forward/chronologia musi zapobiegać użyciu przyszłych informacji.

---

## 12. Guard contract

Guard istnieje tylko po to, by chronić jasno określony invariant.

Guard nie może:

- redefiniować modelu,
- zastępować brakującego modułu,
- kasować legalnego outputu nowego silnika tylko dlatego, że zachował legacy assumption,
- maskować błędu upstream,
- tworzyć alternatywnego outputu o tej samej semantyce.

Każdy guard ma mieć reason code. Konflikty guardów są P1 architecture bug.

Przykład klasy problemu: jeśli silnik świadomie wspiera BO5, a późniejszy legacy guard usuwa prawidłowy BO5 output, należy audytować kontrakt guardu, a nie dokładać kolejny override.

---

## 13. Superbet / PLAYABLE

Superbet jest autorytetem tylko dla:

- istnienia bieżącego meczu/oferty,
- dokładnego rynku,
- dokładnej linii,
- dostępnego kursu.

Nie może usuwać MODEL/RAW tylko dlatego, że operator nie ma rynku.

PLAYABLE ma być fail-closed:

- exact fixture,
- exact selection,
- exact line,
- aktualność oferty,
- wymagany model/readiness.

Nearest-line substitution i zgadywanie operatora są zabronione w PLAYABLE.

---

## 14. Symfonia

Symfonia jest kompozytorem rynków, nie źródłem danych zawodnika.

- konsumuje finalne, wspierane sygnały,
- liczy joint probability tylko dla wspieranego wspólnego state-space,
- nie może udawać niezależności skorelowanych nóg,
- ranking kompozycji/utility nie może być przedstawiany jako probability wejścia całego kuponu,
- liczba nóg nie jest sama w sobie miarą bezpieczeństwa.

---

## 15. iNeed$

Docelowa jednostka ekonomiczna dla Bet Buildera to **cała kompozycja**, nie każda noga osobno.

Po zatwierdzeniu redesignu SHADOW iNeed$ powinien konsumować:

- final composition id,
- pełną listę nóg,
- joint probability,
- rzeczywisty combined odd operatora, jeśli dostępny,
- EV całej kompozycji,
- risk/exposure całej kompozycji,
- jedną stawkę,
- jeden settlement kuponu.

Obecnego SHADOW nie wolno przedstawiać jako dowodu rentowności prawdziwego BB, dopóki kontrakt nie zostanie poprawiony i zwalidowany.

---

## 16. Frontend

Frontend jest widokiem, nie dodatkowym modelem.

Musi rozróżniać:

- MODEL/RAW,
- calibrated/ensemble,
- SHADOW,
- Symfonia,
- operator offer,
- PLAYABLE,
- iNeed$,
- settlement.

Każda wartość powinna mieć jedno źródło backendowe. Jeśli nie wiadomo, skąd pole pochodzi, pole nie powinno być używane do decyzji użytkownika do czasu ustalenia provenance.

Brak danych jest pokazywany jako brak, nigdy jako zmyślony H2H, `0%`, `0.00`, fallback probability albo „najbliższa” linia.

---

## 17. Identity i kolizje danych

- Provider ID obowiązuje tylko w swoim namespace.
- Nie wolno porównywać ID między providerami jak wspólnych identyfikatorów.
- Exact evidence > alias inference.
- Fuzzy matching nie może być podstawą łączenia historii zawodnika bez jawnego, osobnego kontraktu i audytu kolizji.
- Konflikt tożsamości = fail-closed; dane nie wchodzą do profilu do wyjaśnienia.
- Deduplikacja nie może usuwać dwóch różnych meczów tylko dlatego, że mają podobne nazwy.

---

## 18. Zasada minimalnej poprawki

Jeśli bug jest w funkcji X:

1. test pokazujący bug w X,
2. poprawa X,
3. usunięcie nieaktualnej logiki, jeśli zastępowana,
4. test regresyjny,
5. kontrola downstream,
6. aktualizacja registry/architecture, jeżeli zmienił się kontrakt.

Nie twórz `X_fix`, `X_new`, `X_vNext` jako aktywnej równoległej ścieżki.

---

## 19. Zasada wdrażania nowej logiki

Każda nowa logika wpływająca na probability/próg/wagę przechodzi:

`AUDIT -> SHADOW FEATURE -> COUNTERFACTUAL/BACKTEST -> COMMON TEST SET -> REVIEW -> explicit promotion -> PROD`

Nigdy:

`pomysł -> bezpośredni PROD`.

Brak przewagi lub brak wystarczających danych = pozostaje SHADOW albo zostaje usunięte.

---

## 20. Niezmienne granice

Bez jawnej decyzji właściciela projektu nie wolno zmieniać wzajemnych kompetencji:

- Identity nie prognozuje.
- Context nie ustala końcowego probability.
- DNA nie jest current form.
- Player State nie zmienia identity.
- ML nie zmienia raw history.
- AutoLearn nie poprawia settlementu.
- Symfonia nie poprawia Player DNA.
- Superbet nie zmienia MODEL/RAW.
- PLAYABLE nie tworzy brakującej linii.
- iNeed$ nie tworzy probability.
- UI nie tworzy danych.
- SHADOW nie steruje PROD bez jawnej promocji.

To jest podstawowy kontrakt zapobiegający kolizjom logicznym w Tenis AI.