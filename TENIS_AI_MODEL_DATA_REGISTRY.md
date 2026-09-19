# Tenis AI — rejestr modeli, danych, właścicieli logiki i program napraw

Status: **KANONICZNY REJESTR ROBOCZY**

Ostatnia duża reorganizacja dokumentacyjna: 2026-09-17.

Ten plik odpowiada na cztery pytania:

1. Co w projekcie istnieje?
2. Za co dokładnie odpowiada?
3. Czego nie wolno mu robić?
4. Co jest do naprawienia i w jakiej kolejności?

Każdy kolejny agent/czat ma aktualizować ten plik, gdy zmienia właściciela logiki, kontrakt danych, status PROD/SHADOW albo kolejność programu napraw.

---

# A. Mapa danych

## A1. Live Tennis API — fixtures / provider context

**Rola:** bieżące mecze i dane fixture/provider.

**Może dostarczać:**

- bieżące fixture,
- schedule/start time,
- provider player IDs,
- aktualne pola fixture takie jak ranking, jeśli obecne,
- PBP/tape tam, gdzie dostępne i zgodne z kontraktem.

**Nie może:**

- być automatycznie łączone ID z ID innego providera,
- tworzyć aliasów na podstawie samego podobieństwa nazw,
- być traktowane jako historyczne źródło TML bez jawnego mapowania.

**Znany problem:** część aktualnego kontekstu rankingu fixture nie jest wykorzystywana przez Current Engine tak, jak powinna; wymaga audytu provenance cechy rankingowej.

---

## A2. TennisMyLife — historia meczów/statystyk

**Rola:** historyczna baza statystyczna.

**Aktualny runtime:** bieżące źródła + 2026 + 2025.

**Kontrakt sezonów:**

- 2026 = current-season evidence,
- 2025 = previous-season baseline,
- starsze = career prior/historyczny kontekst po osobnej walidacji.

**Nie wolno:**

- używać starego sezonu tylko po to, aby sztucznie dobić do `minimum matches` aktualnej formy,
- nazywać „ostatnimi 5 aktualnymi” pięciu ostatnich dostępnych rekordów bez kontroli wieku,
- łączyć rekordów o niepewnej tożsamości.

**Znany problem P1:** obecny player profile może wykorzystywać bardzo stare rekordy, bo recency jest pozycyjna, nie kalendarzowa.

---

## A3. PBP / point tape

**Rola:** zachowanie punkt/gem, Early Hold i rynki zależne od sekwencji punktowej.

**Nie może:**

- zastępować brakującej historii modelowej, jeśli semantyka danych jest inna,
- udawać świeżości tylko dlatego, że rekord jest jednym z ostatnich dostępnych.

**Znany problem P1/P2:** Early Hold również potrzebuje jawnej polityki wieku danych; „latest N” nie jest wystarczającą definicją aktualnej formy.

---

## A4. Superbet

**Rola:** exact current operator offer.

**Jest autorytetem dla:**

- dostępności meczu,
- rynku,
- selection,
- exact line,
- odds/price,
- aktualności oferty.

**Nie jest autorytetem dla:**

- model probability,
- Player DNA,
- current form,
- historycznej jakości zawodnika.

**Znany problem P1/P2:** etap fixture matching ma element heurystyczny; exact-offer contract jest mocniejszy po dopasowaniu niż samo wejściowe dopasowanie fixture. Wymaga osobnego identity/operator-match audit.

---

# B. Mapa modułów/modeli

## B1. Identity + History Hygiene

**Status:** PROD / krytyczna infrastruktura.

**Odpowiedzialność:**

- normalizacja i higiena rekordów,
- identyfikacja zawodników,
- deduplikacja,
- odrzucenie konfliktów.

**Wyjście:** kanoniczne, audytowalne rekordy przypisane do właściwej tożsamości.

**Nie może:** prognozować ani zgadywać tożsamości, aby zwiększyć coverage.

**Twarde zasady:** provider namespace pozostaje rozdzielony; conflict -> fail-closed.

**Do zrobienia:** docelowy jawny provenance/identity contract używany przez wszystkie modele.

---

## B2. Context Engine

**Status:** SHADOW EVIDENCE READY — canonical owner `backend/match_context_shadow.py`; LOGIC-04 PR #392 merged as `c9acb27e48f41e9a5aaa0fa1bb041c65c5f45ab7`. No PROD activation.

