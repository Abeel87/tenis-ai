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

**Status:** COMPLETE - approved SHADOW/audit observability scope merged and post-merge verified through PR #412.

**Canonical semantic owner:** `backend/readiness_engine_shadow.py`.

**Canonical consumer inventory:** `TENIS_AI_READINESS_CONSUMER_MAP.md`.

**Canonical phase-3 requirement matrix:** `TENIS_AI_READINESS_REQUIREMENT_MATRIX.md`.

**Canonical phase-4 delivery audit:** `TENIS_AI_READINESS_DELIVERY_AUDIT.md`.

Phase 1 reports deterministic reason codes and `READY / NOT_READY / UNKNOWN` beside legacy `model_ready`. Coverage without an approved sufficiency policy remains `UNKNOWN`; a hard missing required input under an existing contract may be `NOT_READY`. Legacy `model_ready` remains observational/read-only for the SHADOW engine.

Market/family readiness may be `READY` only through an existing explicit contract such as PBP `market_evidence_v940`. PBP `market_ready`, Symphony `learning_model_ready`, and Superbet operator availability are separate contracts and must not be collapsed into one overall readiness flag.

Phase 2 is complete in PR #403: 21 exact-token source files are frozen/classified in `TENIS_AI_READINESS_CONSUMER_MAP.md` and contract-tested with zero runtime wiring. Phase 3 maps 22 exact legacy tokens on 19 consumer source lines to consumer-specific requirements, evidence owners, UNKNOWN/missingness semantics and behavior-change risk. No runtime/learning gate is approved for replacement. AutoLearn/specialist/history-learning consumers are deferred to LOGIC-09; the prediction-integrity guard is deferred to LOGIC-10.

The first selected observability path R12/R13 is merged and verified: additive SHADOW-labeled aggregate/meta telemetry sits beside unchanged legacy `meta.model_ready` in `backend/update.py`. Exact snapshot delivery is proven; projection consumes only an already-published sidecar through the canonical helper after `results.json` is written. Stale/missing/misaligned/non-isolated evidence is N/D, never zero. R18/R19 are merged and post-merge verified in PR #412: admin/diagnostic UI displays backend-owned SHADOW tri-state counts only, or explicit N/D when the metadata projection is unavailable. Moderator filtering R16 remains explicitly out of scope. Legacy `model_ready` cannot be removed while any audited consumer still depends on it.

Phase 4 defines the exact-snapshot observability join contract in the canonical SHADOW owner. `backend/snapshot_digest.py` owns deterministic `canonical-json-sha256-v1`. The generic history-coverage owner is unchanged: Point Tape regenerates coverage from restored cache, then stamps only that run-local report with the exact current `results` digest before semantic readiness consumes it. `readiness_engine_shadow` rejects history evidence unless the stamped digest matches the current results snapshot, and `observability_snapshot_alignment()` rejects any stale/missing contract. This eliminates the observed false-positive where counts/IDs matched across different data snapshots without changing identity/history semantics. A semantic aggregate is eligible only when report status is ready, current/readiness/history digests align, Player State aligns, and legacy Current Engine mismatches are zero. Missing/mismatched evidence is unavailable/N/D, never inferred READY/NOT_READY or zero. The sidecar delivery path is now live SHADOW evidence; only the explicitly approved R12/R13 metadata projection consumes it.

Phase 4 audit is merged via PR #408 (final head `cccac2993ed05dd8fb75a4f9b57328dda2d12bd9`, merge `4d626b2bd59f454773b350766f8207567460d07b`). Exact-head Point Tape `35446260835` and artifact `10586677424` independently verified equal current/history/readiness digest `79645fe3f81bc628b7152f1597811a09f1d5dc3c29bce3bbde2c0a15f6a7d3bd`, aligned Player State/history evidence and zero legacy-reference mismatches. The separate delivery implementation PR #410 final head `ddb040f144c75b9fbee0a984b72c553a42fd2aa6` merged as `57a49ade723179417cba07e77c791b1e425f38ca`.

Producer-host implementation is now proven in the existing `Player DNA SHADOW refresh`. Exact PR run `35450914610` passed on PR #410 with restored real cache and independently verified artifact alignment/isolation. Post-merge main run `35453848556` completed SUCCESS through publish and FAST Pages dispatch. Its bot publication commit `3185ba47eb0a869ed09fd36a4cb188c6279f150b` changed only the expected Player DNA SHADOW payloads plus `frontend/data/readiness_engine_shadow.json`; it did not retrigger Update-and-Pages. No new parallel workflow exists.