**Odpowiedzialność:** tworzyć znaczenie wokół każdego rekordu:

- season,
- days_old,
- same_surface,
- tour/event level,
- player rank at observation,
- opponent rank at observation,
- rank difference/tier,
- inactivity gap,
- match number after comeback,
- provenance/confidence.

**Nie może:** tworzyć finalnego probability ani zmieniać historycznego wyniku.

**Cel:** jeden wspólny kontekst dla DNA, State, Current, ML i specjalistów; koniec z różnymi definicjami świeżości w różnych modułach.

---

## B3. Current Engine

**Status:** PROD.

**Kanoniczna odpowiedzialność:** bazowy silnik statystyczny probability.

**Główne wejścia:** historyczne profile/statystyki + fixture context.

**Główne wyjścia:** bazowe probability/rynki/metryki profilu.

**Nie może:**

- pobierać kursów jako źródła probability,
- poprawiać identity,
- udawać, że stare dane są aktualne,
- mieszać populacji bez jawnego kontraktu.

**Znane problemy:**

1. **P1 Freshness:** brak maksymalnego wieku danych; positional decay może nadać istotną wagę bardzo staremu rekordowi.
2. **P1 Readiness:** `model_ready` oznacza głównie techniczną dostępność danych, nie pełną aktualność/adequacy.
3. **P1 Surface readiness:** brak wystarczająco silnego rozdzielenia „ogólnie mam dane” od „mam dane właściwe dla aktualnej nawierzchni”.
4. **P1 Population priors:** globalne surface priors wymagają audytu segmentacji ATP/CH/WTA.
5. **P1 Ranking provenance:** historyczny `latest_rank` może być stary; aktualny ranking fixture wymaga poprawnego kontraktu cechy.
6. **P1 Opponent quality:** surowe statystyki są niewystarczająco opponent-adjusted.
7. **P2 BO5/guard conflict:** silnik i downstream guard mają niespójny kontrakt dla części BO5 outputs.

**Zakaz:** nie poprawiać tych punktów jednym wielkim refaktorem. Każdy wymaga SHADOW/counterfactual i osobnego PR.

---

## B4. Player DNA

**Status:** istniejąca warstwa; kontrakt długoterminowy.

**Odpowiedzialność docelowa:** względnie trwałe cechy zawodnika.

**Nie jest:** current form.

**Docelowe znaczenie:**

- serve/return ability,
- hold/break ability,
- surface profile,
- pressure/tie-break tendencies,
- względnie stabilne wzorce.

**Znany dług technologiczny:** część surowych procentów może odzwierciedlać klasę przeciwników zamiast wyłącznie „talentu” zawodnika.

**Kierunek:** opponent-adjusted DNA w SHADOW; stary DNA nie może być nadpisany przed walidacją.

---

## B5. Player State

**Status:** SHADOW EVIDENCE READY — canonical owner `backend/player_dna_player_state_shadow.py`; PR #399 merged as `7d5e66a07ba400473302966e40592a591dfd71c3`. No PROD activation.

**Odpowiedzialność:** bieżący stan zawodnika.

**Planowane cechy:**

- current-season level,
- recent/medium-term form,
- season trend,
- ranking momentum,
- serve/return trend,
- surface state,
- inactivity/comeback state,
- uncertainty/confidence.

**Nie może:** zmieniać Player DNA ani identity.

**Główna zasada:** `DNA != State`.

---

## B6. Opponent Strength / Opponent Adjustment

**Status:** SHADOW EVIDENCE READY — canonical owner `backend/player_dna_opponent_adjustment_audit.py`; LOGIC-05 PR #394 and LOGIC-06 PR #397 are merged. Opponent-strength and opponent-adjusted serve/return/hold/break remain evaluation-only; no PROD activation.

**Odpowiedzialność:** osadzić wynik/statystykę w sile rywala.

**Wejście:** ranking/historyczny rank, surface strength, tour/event context, docelowo Surface Elo/validated opponent strength.

**Wyjście:** expected performance + residual/adjusted performance.

**Nie może:** zakładać liniowej relacji rankingów bez walidacji.

**Cel:** 72% serve przeciw Top 30 i 72% przeciw #500 nie są tym samym dowodem jakości.

---

## B7. Surface layer / Surface Elo

**Status:** istniejące elementy, Surface Elo SHADOW.

**Odpowiedzialność:** jakość/siła w kontekście nawierzchni.

**Nie może:** po cichu wpływać na PROD, dopóki status SHADOW nie zostanie jawnie promowany.

**Do zrobienia:** odróżnić:

- long-term surface DNA,
- current-season surface state,
- opponent-adjusted surface strength.

---

## B8. Serve Specialist

**Status:** istniejąca specjalistyczna warstwa.

**Odpowiedzialność:** sygnały serwisowe.

**Docelowo:** raw + opponent-adjusted serve, rozdzielone i jawnie opisane.

**Nie może:** uznawać tego samego procentu za tę samą siłę bez kontekstu jakości returnera.

---

## B9. Return Specialist

**Status:** logiczna odpowiedzialność musi być jawna, nawet jeśli obecna implementacja jest rozproszona.

**Odpowiedzialność:** jakość returnu.

**Docelowo:** actual return vs expected return against opponent serve strength.

**Do zrobienia:** ustalić jednego kanonicznego właściciela implementacyjnego; nie tworzyć duplikującego modułu przed inwentaryzacją.

---

## B10. Early Hold / PBP

**Status:** aktywna specjalistyczna warstwa.

**Odpowiedzialność:** zachowanie we wczesnych gemach, sekwencje 1:1/2:2/3:3, service holds, rynki PBP.

**Znany problem:** latest-N bez jawnej granicy wieku może mylić historyczną dostępność z bieżącą formą.

**Nie może:** używać zbyt starej próbki bez jawnego uncertainty/reason code po wdrożeniu nowego kontraktu freshness.

---

## B11. Form Specialist

**Status:** istniejąca specjalistyczna odpowiedzialność; implementacja wymaga inwentaryzacji.

**Docelowa odpowiedzialność:** trend bieżącego performance, nie proste W/L.

**Ma uwzględniać w przyszłości:**

- opponent strength,
- performance residual,
- season delta,
- ranking momentum,
- comeback uncertainty.

**Nie może:** sprowadzać „formy” do średniej z nieograniczonego wiekiem latest-N.

---

## B12. AutoLearn

**Status:** PROD learning/calibration stack.

**Odpowiedzialność:** uczenie/ocena modeli na rozliczonej historii zgodnie z chronologią.

**Nie może:**

- zmieniać raw history,
- poprawiać identity,
- przedstawiać selected-signal accuracy jako globalnej accuracy wszystkich prognoz.

**Znany problem P1:** selection bias / różne populacje obserwacji wymagają audytu Learning Integrity.

**Do zrobienia:** prediction ledger + common test set + rozdzielone metryki ALL/PLAYABLE/SELECTED.

---

## B13. CatBoost / TabPFN / challenger ML

**Status:** aktywne/uczące się zgodnie z obecną architekturą.

**Odpowiedzialność:** niezależne predykcyjne challengery.

**Nie mogą:** być porównywane jako „lepszy/gorszy model” wyłącznie na nieidentycznych próbkach.

**Do zrobienia:** common intersection test set, walk-forward, calibration comparison.

---

## B14. Adaptive Learning / Dynamic Weights

**Status:** aktywne meta-warstwy według bieżącej architektury.

**Odpowiedzialność:** kontrolowane łączenie/zmiany wag na podstawie zatwierdzonej telemetryki.

**Nie mogą:** maskować złych cech wejściowych. Lepszy weight nie naprawi złej definicji formy.

**Do zrobienia:** po naprawie sampling/ledger ponownie ocenić governance wag na wspólnym zbiorze.

---

## B15. Neuron

**Status:** SHADOW_RESEARCH.

**Odpowiedzialność:** eksperymentalna niezależna analiza/research.

**Nie może:** sterować PROD/PLAYABLE/Symphony/iNeed$ bez jawnej promocji.

**Twarda zasada:** obecny przebudowany Neuron zostaje; stary NEURO/Neutron pozostaje usunięty.

---

## B16. Symfonia 2.0

**Status:** kanoniczna warstwa kompozycji.

**Odpowiedzialność:**