The published current sidecar is exact-snapshot aligned for 109 matches at digest `79645fe3f81bc628b7152f1597811a09f1d5dc3c29bce3bbde2c0a15f6a7d3bd`, with history and Player State alignment true, zero legacy-reference mismatches, `network_calls=0` and all isolation flags false. R12/R13 therefore have the required delivery evidence. Their implementation is telemetry-only: `backend/update.py` projects already-published evidence into `meta.semantic_readiness_shadow`, while `meta.model_ready` and every runtime/learning gate remain unchanged. PR #411 merged this path as `0f200405f884389404d351a9264a534c7f78b00e`. Post-merge Update run `35462310243` completed SUCCESS and bot commit `4911831dd6970486b6025b7cae6b893737c21047` published 115 visible matches with legacy `results[].model_ready=true == meta.model_ready == 44`; semantic readiness correctly failed closed as `N/D / RESULTS_SNAPSHOT_MISMATCH` because the prior sidecar covered the earlier 109-match snapshot. R18/R19 consume only this metadata surface and do not read or recompute the sidecar in the browser. A subsequent concurrent case further proved the boundary: Superbet refreshed `results.json` while Player DNA run `35463366219` was executing, then the Player DNA publisher rebased its SHADOW sidecar onto newer main. The sidecar's own exact digest no longer matched live results, and `meta.semantic_readiness_shadow` remained N/D. Sidecar workflow success therefore does not imply live-current telemetry; only the exact-digest meta projection is authoritative for R18/R19 observability.

Final LOGIC-08 closeout: PR #412 final head `4a6895672fa3783c18015470f8c8ade6c3373155` merged as `f9c4f000600e4b24c863488fdf9814f3d6a968d6`. Post-merge Fast frontend deploy `35495378715`, Delivery/Security `35495378694`, CodeQL `35495378755` and UI/Project Health `35495378723` all completed SUCCESS. The browser remains presentation-only: it does not compute readiness, infer an overall-ready count, change R16 filtering or affect any model/learning/PLAYABLE path. Runtime/learning consumers R07/R08/R11 remain deferred to LOGIC-09; prediction-integrity guard R14 remains deferred to LOGIC-10.

Zero probability, threshold, weight, training, PLAYABLE or iNeed$ influence.

---

## LOGIC-09 ? Learning Integrity / Prediction Ledger

**Status:** PHASES 0-3 INFRASTRUCTURE MERGED + POST-MERGE VERIFIED; prospective exact common-set evidence collection is active. Common binary settled sample is still `n=0`. No telemetry/weight/learning/runtime migration is approved.

Phase-0 merge evidence: PR #414 final head `8532212b0a3292112dc33ae6ec052d766b5058d7` merged as `d589b7204098fe285fe30ec66fbd6be96ee3f5a8`; docs closeout PR #415 merged as `8cf20c7fd0249c84c64e6bdb87979b5db0b3197f`. Phase-0 proved unequal historical populations and froze the prospective ledger/common-test-set contract.

Phase-1 merge evidence: PR #416 final head `ef2c46956c3a43afdb85ba0626d9634f63cec592` merged as `039740786ae7026980fa0931465d03e632450879`. Canonical owner `backend/prediction_ledger_shadow.py` captures the first immutable pre-selection Current/CatBoost/TabPFN snapshot for every supported prospective candidate. The source ledger is append-only, population `ALL`, and remains disconnected from runtime/learning/telemetry gates.

Phase-2 audit PR #418 merged as `fe368f7308ef667be90fecb1c7dff09d47cca626`. It proved the legal downstream ownership contracts: PLAYABLE through exact `backend/superbet_playable.py` frozen signatures + pre-match chronology, Symphony through exact `backend/symphony2_tracker.py` selection/composition identity + pre-match chronology, and iNeed$ remains `N/D` because no local prospective placement owner currently proves exact match identity plus pre-match placement time. Missing evidence is `N/D`, never inferred `false`.

Phase-2 implementation PR #419 merged as `480994ef0ba3beae3358e91bb9ee41e75b5d3ae5`. Canonical additive owner `backend/prediction_ledger_selection_shadow.py` publishes `frontend/data/prediction_ledger_selection_shadow.json` after final PLAYABLE/Symphony freezing. Normal Update run #808 completed SUCCESS through final regression and Pages; bot publication moved main to `0bb7613322ce77bfafcb551bcb7dcb960fd6dda0`.

Published phase-2 evidence at that main: `ALL=2143`, exact positive `PLAYABLE=443`, exact positive `SYMPHONY_SELECTED=2`, exact three-model common Current+CatBoost+TabPFN intersection `187`, common+PLAYABLE `73`, common+Symphony `2`, common+both `2`; iNeed$ remains `N/D`. No model, PLAYABLE, Symphony, settlement, telemetry, dynamic-weight or iNeed$ calculation was changed.