- konsumowanie wspieranych sygnałów,
- exact-line/operator-aware composition,
- joint probability tylko dla wspieranego state-space,
- ranking kompozycji.

**Nie może:**

- zmieniać Player DNA/State,
- wymyślać brakującego market probability,
- mnożyć skorelowanych nóg jak niezależnych,
- przedstawiać utility jako probability kuponu.

**Znany problem/ryzyko:** interpretation `recommended_leg_count`/utility musi być jasno oddzielona od realnego probability/EV całego BB.

---

## B17. PLAYABLE

**Status:** PROD, fail-closed.

**Odpowiedzialność:** operatorowa i jakościowa bramka finalnej selekcji.

**Musi wymagać:** exact current offer zgodnie z kontraktem.

**Nie może:**

- usuwać MODEL/RAW,
- tworzyć nearest line,
- zmieniać upstream probability,
- zastępować brakującego kontekstu fikcyjnym fallbackiem.

---

## B18. iNeed$

**Status:** SHADOW / eksperymentalny risk layer.

**Odpowiedzialność:** bankroll/risk/EV/stake po PLAYABLE.

**Znany problem P0 przed realnym execution:** obecna jednostka ekonomiczna jest zbyt bliska pojedynczemu signal/leg zamiast finalnemu Bet Builderowi jako całości.

**Docelowy kontrakt:** composition -> joint probability -> combined odd -> EV całego BB -> stake całego BB -> jeden settlement.

**Zakaz:** żadnego real-money automation do czasu osobnej, jawnej decyzji i pełnej walidacji bezpieczeństwa.

---

## B19. Settlement

**Status:** PROD infrastruktura wynikowa.

**Odpowiedzialność:** jednoznaczne rozliczenie zamrożonych predykcji/rynków.

**Nie może:** zgadywać wyniku, traktować braku score jako zero ani poprawiać modelu.

**Do zrobienia:** market-by-market contract audit po uporządkowaniu prediction ledger.

---

## B20. Frontend

**Status:** PROD presentation layer.

**Odpowiedzialność:** prezentować kanoniczne backend outputs.

**Nie może:**

- liczyć własnego probability,
- inventować H2H,
- wyświetlać SHADOW jako PROD,
- zastępować brakującej linii najbliższą,
- przedstawiać stale snapshot jako realtime bez timestampu,
- używać pól o nieustalonym provenance do decyzji.

**Znany problem P2:** `ARCHITECTURE.md` i faktyczni właściciele UI po przebudowie nie są w pełni zgodni; trzeba wykonać Frontend Ownership Audit i zaktualizować mapę.

---

# C. Known Logic Debt — kolejka problemów

## P0 — blokuje przyszłe realne użycie

### P0.1 iNeed$ unit-of-bet mismatch

**Problem:** pojedyncze nogi są traktowane zbyt niezależnie względem docelowego BB.

**Naprawa:** osobny SHADOW redesign po zakończeniu audytów danych/modeli. Nie poprawiać przez wrapper; poprawić kanoniczny przepływ iNeed$.

---

## P1 — wysoki wpływ na jakość probability

### P1.1 Freshness semantics

Obecne latest-N może zawierać bardzo stare obserwacje.

**Następny krok:** counterfactual 30/60/90/120/180/365 dni bez zmiany PROD.

### P1.2 Season semantics

2026 i 2025 są dostępne, ale nie mają wystarczająco odrębnych ról `current state` vs `previous baseline`.

**Następny krok:** SHADOW season features i season delta.

### P1.3 Opponent strength

Surowe statystyki/wyniki nie są wystarczająco osadzone w klasie rywala.

**Następny krok:** Context + opponent-strength SHADOW.

### P1.4 Ranking provenance

Należy rozdzielić ranking aktualny od rankingu w historycznej obserwacji i zweryfikować, który jest używany gdzie.

### P1.5 Priors/population segmentation

Zweryfikować ATP/CH/WTA i event-level priors. Brak mieszania populacji bez dowodu.

### P1.6 model_ready semantics

Obecny boolean nie powinien być interpretowany jako uniwersalna gotowość wszystkich rynków.

SHADOW audit owner dla semantycznego readiness: `backend/readiness_engine_shadow.py`. Legacy `model_ready` pozostaje read-only i bez zmiany semantyki podczas migracji.

### P1.7 Learning Integrity

Selection bias, różne sample sizes i brak pełnego ledger wymagają wspólnego benchmarku.

### P1.8 Guard collision audit

Wykryć legacy guardy sprzeczne z kanonicznym silnikiem, zaczynając od znanych konfliktów typu BO5.

### P1.9 Identity/operator match boundary

Zweryfikować wszystkie miejsca fuzzy/similarity matching i wymusić fail-closed tam, gdzie błędne dopasowanie może skażać PLAYABLE/history.

---

## P2 — architektura/utrzymywalność/prezentacja

### P2.1 Frontend ownership drift

Zmapować faktycznych właścicieli listy, detail, Symphony, PLAYABLE, admin, history po przebudowie UI i poprawić `ARCHITECTURE.md`.

### P2.2 Duplicated responsibilities

Inwentaryzacja plików `vXXX`, wrapperów kompatybilności i równoległych ścieżek. Usuwanie tylko po ustaleniu aktywnego właściciela i testów.

### P2.3 Snapshot/realtime semantics

UI ma pokazywać prawdziwy `generated_at`/freshness, nie sugerować realtime tylko dlatego, że frontend często odświeża JSON.

### P2.4 Old immutable archive refresh policy

Zweryfikować, czy roczne archiwa traktowane jako immutable wymagają okresowego checksum/revalidation.

---

# D. Program reorganizacji — kolejność prac

Każdy etap ma osobny PR. **Nie łączyć etapów dla wygody.**

## LOGIC-00 — Constitution / Registry

**Zakres:** tylko dokumentacja i kontrakty.

**Cel:** jeden punkt prawdy dla kolejnych agentów.

**Runtime:** zero zmian.

---

## LOGIC-01 — Freshness Counterfactual

**Zakres:** Current + PBP, tylko audit/SHADOW.

Porównać dla tych samych fixture:

- obecny system,
- max age 30,
- 60,
- 90,
- 120,
- 180,
- 365 dni.

Raportować:

- profile remaining,
- model_ready delta,
- market availability delta,
- probability deltas,
- calibration/Brier/accuracy na settled sample, jeśli statystycznie możliwe,
- affected players/matches,
- surface coverage.

**Zakaz:** nie wybierać progu przed wynikami.

---

## LOGIC-02 — Feature Provenance + Ranking Audit

**Zakres:** zero zmiany probability.

Dla każdego model-ready fixture udokumentować:

- które historyczne mecze weszły,
- ich daty/age/season/surface/tour,
- player/opponent rank dostępny w źródle,
- aktualny rank fixture,
- jakie priory i wagi zastosowano,
- skąd pochodzi każde pole rankingu używane w kalkulacji.

**Cel:** żadnych „magicznych” cech bez źródła.

---

## LOGIC-03 — Population / Prior Audit

**Zakres:** ATP/CH/WTA/event-level/surface priors.

Porównać wspólne priory vs segmentowane counterfactual.

**Runtime:** bez zmian.

**Promotion:** tylko jeśli dane pokażą przewagę i sample size jest wystarczający.

---

## LOGIC-04 — Context Engine SHADOW

Zbudować kanoniczny context record bez wpływu na PROD:

- season,
- days_old,
- surface,
- tour/event,
- current/historical rank provenance,
- opponent tier,
- inactivity,
- confidence.

**Nie tworzyć nowych probability.**

---

## LOGIC-05 — Opponent Strength SHADOW

Zbudować opponent difficulty/expected performance.

Testować ranking-only baseline oraz bogatszy kontekst. Nie zakładać liniowej relacji rankingu.

Wyjście musi być audytowalne per historyczny mecz.

---

## LOGIC-06 — Opponent-Adjusted Serve/Return SHADOW

Dodać równoległe diagnostyczne cechy:

- actual,
- expected,
- residual,
- sample size,
- opponent strength distribution.

Nie nadpisywać istniejącego Player DNA.

---

## LOGIC-07 — Player State SHADOW

Oddzielić:

- current season,
- recent trend,
- medium trend,
- season-over-season delta,
- ranking momentum,
- inactivity/comeback uncertainty,
- current-surface state.

Porównać z samym Player DNA.

---

## LOGIC-08 — Readiness Semantics Audit