Phase-3 audit identified the existing canonical settlement owners instead of creating a parallel rule set. `backend/live_history_settle.py` owns terminal match evidence and provenance in `frontend/data/history.json`; `backend/signal_settlement.py::settle_signal_live` owns market-specific hit/miss/void/unverifiable semantics. `game_state` deliberately remains unverifiable from final set scores. The phase-3 consumer must make zero network requests and must not mutate either owner or the immutable prediction ledger.

Phase-3 implementation PR #420 merged as `bf959fa23f83025851a5b6db8a329d6443836547`. Canonical additive owner `backend/prediction_ledger_settlement_shadow.py` publishes `frontend/data/prediction_ledger_settlement_shadow.json`. The legal join contract is unchanged: exact numeric `id:<Live Tennis match_id>`, exactly one matching history row, exact scheduled-time agreement, terminal history state, valid post-start `settled_at`, settlement source/version provenance and the canonical existing scorer. Any mismatch/ambiguity/missing provenance is `N/D`; no names, nearest time/line, provider conversion or post-start reconstruction is allowed.

Frozen real-snapshot proof on base main `0bb7613322ce77bfafcb551bcb7dcb960fd6dda0`: ledger rows `2143`; exact history match keys `1486`; common Current+CatBoost+TabPFN rows `187`; exact PLAYABLE rows `443` with `73` common; exact Symphony rows `2` with `2` common. At audit time all prospective settlement rows are still `N/D` (`hit=0`, `miss=0`, `void=0`) because the young prospective ledger has not yet matured into canonical settled history. This is expected fail-closed behavior, not a missing-data backfill target.

Post-merge Update #809 completed SUCCESS with canonical settlement #25 GREEN; selection sidecar #67/#68 GREEN; settlement common-set #69 GREEN; dedicated settlement guard #70 GREEN; Symphony guards #71/#72 GREEN; final full regression #75 GREEN; JSON commit #77 GREEN; Pages upload/deploy GREEN. Bot publication produced main `a3c9b6e8338e3fa5ca3da7edd432700e720e74bf`; later `e2d6a124325e449535c191abdd8a2feb3842e04a` changed generated data only and did not touch Prediction Ledger owners or sidecars.

Published phase-3 evidence: schema `prediction-ledger-settlement-shadow-v1`, mode `SHADOW_ONLY`, rows `2460`, exact history match keys `1488`, exact three-model common Current+CatBoost+TabPFN rows `220`, settlement results `hit=0`, `miss=0`, `void=0`, `N/D=2460`, common binary settled `0`, common void `0`, status `NO_SETTLED_COMMON_ROWS`. Population reports: `ALL rows=2460/common=220`; exact `PLAYABLE rows=585/common=83`; exact `SYMPHONY_SELECTED rows=2/common=2`; exact `PLAYABLE_AND_SYMPHONY rows=2/common=2`; all have common binary settled `0`.

Published isolation remains explicit: `network_fetch_enabled=false`, `source_ledger_mutated=false`, `production_influence=false`, `runtime_gating_enabled=false`, `learning_consumer_enabled=false`, `telemetry_consumer_enabled=false`, `auto_promote=false`.

Common-test metrics may be reported only on exact prospective rows with all three frozen model scores and canonical `result in {hit, miss}`. `void` remains auditable but is excluded from binary accuracy/Brier/log-loss. Populations remain separate (`ALL`, exact `PLAYABLE`, exact `SYMPHONY_SELECTED`, exact intersection; generator/iNeed remain unavailable until their own exact owner evidence exists). Phase-3 explicitly disables model ranking, winner selection, auto-promotion, telemetry consumers, learning consumers and runtime gating. No minimum sample or promotion threshold is invented in this phase.

**Current gate:** evidence maturity only. Allow normal prospective matches to mature through the existing settlement owner. If `common_binary_settled` remains `0`, do not add code to force it. When exact common `hit/miss` rows appear naturally, report factual coverage/Brier/log-loss/accuracy separately by population. Do not rank/promote models or migrate telemetry/weights merely to create a sample.

---

## LOGIC-10 - Guard Ownership Audit

**Status:** COMPLETE - PR #422, #423 and #424 merged. Phase-3 PR #424 merged as `2b81e589e3d9f78db31d7f41b2959f091fc4bc1c` after exact-head all-green CI, `BAD_OR_PENDING=0`, PR base equal to main and MERGEABLE state. Post-merge Delivery/Security and UI Health are GREEN. Final Player DNA SHADOW completed SUCCESS 34/34 and published `e17e4c4ac37f15d79d5c2c4398ed00d513614c20`. Subsequent Update/Neuron/Superbet generated-data commits advanced main to `a329444df36968a48aa92ce2e3d26ae1dea011e6`; Runtime Private and Fast frontend deploy on `a329444d...` are GREEN.

Canonical audit artifact: `TENIS_AI_GUARD_OWNERSHIP_AUDIT.md`. The exact active named workflow inventory is enforced by `tests/test_guard_ownership_audit_contract.py`.

**Phase 1 / BO5:** `backend/model.py` is the Current Engine owner of legal format-aware BO5 full-match output. Legacy `backend/prediction_integrity_v78a.py::apply_pre_output_guards()` erased legal BO5 match fields. PR #422 removed the destructive rewrite and replaced it with structural BO5 score-space validation; Market Lab remains `LAB_SET1_ONLY`; Serve Props remains BO5 `ready=false` with `bo5_full_match_not_supported`. PR #422 merged as `aada53ad...`; post-merge Update #65 Prediction integrity #20, final regression #75, JSON publication and Pages deploy all GREEN.

**Phase 2 / presentation guard ownership:** five historical commands (`verify_v84d1.py`, `verify_v84d2.py`, `verify_v84e11.py`, `verify_v853_runtime_ui.py`, `verify_v87_decision_center.py`) were compatibility aliases of one canonical owner: `scripts/verify_ui.py::main()` -> `tests/ui_static_smoke.mjs`. PR #423 removed fake distinct workflow ownership while retaining real boundary checks: one canonical UI presentation guard in Update, dedicated Decision Center smoke, canonical revalidation after prune/compaction, and the real `tests/match_time_smoke.mjs` owner. Wrapper files remain only for compatibility. Phase-2 focused pack 19/19 GREEN and full local suite 1345/1345 GREEN.

**Phase 3 / semantic closeout:** the two direct `backend/player_dna_market_walk_forward.py` workflow executions were renamed from `Validate...` to `Build ... evidence`, because the module writes SHADOW walk-forward/phase-7 evidence. Execution, training, probability and output math are unchanged. Contract tests freeze all 52 inline Python guard/validation blocks as read-only and prevent named guard/validator steps from directly executing this producer. `Central API Quota Guard` remains the intentional stateful exception because `backend/api_quota.py` owns shared quota state/report consumed by update/history/PBP. Active named guard/validation inventory is 92 across 28 workflows. Phase-3 focused pack 24/24 GREEN; full repository suite 1349/1349 GREEN. Exact-head PR checks including Player DNA SHADOW and Point Tape all completed SUCCESS before merge.

**Operational note outside LOGIC-10:** Training Archive HTTP 500 is the known 250 MB budget-gate rejection and remains separate from guard ownership. Runtime Private later returned to SUCCESS. Do not reopen LOGIC-10 for archive budget/retention or transport-service issues unless direct code evidence links them.

---

## LOGIC-11 - Frontend Ownership + Provenance

**Status:** COMPLETE - phases 1-7 merged through PR #432. Phase 7 merge `5ad329b0f08688bf3d2b2d32df124b0f9e71dccf`; exact-head required CI 10/10 GREEN; post-merge Update+Pages #815 and Pages deploy GREEN.

**Confirmed runtime owners:** `scripts/build_delivery.mjs` produces delivery; `frontend/presentation-data.js` is the application data/presentation entry point; `frontend/app.js` owns shell/list/detail routes; `runtime-data-transport.js` wraps reads without changing presentation ownership; `history-ui.js`, `admin-users.js` and `ineed.js` are explicit feature owners.

**Merged evidence:** PRs #426-#432 removed frontend probability synthesis, fake-zero missingness, noncanonical route/player/H2H identity fallbacks, client-clock publication provenance, ghost retired-owner references, unlabeled SHADOW presentation, and active boot/cache/VM loading of six no-consumer calculation helpers. Current UI fails closed on missing/ambiguous identity and leaves unavailable data as N/D.

**Phase-7 production proof:** focused provenance/ownership pack 30/30 GREEN and full local repository 1353/1353 GREEN before publication. PR #432 exact-head 10/10 GREEN. Post-merge Update+Pages #815 passed Canonical UI presentation guard, Symphony 2.0 Guard, final PLAYABLE publication Guard and Final full regression v9.3.3, then committed refreshed JSON, built lazy delivery and deployed Pages. Subsequent `data: refresh tennis analysis` and `data: refresh Superbet market context` publications preserved the line; Runtime Private and iNeed$ SHADOW are GREEN on current `2db38c03...`.

**Contract:** displayed fields retain explicit provenance classification (RAW / MODEL / CALIBRATED-ENSEMBLE / SHADOW / SYMPHONY / SUPERBET / PLAYABLE / iNeed$ / SETTLEMENT). The browser must not fabricate probability, H2H, odds, identity, missing counts or publication time.

---

## LOGIC-12 — iNeed$ Bet Builder Redesign SHADOW