**Status:** IN PROGRESS — phase-1/2 merged; phase-3 consumer requirement matrix merged in PR #406 (`777f48b87407b14937feb7d46ce97e707dca4f71`); phase-4 exact-snapshot observability delivery audit next.

**Canonical semantic owner:** `backend/readiness_engine_shadow.py`.

**Canonical consumer inventory:** `TENIS_AI_READINESS_CONSUMER_MAP.md`.

**Canonical phase-3 requirement matrix:** `TENIS_AI_READINESS_REQUIREMENT_MATRIX.md`.

**Canonical phase-4 delivery audit:** `TENIS_AI_READINESS_DELIVERY_AUDIT.md`.

Phase 1 reports deterministic reason codes and `READY / NOT_READY / UNKNOWN` beside legacy `model_ready`. Coverage without an approved sufficiency policy remains `UNKNOWN`; a hard missing required input under an existing contract may be `NOT_READY`. Legacy `model_ready` remains observational/read-only for the SHADOW engine.

Market/family readiness may be `READY` only through an existing explicit contract such as PBP `market_evidence_v940`. PBP `market_ready`, Symphony `learning_model_ready`, and Superbet operator availability are separate contracts and must not be collapsed into one overall readiness flag.

Phase 2 is complete in PR #403: 21 exact-token source files are frozen/classified in `TENIS_AI_READINESS_CONSUMER_MAP.md` and contract-tested with zero runtime wiring. Phase 3 maps 22 exact legacy tokens on 19 consumer source lines to consumer-specific requirements, evidence owners, UNKNOWN/missingness semantics and behavior-change risk. No runtime/learning gate is approved for replacement. AutoLearn/specialist/history-learning consumers are deferred to LOGIC-09; the prediction-integrity guard is deferred to LOGIC-10.

The first selected observability path is additive SHADOW-labeled aggregate/meta telemetry beside legacy `meta.model_ready` in `backend/update.py`, only after exact snapshot alignment is proven. Diagnostic/admin UI counters are second; moderator filtering is explicitly not observability-only. Legacy `model_ready` cannot be removed while any audited consumer still depends on it.

Phase 4 now defines the exact-snapshot observability join contract in the canonical SHADOW owner. `backend/snapshot_digest.py` owns deterministic `canonical-json-sha256-v1`. The generic history-coverage owner is unchanged: Point Tape regenerates coverage from restored cache, then stamps only that run-local report with the exact current `results` digest before semantic readiness consumes it. `readiness_engine_shadow` rejects history evidence unless the stamped digest matches the current results snapshot, and `observability_snapshot_alignment()` rejects any stale/missing contract. This eliminates the observed false-positive where counts/IDs matched across different data snapshots without changing identity/history semantics. A semantic aggregate is eligible only when report status is ready, current/readiness/history digests align, Player State aligns, and legacy Current Engine mismatches are zero. Missing/mismatched evidence is unavailable/N/D, never inferred READY/NOT_READY or zero. Runtime delivery remains unwired.

Producer-host audit result: existing `Player DNA SHADOW refresh` is the selected implementation candidate because it is already chained after successful Update on `main`, restores the local cache, builds required Player DNA derived state and owns the existing SHADOW publication commit. Required readiness prerequisite modules are local-only/zero-network by source audit. Historical bot commit `34285c9...` did not retrigger Update, but the implementation PR must re-verify this run topology. No new parallel workflow is approved.

Zero probability, threshold, weight, training, PLAYABLE or iNeed$ influence.

---

## LOGIC-09 — Learning Integrity / Prediction Ledger

Wprowadzić pełny, pre-match frozen ledger oraz wspólny zbiór porównawczy Current/CatBoost/TabPFN.

Oddzielić metryki:

- ALL,
- PLAYABLE,
- SELECTED.

Usunąć błędne porównania dopiero po udowodnieniu i migracji telemetryki.

---

## LOGIC-10 — Guard Ownership Audit

Lista wszystkich guardów/walidatorów:

- owner,
- invariant,
- input/output,
- reason code,
- czy blokuje legalny output,
- czy duplikuje inny guard.

Naprawa: usuwać/zmieniać nieaktualny warunek **w kanonicznym guardzie**, nie dodawać obejść.

---

## LOGIC-11 — Frontend Ownership + Provenance