**Status:** ACTIVE - phases 1-6, shared-exposure read/accounting/presentation, the dormant SHADOW reservation writer, and the canonical exact Bet Builder quote artifact are merged. PR #455 merged the read-only quote artifact as `033227f670d46c53b6f4dbdd7e3822fe5d91a6e1`. The active bounded step is an ephemeral Phase-4/5 SHADOW producer inside the existing scoped runner. The writer remains disabled by absent experiment config and has no runtime caller; one-ticket builder settlement remains `NOT_IMPLEMENTED`, and real-money execution remains disabled.

**Current production owner/economic unit:** `backend/ineed_scoped_runner.py` + `backend/ineed_money.py` remain the current single-leg V1 path. Existing V1 calculations, persistence, sync and settlement are unchanged.

**Target unit:** one final same-match Bet Builder composition with canonical `composition_id`, at least two legs, upstream Symphony joint probability, exact verified Superbet combined price, builder-level EV/exposure/stake, one bankroll reservation and one-ticket settlement.

**Combined-price rule:** never multiply same-match leg odds to synthesize a builder price. Exact operator combined quote or N/D / NO BET only.

**Isolation rule:** LOGIC-12 remains additive SHADOW/DRY_RUN. Do not change Current Engine math, Symphony probability, PLAYABLE, existing single-leg iNeed$ calculations, settlement behavior, SHADOW->PROD state or execute real-money bets.

**Phases 1-3:** `backend/ineed_builder_shadow.py` owns canonical composition + exact combined-price provenance. Phase 2 proves exact pre-priced `superbets` rows; phase 3 proves read-only arbitrary exact composition pricing through Superbet `v2/getSgaOddPrice`. PR #436 merged as `05e818d4ed599dfee5cb82d90298cb547872b787`.

**Phase 4:** `evaluate_builder_economics_shadow()` is pure whole-builder economics. It consumes upstream joint probability unchanged + exact verified operator combined price, reuses existing V1 tax/risk semantics without changing V1, emits only `SHADOW_QUALIFIED/SHADOW_REJECTED`, and creates at most one nonpersisted `SHADOW_PROPOSED` reservation for the whole composition. PR #437 merged as `9a0ad2fe84298e847a2af7a6bc5afabdafee6963`; local validation before merge was focused 27/27, broad 371/371, full 1388/1388 GREEN.

**Phase 5:** `backend/ineed_builder_ticket_shadow.py::build_builder_ticket_shadow()` is the canonical pure ticket-envelope owner. It accepts only a matching exact composition + Phase-4 `SHADOW_QUALIFIED` economics with exactly one whole-builder reservation, then freezes exact legs, match/player identity, joint probability, combined price, exact Superbet event/SGA/component/source provenance, economics snapshot and reservation proposal into deterministic `builder-ticket:<composition_id>` output. It fails closed on any identity/economic/provenance mismatch and deep-copies evidence.

**Phase-5 safety contract:** `status=SHADOW_TICKET_PROPOSED`, `economic_unit=BET_BUILDER_COMPOSITION`, `runtime_publishable=false`, `persistence_ready=false`, `settlement_ready=false`, `settlement_contract_status=NOT_IMPLEMENTED`, `automatic_real_betting=false`. The ticket has no V1 `signal_id`, fingerprint, single-market selection/outcome or payout semantics. The scoped runner may construct it only as ephemeral SHADOW evidence; it is not included in the V1 Edge sync payload, is not persisted by Supabase, is not consumed by frontend or settlement, and remains `runtime_publishable=false`.

**Phase-5 merge proof:** exact head `ac9d6d024336aa9f0fa56c155020959e13e09769` passed 8/8 GREEN workflows (LOGIC-01/02/03/04, iNeed$ SHADOW, Delivery/Security, CodeQL, UI/Project Health) and merged via PR #438 as `73926853e4439f41a97c08ffd4be93f55e16c24f`. Local validation: focused 38/38, broad 410/410, full 1399/1399. Post-merge grep shows no runtime/frontend/workflow/Supabase consumer; current `ineed-sync` and settlement runner blobs are unchanged.

**Phase-6 runtime proof:** repository plus live Supabase read-only audit confirms V1 is single-leg at every persistence boundary: signal fingerprint identity, `signal_id UNIQUE` bet ownership, `QUALIFIED` auto-placement, single-leg insert guard, V1-only exposure accounting and one-bet settlement. The deployed `ineed-sync` v10 persistence core matches this contract.

**Phase-6 persistence contract:** future builder persistence is a separate experiment-scoped logical object keyed by deterministic `builder-ticket:<composition_id>` plus immutable `ticket_digest`. Exact replay returns idempotent success; same identity with different immutable evidence fails closed. No builder object may become a fake V1 signal/bet or use current V1 statuses to imply unimplemented semantics.

**Shared-bankroll read-side:** the deployed `ineed_open_risk_exposures` source now accounts for V1 open bets and future `SHADOW_RESERVED` builder owners in placement, admin-start, settlement bookkeeping, Edge state and staff presentation. Builder reservation writes remain disabled because the deployed reserve RPC has no caller and the active experiment lacks the required enable flag/version; builder settlement is still unimplemented.

**Source-parity step:** deployed `ineed-sync` v10 contains SMTP/email source changes absent from pre-Phase-6 Git: env aliases/fallback sender selection, explicit configuration-state detail and `operator_event_url` email metadata. The active source-parity branch copies those already-live semantics into Git only; no Supabase deployment is part of this step.

**Phase-6 local proof:** focused persistence/V1-isolation/Phase-5/docs pack 30/30 GREEN, full repository pytest 1405/1405 GREEN, UI static smoke PASS, Project Health 0 FAIL / 1 existing WARN and clean `git diff --check`; audit changes only docs plus a contract/isolation test.

**Phase-6 merge proof:** PR #440 exact head `96b248b1c8aebe5d161976c29d5f02b0e80d9b6f` passed 7/7 GREEN workflows and merged as `5fd2d45d1c8b55d663e2a05f181a48e7d3e80ace` after fresh-main equality.

**Source-parity local proof:** deployed-v10 markers + V1 isolation tests 22/22 GREEN, full repository pytest 1408/1408 GREEN, UI static smoke PASS, Project Health 0 FAIL / 1 existing WARN, Deno type-check GREEN and clean `git diff --check`; no Supabase deployment executed.

**Source-parity merge proof:** PR #441 exact head `b9755be1c7248f389dcb646108cedccb5f079269` passed 8/8 GREEN workflows and merged as `54c0c84e1e37fc8905a26993b1464ee1d6d4d48e`; post-merge live Supabase remained ACTIVE `ineed-sync` v10 with unchanged deployment metadata, so no Edge deployment occurred.

**Shared-exposure audit:** current V1 available capital comes from latest ledger balance while all open concentration/exposure comes from `ineed_shadow_bets`. Phase-4 builder economics can model proposed builder exposure only ephemerally inside one evaluation call. The future logical interface therefore keeps `open_bets` V1-only and introduces a separate normalized `risk_exposures` view across V1 single bets + builder compositions. Builder stake counts once for total/match/player and once per distinct constituent market for market concentration.

**Shared-exposure local proof:** focused shared-exposure/V1/builder/settlement/source-parity/docs pack 47/47 GREEN, full repository pytest 1413/1413 GREEN, UI static smoke PASS (389 current matches / 103 Symphony), Project Health 0 FAIL / 1 existing WARN and clean `git diff --check`; audit changes only docs plus a contract/isolation test.

**Shared-exposure merge proof:** PR #442 exact head `673df0e8c6c303e28876b6e5ade9d2f8478a0c88` passed 7/7 GREEN workflows and merged as `f21e6e5a0da796bac7e21a91b8feb1606eb3b24e` after fresh-main equality.

**Normalized risk read model:** `backend/ineed_money.py` is the canonical owner of `risk_exposures`. With no explicit `risk_exposures`, current runtime V1 `open_bets` are normalized to `V1_SINGLE_BET` and current decision semantics are preserved. Explicit read-only state may contain `V1_SINGLE_BET` + `BET_BUILDER_COMPOSITION`; `backend/ineed_builder_shadow.py` consumes the same normalized owner. `open_bets` remains V1 settlement-only.

**Read-model safety:** builder-shaped V1 `open_bets` fail closed; explicit V1 rows require one market and no composition identity; explicit builder rows require composition identity, two players and constituent markets. Supabase/Edge are unchanged and do not emit `risk_exposures`; no durable builder exposure or ledger reservation is created.

**Read-model local proof:** deterministic old-vs-new V1 comparison 500/500 identical; focused implementation pack 46/46 GREEN; focused + docs 59/59 GREEN; full repository pytest 1426/1426 GREEN; UI static smoke PASS (389 current matches / 103 Symphony); Project Health 0 FAIL / 1 existing WARN; `git diff --check` clean. After data-only main drift to `f8174f53a9a8f8f88c304af356ae89d5a2536f44`, the branch was rebased and the full pytest/UI/health gates passed again. Live Supabase contains 0 builder-shaped rows in `ineed_shadow_bets`.

**Read-model merge proof:** PR #443 exact head `850c48a8b662a897aa88b0303688bbd20851216d` passed 8/8 GREEN workflows, fresh main remained `f8174f53a9a8f8f88c304af356ae89d5a2536f44`, and merged as `8666d37e41b79d959d1be9c9d5846a9289cbb979`. Post-merge `ineed-sync` remained ACTIVE v10 with unchanged source hash and no Supabase deployment.