Zmapować faktyczny UI po przebudowie.

Każde wyświetlane pole klasyfikować jako:

- RAW,
- MODEL,
- CALIBRATED/ENSEMBLE,
- SHADOW,
- SYMPHONY,
- SUPERBET,
- PLAYABLE,
- iNeed$,
- SETTLEMENT.

Usunąć/naprawić pola bez źródła. Brak danych = brak danych.

---

## LOGIC-12 — iNeed$ Bet Builder Redesign SHADOW

Dopiero po ustabilizowaniu upstream.

Jednostka: finalna kompozycja BB.

Wymagane:

- composition id,
- legs,
- joint probability,
- exact combined operator odds,
- EV,
- exposure,
- stake,
- one-ticket settlement.

Nie implementować real-money execution w tym etapie.

---

# E. Reguła promocji SHADOW -> PROD

Każdy LOGIC etap wpływający na wynik musi przejść:

1. audyt aktualnego zachowania,
2. testy jednostkowe,
3. frozen counterfactual na tych samych fixture,
4. historyczny walk-forward tam, gdzie dane pozwalają,
5. common test set,
6. calibration/Brier + accuracy jako pomocnicze,
7. analiza coverage i regresji,
8. jawna decyzja właściciela projektu,
9. osobny promotion PR,
10. pełne zielone CI i produkcyjną weryfikację.

**Brak dowodu przewagi = brak promocji.**

---

# F. Reguła usuwania starego kodu

Stary aktywny kod można usunąć, gdy:

- wskazano nowego kanonicznego właściciela,
- wszyscy konsumenci są zmigrowani,
- testy kontraktowe przechodzą,
- nie istnieje potrzebny historyczny format danych zależny od tej ścieżki,
- pełne CI jest zielone.

Nie zostawiać aktywnego starego kodu „na wszelki wypadek”. Jeżeli potrzebny jest rollback, zapewnia go Git, nie dwie produkcyjne implementacje.

---

# G. Checklist dla każdego kolejnego PR dotyczącego logiki

- [ ] Fresh `main` sprawdzony.
- [ ] `AGENTS.md` przeczytany.
- [ ] Ten registry przeczytany.
- [ ] Kanoniczny owner wskazany.
- [ ] Brak nowego `vXXX`/równoległego hotfixu.
- [ ] Bug odtworzony testem/audytem.
- [ ] Zakres nie wychodzi poza właściciela problemu.
- [ ] Dane mają provenance.
- [ ] Brak SHADOW -> PROD bez jawnej promocji.
- [ ] Brak zmyślonych fallbacków.
- [ ] Guardy nie są obchodzone drugim guardem.
- [ ] UI nie liczy logiki modelowej.
- [ ] Registry zaktualizowany, jeśli zmienił się kontrakt.
- [ ] Pełne CI zielone.
- [ ] Fresh-main check przed merge.
- [ ] Produkcyjna weryfikacja po merge.

---

# H. Definicja sukcesu reorganizacji

Projekt jest uporządkowany, gdy dla dowolnej widocznej prognozy można odpowiedzieć bez zgadywania:

1. Skąd pochodzi fixture?
2. Jak zidentyfikowano obu zawodników?
3. Jakie dokładnie mecze historyczne weszły do obliczenia?
4. Ile mają dni i z jakiego są sezonu?
5. Na jakiej były nawierzchni i poziomie rozgrywek?
6. Jak silni byli przeciwnicy?
7. Które wartości są RAW, które opponent-adjusted, które State, a które DNA?
8. Który model stworzył probability?
9. Czy i jak probability zostało skalibrowane/połączone?
10. Dlaczego konkretny market jest albo nie jest ready?
11. Jak Symfonia utworzyła kompozycję i joint probability?
12. Jaki dokładnie rynek/linia/kurs pochodzi z Superbet?
13. Dlaczego coś stało się PLAYABLE?
14. Jak iNeed$ policzył EV/risk/stake?
15. Co dokładnie wyświetla frontend i z którego pola backendu?
16. Jak prediction został zamrożony i później rozliczony?

Jeżeli na którekolwiek pytanie odpowiedź brzmi „chyba”, „fallback”, „stary guard” albo „tak wyszło ze średniej”, ten fragment systemu nie jest jeszcze uporządkowany.