**Atomic reservation audit:** current V1 place + settle RPCs serialize bankroll mutation through the same experiment-row `FOR UPDATE` lock. A future builder reservation must use this same mutex and cannot be enabled until one shared DB exposure source is also used by V1 placement and `ineed-sync`; otherwise V1 could ignore open builder exposure and over-allocate.

**Atomic physical design:** one `ineed_builder_tickets` table is the immutable ticket/exposure owner; the existing `ineed_bankroll_ledger` stays the only ledger; `ineed_open_risk_exposures` is the normalized source spanning V1 open bets with builder `SHADOW_RESERVED` owners. The atomicity design remains owner + exactly one `STAKE_RESERVED` debit under the experiment lock or neither.

**Atomicity-audit merge proof:** PR #444 exact head `b9ef35874f2cbd1ca92468abd140507d6441d2e9` passed 8/8 GREEN workflows on fresh base `b1b3eb22fb827e83bd36f20e8562a18d84e6c6e1` and merged as `6f0fa7b204b232e398cf095e2e85b0017206f102`. Live `ineed-sync` remained ACTIVE v10 with unchanged source hash; no Supabase deploy occurred.

**Shared-DB schema merge history (originally dormant; deployed 2026-09-21):** `supabase/migrations/20260921084010_ineed_builder_shared_exposure_dormant.sql` defines the builder owner, generated ticket/reservation identities, DB-owned `pgcrypto` SHA-256 digest, ledger `builder_ticket_id` ownership constraints/uniqueness, RLS and service-only `security_invoker` view. PR #445 merged it as `ab2d1034f8e34539fc1d905f95205567915f86bb`; no live DDL or Edge deployment occurred.

**Status namespace correction:** builder open exposure uses `SHADOW_RESERVED`; V1 remains `PENDING` / `SHADOW_PLACED`. This prevents builder persistence from impersonating V1 state without altering current V1 runtime calculations.

**Dormant-schema local proof:** live read-only compatibility shows PostgreSQL 17.6, `pgcrypto` in schema `extensions`, immutable `digest(text,text)`, and 35/35 existing `STAKE_RESERVED` rows owned by V1 `bet_id`. Migration parses as 14 PostgreSQL statements; focused schema/risk/builder/audit pack 41/41 GREEN; full iNeed pack 109/109 GREEN; full repository pytest 1442/1442 GREEN; UI static smoke PASS (377 current matches / 101 Symphony) after data-only rebase to `9fd45f4938413f4e81bb9c701d3a6077ce75bf7d`; Project Health 0 FAIL / 1 existing WARN. The equivalence test covers 250 deterministic V1 view-vs-backend states. No live DDL has been executed.

**Shared-reader merge proof:** `supabase/migrations/20260921091005_ineed_shared_exposure_readers.sql` moves V1 placement total/match/player/market exposure queries to `ineed_open_risk_exposures`; repository `ineed-sync::activeState()` reads the same view for `risk_exposures`/equity while keeping `open_bets` V1-only for settlement. PR #446 exact head `699076da8144c40549a2f36d7287f947954acea1` passed 8/8 GREEN and merged as `979d4b3238ab7458e870145af5f6d4bbdd2cc184`. Live Edge remains v10 and no live DDL was executed.

**Admin-start merge proof:** `supabase/migrations/20260921093354_ineed_admin_start_shared_exposure.sql` changes only the previous-experiment open exposure read in `ineed_admin_start_experiment()` to `ineed_open_risk_exposures`. PR #447 exact head `8e5be0747fc7dc68759cd6a8f086219b9de0f597` passed 8/8 GREEN and merged as `59ec7d99cadd95ce6cea545f6db6a888ed644f1c`; no live DDL or Edge deploy occurred.

**Settlement merge proof:** live read-only function definition proved production `ineed_system_settle_bet()` already locks the target V1 bet and owning experiment row `FOR UPDATE`, while historical Git migration `20260910221444_ineed_v1.sql` lacked the experiment lock. `supabase/migrations/20260921095220_ineed_settlement_shared_exposure.sql` preserves that live mutex and all V1 outcome/payout/ledger/status semantics while changing only `other_exposure` to the shared view. PR #448 exact head `9f24dd9071375a4eb6506d2c37609354bd5bfc37` passed 8/8 GREEN and merged as `03cb21f741d5621c8851ebed692a8443f0562b8f`; no live DDL or Edge deploy occurred.

**Frontend shared-exposure merge proof:** `supabase/migrations/20260921101354_ineed_staff_exposure_summary.sql` adds a staff-authorized aggregate RPC over service-only `ineed_open_risk_exposures`; `frontend/ineed.js` uses it for exposure/equity/open-unit presentation and accepts V1 fallback only when the RPC is absent (`PGRST202` / `42883`). PR #449 exact head `81bff0eaeca09e25295a6d678d0944cc8327d6de` passed 8/8 GREEN and merged as `5e2f008bafc516ccc47ac79a9844b46c98a71281`; no live DDL or Edge deploy occurred.

**Deployment closeout:** PR #450 exact head `345cf2245748a23be513f2bc02ff50d9feaca1e5` passed 7/7 GREEN and merged as `8f6795e4670b32f601f04e8822a4dc40875e4d6f`. Production then received the five reviewed shared-exposure migrations in dependency order plus advisor-driven `ineed_builder_ticket_fk_index`. `ineed-sync` is ACTIVE v11/hash `5e6cd2eea5937fd66de98754dbd40afe2906f6d70fbe5588116f218ef45c673f`; normal SHADOW workflow run `35596941111` passed guard, settlement and scoped sync on `main`.

**Live V1 proof after rollout:** 41 real scoped evaluations were processed, all `REJECTED`, with `0` placed; `active_exposure=0`, `open_bets=[]`, `risk_exposures=[]`, available/equity `191.2532 PLN`, and `automatic_real_betting=false`. Staff aggregate returned `source=SHARED_DB` with zero V1/builder units. Email non-regression remains live: 36 historical events are `SENT` with provider IDs, zero events are pending/failed, and no synthetic email was generated during rollout.

**Advisor closeout:** the post-DB unindexed-FK finding for `builder_ticket_id` was fixed by `20260921115606_ineed_builder_ticket_fk_index.sql`. Remaining new `unused_index` INFO is expected with zero builder rows. Service-only RLS/no-policy and authenticated staff-summary SECURITY DEFINER findings are intentional and explicitly reviewed against ACL + internal `is_staff(auth.uid())` guard.

**Writer boundary:** shared read-side and dormant reserve RPC are deployed and verified. Live migration `20260921134348 ineed_builder_reservation_writer_shadow` installs the service-role-only RPC using the experiment mutex, immutable DB digest, shared exposure caps and one owner + one ledger debit transaction. It has no Edge/workflow/frontend caller and requires explicit `builder_reservation.enabled=true` plus matching contract version; the active production experiment has no such config block. Builder settlement remains `NOT_IMPLEMENTED`, and real-money execution remains disabled.

**Caller/enablement audit progression:** PR #453 deployment closeout is merged and the live writer stays disabled. PR #455 then added the canonical read-only exact-builder-quote artifact in the Superbet refresh path. The current bounded owner is `backend/ineed_scoped_runner.py`: it may read the frozen published Direct snapshot plus the aligned exact quote artifact, call the existing pure Phase-4/5 functions, and emit only ephemeral SHADOW composition/evaluation/ticket evidence. V1 `evaluations`/`settlements`, Edge sync, email behavior, reservation RPC caller/flag, builder settlement and real-money execution remain unchanged/disabled.


**Exact quote artifact merge proof:** PR #455 exact head `c03c8930660fdb2eac87f263d6fa8c314df5dedc` passed the exact-head CodeQL, Delivery/Security, UI/Project Health and Superbet refresh checks and merged as `033227f670d46c53b6f4dbdd7e3822fe5d91a6e1`. `frontend/data/superbet_builder_quotes_current.json` is owned by the canonical Superbet refresh path, accepts only exact operator pre-priced combination rows, freezes component/operator/event/timestamp provenance and fails closed to an empty safe state on source failure. It never synthesizes a combined price.

**Scoped-producer isolation contract:** the runner-side producer must resolve quotes against the exact published Direct snapshot named by `direct_generated_at`; runtime Direct enrichment is not eligible for builder provenance. Builder output is summarized only in runner logs and is not inserted into the payload sent to `ineed-sync`. Any unexpected builder-producer exception is converted to empty `SOURCE_UNAVAILABLE` SHADOW evidence before the unchanged V1 payload/sync path runs. Therefore builder evidence cannot create V1 signals, V1 email events, builder reservations or settlements, and a builder-local failure cannot block V1 sync.

**Dormant writer implementation:** canonical audit `TENIS_AI_LOGIC12_BUILDER_RESERVATION_WRITER_AUDIT.md`. The RPC accepts only the frozen Phase-5 ticket contract, resolves identical replay as `IDEMPOTENT`, rejects digest drift as `IMMUTABLE_TICKET_CONFLICT`, and never recomputes probability/joint probability/combined odds/EV/Kelly/stake. The frozen stake is only revalidated against current V1 risk caps on `ineed_open_risk_exposures`; if it no longer fits, the transaction fails closed rather than resizing immutable evidence.

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
