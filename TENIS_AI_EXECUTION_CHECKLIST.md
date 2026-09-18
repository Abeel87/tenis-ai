# Tenis AI — execution checklist i checkpoint pracy

Status: **KANONICZNA LISTA WYKONAWCZA / PUNKT WZNOWIENIA**

Ten plik odpowiada za:

1. kolejność programu napraw i możliwość odhaczania etapów,
2. jednoznaczny punkt wznowienia po przerwaniu pracy, limicie czatu, zmianie agenta albo przesunięciu `main` przez boty.

Nie wolno zaczynać kolejnego etapu tylko dlatego, że „wydaje się następny”. Najpierw sprawdź ten plik, bieżący GitHub i ostatni checkpoint.

---

## 0. Legenda statusów

- `[ ]` — nie rozpoczęto,
- `[~]` — rozpoczęte / w toku,
- `[x]` — zakończone i potwierdzone dowodem,
- `[!]` — blocker / konflikt wymagający rozwiązania,
- `[S]` — SHADOW/audyt gotowy, ale bez promocji do PROD.

Element wolno oznaczyć `[x]` tylko wtedy, gdy istnieje odpowiedni dowód: commit/PR, test, artefakt audytu, zielone CI albo produkcyjna weryfikacja — zależnie od rodzaju zadania.

---

# 1. LIVE CHECKPOINT — od tego miejsca ma zaczynać kolejny czat

**Ostatnia aktualizacja checkpointu:** 2026-09-18

**Aktywny program:** reorganizacja logiki/danych/modeli Tenis AI

**ACTIVE LOGIC/TASK:** `LOGIC-05 — Opponent Strength Engine`

**SUBSTEP:** skonsolidować istniejący leakage-safe opponent-context challenger jako jednego kanonicznego ownera LOGIC-05 i uruchomić go jako reprodukowalny SHADOW evidence run na aktualnym Player DNA/TML cache. Najpierw dowód i benchmarki, bez promocji do PROD.

**BRANCH:** checkpoint closeout `logic-04-checkpoint-closeout`; po jego merge utworzyć świeży `logic-05-opponent-strength-engine` z ponownie zweryfikowanego `main`.

**PR:** PR #392 zakończony i zmergowany. Dla LOGIC-05 jeszcze brak PR.

**LAST VERIFIED MAIN:** `9c1a8ca7cda5a42d4f079c2c17f6456d67e53929` — botowy `data: refresh Player DNA SHADOW` po pełnym post-merge refresh/Pages LOGIC-04. W momencie checkpointu brak otwartych PR-ów.

**LAST COMPLETED WORK:** `LOGIC-04 — Context Engine SHADOW` zakończony. PR #392 miał finalny head `e4a8d70ef9889a26859ac8414420a47ea10ec0c2`, został przebudowany na świeżym `main` po data-only drift i zmergowany jako `c9acb27e48f41e9a5aaa0fa1bb041c65c5f45ab7`. Context Engine pozostaje wyłącznie opisowym SHADOW/audyt ownerem: strict as-of, fail-closed identity, season buckets, freshness, surface/tour/event provenance, rank context i inactivity gaps bez probability, medycznych inferencji ani runtime wiring.

**CHANGED FILES w PR #392:**

- `backend/match_context_shadow.py`
- `tests/test_match_context_shadow.py`
- `.github/workflows/context-engine-shadow.yml`

**LOGIC-04 EVIDENCE:**

- final PR head: `e4a8d70ef9889a26859ac8414420a47ea10ec0c2`;
- merge commit: `c9acb27e48f41e9a5aaa0fa1bb041c65c5f45ab7`;
- final dedicated workflow: `35304943727` = GREEN;
- artifact: `10531313079`;
- digest: `sha256:99e85d6fb61c9543babb15033efa07c98a0b91aa3b35e4ec1d2a4082fa6c61b7`;
- artifact snapshot: 214 meczów / 428 player-contexts;
- identity resolved: 268 contexts, w tym 261 exact + 7 deterministic expanded; 160 fail-closed;
- history rows użyte przez schema: 3626;
- contexts z pełnym historycznym rank-gap: 3584;
- wszystkie 75 `model_ready` mecze miały oba identity rozwiązane;
- 46/75 `model_ready` miało brak fixture surface; wszystkie te przypadki pozostają `null/missing`, bez inferencji;
- strict same-day protection: TML day-only rows z dnia fixture nie są traktowane jako legalne pre-match history;
- direct-only event metadata: brak event level w źródle => `null/unavailable`, bez zgadywania z tour/name;
- inactivity/gap jest obserwowalnym odstępem czasu, nie diagnozą kontuzji/comeback;
- fixture provider rank jest provenance-only; nie wymyślono effective date ani nie aktywowano go jako Current feature;
- zero Live Tennis API calls, zero production cache writes, zero probability output, zero runtime wiring, zero SHADOW→PROD promotion.

**TEST STATUS:** finalny PR #392: dedicated LOGIC-04 tests 8/8 GREEN, real production TML cache restored, identity/time leakage tests, season/freshness/missing-event/rank-gap/inactivity guards i hard no-probability/no-medical-inference contract = GREEN. Final `Tenis AI UI & Project Health` run `35304943712` = GREEN z pełnym pytest i wszystkimi guardami.

**CI STATUS:**

- final head `e4a8d70ef9889a26859ac8414420a47ea10ec0c2`: LOGIC-04 `35304943727` = GREEN; CodeQL `35304943656` = GREEN; Delivery/Security `35304943669` = GREEN; UI & Project Health `35304943712` = GREEN;
- merge commit `c9acb27e48f41e9a5aaa0fa1bb041c65c5f45ab7`;
- post-merge Update tennis data and deploy Pages `35305172850` = GREEN, w tym full pytest, quota guard, settlement, AutoLearn, SHADOW modules, Surface Elo, Symphony 2.0, final PLAYABLE publication guard, final full regression v9.3.3, data commit i Pages deploy;
- post-merge CodeQL, Delivery/Security/browser/dependencies i Project Health = GREEN;
- botowy Player DNA SHADOW refresh przesunął `main` do `9c1a8ca7cda5a42d4f079c2c17f6456d67e53929` po zakończeniu powyższych gate’ów.

**BLOCKERS:** brak blockerów.

**DO NOT REDO:** nie powtarzać LOGIC-01/02/03/04 bez nowego dowodu, że evidence jest błędne. Nie promować Context Engine do PROD. Nie aktywować fixture rank, freshness policy, population priors ani opponent adjustment na podstawie samych audytów. Nie zgadywać aliasów, event level, surface, kontuzji ani przyczyny inactivity. Nie fabricować Brier/calibration bez uczciwego common ledger — owner LOGIC-09.

**RISKS / HARD BANS:** zero zmian model math, probability, progów, wag, treningu, Current, Player DNA, Surface Elo, Symfonii, Neuronu, PLAYABLE, settlementu, SHADOW→PROD i iNeed$ calculations bez oddzielnej autoryzacji. LOGIC-05 jest evidence/SHADOW only. Brak fuzzy matching, ręcznych aliasów i porównywania provider IDs między namespace’ami.

### Co zakończono wcześniej

- [x] LOGIC-00 — Project Constitution / Operating Contract — PR #384 / merge `5269f6c467c3602fd6d557ed3385bc951008f07d`.
- [x] LOGIC-01 — Freshness Counterfactual — PR #386 / merge `c9292b630c918f7fde0c9c48231629a10819c09f`.
- [x] TASK 019 / PR #383 evidence skonsumowane przez LOGIC-01; #383 zamknięty bez merge.
- [x] LOGIC-02 — Feature Provenance / Ranking Audit — PR #388 / merge `7328c0ec666272abf2a73b3b2a93d06f87d05704`.
- [x] LOGIC-03 — Population / Priors Audit — PR #390 / merge `abc13dd7204f69bcf32160c6e1f533f5e1ccc566`.
- [x] LOGIC-04 — Context Engine SHADOW — PR #392 / merge `c9acb27e48f41e9a5aaa0fa1bb041c65c5f45ab7`.

### NEXT EXACT ACTION

1. Sprawdź ponownie świeży `main`, otwarte PR-y i ostatnie CI; boty mogą przesunąć `main` po tym checkpointcie.
2. Odczytaj `backend/player_dna_opponent_adjustment_audit.py`, `backend/player_dna_point_scorer.py`, `backend/player_dna_shadow_profiles.py`, `backend/player_dna_point_dataset.py`, Context Engine LOGIC-04 i odpowiadające testy/workflowy.
3. Ustal `player_dna_opponent_adjustment_audit.py` jako istniejącego kanonicznego challengera/ownera LOGIC-05; nie twórz równoległego opponent engine, jeśli brak twardego powodu.
4. Utwórz świeży branch `logic-05-opponent-strength-engine` z aktualnego `main`.
5. Najpierw uruchom obecnego challengera na aktualnym, przywróconym cache i zapisz reprodukowalny artifact. Jeśli potrzebne jest workflow wiring, dodaj wyłącznie dedykowany audit workflow, zero PROD wiring.
6. Zweryfikuj strict as-of, same-time leakage, opponent-own-profile semantics i brak użycia przyszłych meczów przeciwnika.
7. Dodaj jawny ranking benchmark jako osobny sygnał porównawczy; nie używaj ręcznego prostego mnożnika rankingu jako definicji strength.
8. Dodaj surface-aware i tour/event context tylko tam, gdzie istnieje twarde provenance; missing pozostaje missing.
9. Zdefiniuj performance-vs-expectation residual jako SHADOW evidence, nie jako nową wagę produkcyjną.
10. Waliduj na chronological holdout + walk-forward; porównaj z istniejącym profile/rank baseline na tej samej próbce.
11. Raportuj Brier/match-equal Brier/log-loss wyłącznie na wspólnym holdout danego audytu; nie utożsamiaj tego z produkcyjnym unbiased ledger LOGIC-09.
12. Hard gate: `candidate_may_replace_reference=false`, `promotion_gate=false` do osobnej decyzji po evidence.
13. PR → artifact → pełne zielone CI → fresh-main check → merge → post-merge verification → checkpoint do LOGIC-06.

---

# 2. Obowiązkowa checklista KAŻDEGO zadania / PR

## A. Start

- [ ] Sprawdź aktualny `main`/HEAD.
- [ ] Sprawdź wszystkie otwarte PR-y związane z tym obszarem.
- [ ] Sprawdź ostatnie workflow/CI i ostatni gate.
- [ ] Przeczytaj `AGENTS.md`.
- [ ] Przeczytaj `TENIS_AI_LOGIC_CONSTITUTION.md`.
- [ ] Przeczytaj odpowiedni wpis w `TENIS_AI_MODEL_DATA_REGISTRY.md`.
- [ ] Przeczytaj `TENIS_AI_EXECUTION_CHECKLIST.md` i `LIVE CHECKPOINT`.
- [ ] Ustal dokładnie jednego kanonicznego ownera błędu/logiki.
- [ ] Potwierdź, że nie istnieje aktywna równoległa implementacja tego samego rozwiązania.

## B. Audyt przed zmianą

- [ ] Odtwórz faktyczne zachowanie z kodu/runtime, nie z pamięci.
- [ ] Zapisz źródła wejściowych danych i provenance.
- [ ] Zapisz konsumentów wyniku.
- [ ] Zapisz guardy/walidatory przed i za modułem.
- [ ] Odtwórz problem testem, raportem lub audytem.
- [ ] Rozdziel: bug implementacyjny / problem danych / problem modelowy / debt dokumentacyjny.
- [ ] Jeśli zakres dotyczy probability/wag/progów/modelu — najpierw SHADOW/counterfactual i osobna autoryzacja.

## C. Implementacja

- [ ] Popraw/utwórz kanonicznego ownera **w miejscu**.
- [ ] Nie twórz nowego `vXXX`, wrappera ani równoległej runtime ścieżki jako obejścia.
- [ ] Nie zmieniaj downstream UI, aby ukryć zły upstream.
- [ ] Zachowaj provenance i reason codes.
- [ ] Dodaj testy regresyjne/leakage.
- [ ] Zaktualizuj registry/architekturę/checklistę, jeśli zmieniła się odpowiedzialność lub pipeline.

## D. Walidacja

- [ ] Testy jednostkowe są zielone.
- [ ] Testy sąsiednich modułów są zielone.
- [ ] Pełny wymagany pytest jest zielony.
- [ ] UI smoke jest zielony, jeśli zakres dotyczy UI/runtime danych.
- [ ] Project Health jest zielony.
- [ ] Security/CodeQL wymagane dla PR są zielone.
- [ ] Brak niezamierzonej zmiany probability/model math/settlement/PROD-SHADOW poza zakresem.
- [ ] Artifact odpowiada rzeczywistemu cache/snapshotowi, nie fixture'om testowym.

## E. Merge

- [ ] PR zawiera wyłącznie zakres zadania.
- [ ] Wszystkie wymagane CI = GREEN.
- [ ] Świeży `main` sprawdzony bezpośrednio przed merge.
- [ ] Jeśli `main` się przesunął — oceń drift; przebuduj/rebase i uruchom CI ponownie.
- [ ] Merge wykonany.
- [ ] Merge commit zapisany w checkpointcie.

## F. Po merge

- [ ] Sprawdź workflow/snapshot na `main`.
- [ ] Potwierdź brak regresji downstream.
- [ ] Odhacz zadanie w programie.
- [ ] Ustaw `NEXT EXACT ACTION` następnego etapu.
- [ ] Zapisz nowy checkpoint przed zakończeniem/przerwą.

---

# 3. PROGRAM GŁÓWNY — lista do odhaczania

## LOGIC-00 — Project Constitution / Operating Contract

Status: `[x] COMPLETED — PR #384 / merge 5269f6c467c3602fd6d557ed3385bc951008f07d`

Cel: jedna prawda o projekcie, jeden sposób pracy, jedna kolejność napraw.

- [x] AGENTS protocol.
- [x] Logic Constitution.
- [x] Model/Data Registry.
- [x] README canonical entrypoint.
- [x] ARCHITECTURE authority order.
- [x] Contract-doc tests.
- [x] Execution checklist + resume protocol.
- [x] Final CI green / fresh-main / merge / post-merge.

**Definition of Done:** spełnione.

---

## LOGIC-01 — Freshness Counterfactual

Status: `[x] COMPLETED — PR #386 / merge c9292b630c918f7fde0c9c48231629a10819c09f`

Cel: ustalić wpływ świeżości na Current player history bez zmiany PROD.

- [x] Baseline TASK 019.
- [x] Scenariusze 30/60/90/120/180/365.
- [x] PBP/Early Hold freshness osobno.
- [x] Zamrożone surface priors dla izolacji efektu historii gracza.
- [x] Profile/model-ready retained-lost + output deltas.
- [x] Brier/calibration `N/A` bez unbiased settled ledger — owner LOGIC-09.
- [x] Zero zmian PROD + CI + artifact.

**Definition of Done:** spełnione; nie wybrano cutoffu „na oko”.

---

## LOGIC-02 — Feature Provenance / Ranking Audit

Status: `[x] COMPLETED — PR #388 / merge 7328c0ec666272abf2a73b3b2a93d06f87d05704`

Cel: znać źródło, wiek i faktyczne użycie ranking features.

- [x] Fixture rank provenance.
- [x] TML `latest_rank` i `opponent_rank` provenance.
- [x] Current-vs-history i age audit.
- [x] Oddzielne counterfactuals fixture rank / historical rank / opponent rank.
- [x] Provenance report per player/match.
- [x] Zero zmian model math i zero promocji.

**Definition of Done:** spełnione.

---

## LOGIC-03 — Population / Priors Audit

Status: `[x] COMPLETED — PR #390 / merge abc13dd7204f69bcf32160c6e1f533f5e1ccc566`

Cel: sprawdzić mieszanie ATP/WTA/Challenger i wpływ globalnych priors.

- [x] Zmierzyć current `_surface_priors` per surface.
- [x] Rozbić priory na ATP / CH / WTA.
- [x] Zmierzyć różnice hold/break/serve/return.
- [x] Zmierzyć profile/fixture output zmieniające się przez mixed-population prior.
- [x] Sprawdzić produkcyjny fallback i oddzielić `surface_missing` od `<100` support.
- [x] Zaprojektować evidence-only hierarchy/fallback bez wdrażania do PROD.
- [x] SHADOW comparison.
- [x] Zero zmian model math / progu surface support 100 / PROD.
- [x] Artifact + pełne CI + fresh-main rebases po data-only bot drift + merge + post-merge green.

**Definition of Done:** spełnione dla fazy audytowej; brak promocji do PROD.

---

## LOGIC-04 — Context Engine SHADOW

Status: `[x] COMPLETED — PR #392 / merge c9acb27e48f41e9a5aaa0fa1bb041c65c5f45ab7`

Cel: jeden kanoniczny producent kontekstu meczu/historycznego rekordu, bez probability i bez runtime promotion.

- [x] Zdefiniować schema contextu.
- [x] current season / previous season / career prior.
- [x] days_old / opisowy freshness bucket.
- [x] surface / same_surface z missingness.
- [x] source tour i raw event level tylko jeśli istnieje.
- [x] player rank / opponent rank / rank gap.
- [x] opponent tier wyłącznie jako opisowy rank band, nie strength score.
- [x] inactivity gap i obserwowalne położenie rekordu względem przerw bez diagnozy comeback/injury.
- [x] provenance/reason code dla każdego pola.
- [x] reużyć deterministic fail-closed identity resolution.
- [x] strict as-of i jawna date granularity.
- [x] brak zgadywania kontuzji/event level/aliasów.
- [x] SHADOW only; brak probability.
- [x] testy identity/time leakage.
- [x] artifact na dokładnym production cache/current snapshot.
- [x] pełne CI + fresh-main rebuild + merge + post-merge refresh/Pages GREEN.

**Definition of Done:** spełnione. Istnieje spójny SHADOW context schema z provenance; nie jest podłączony do Current/Player DNA/Symfonii ani PROD.

---

## LOGIC-05 — Opponent Strength Engine

Status: `[~] ACTIVE — SHADOW EVIDENCE / CONSOLIDATE EXISTING CHALLENGER`

Cel: wynik/statystyka ma znaczenie względem klasy przeciwnika.

- [~] Dostępne historyczne informacje o jakości rywala — istniejący leakage-safe opponent-own-profile challenger do formalnej konsolidacji.
- [ ] Opponent strength bez ręcznego prostego przelicznika rankingu.
- [ ] Ranking tier / continuous transform jako oddzielny benchmark.
- [ ] Surface-aware opponent strength.
- [ ] Event/tour context z hard provenance.
- [ ] Performance-vs-expectation residual.
- [ ] Chronological holdout + walk-forward validation.
- [ ] Wspólna próbka vs profile/rank baseline.
- [ ] Dedykowany artifact/workflow z aktualnego cache.
- [ ] SHADOW only do osobnej decyzji o promocji.

**Definition of Done:** istnieje jeden leakage-safe opponent-strength owner z reprodukowalnym evidence runem i walk-forward; różna klasa rywala jest mierzalna bez prostego arbitralnego rank-multiplier. W LOGIC-05 nie ma promocji do PROD.

---

## LOGIC-06 — Opponent-Adjusted Serve / Return / Hold / Break

Status: `[ ] NOT STARTED`

Cel: Player DNA opisuje realną siłę, nie tylko surowe procenty z różnej klasy rywali.

- [ ] Expected serve vs opponent return strength.
- [ ] Serve residual.
- [ ] Expected return vs opponent serve strength.
- [ ] Return residual.
- [ ] Hold residual.
- [ ] Break residual.
- [ ] Surface split.
- [ ] Sample/confidence handling.
- [ ] Porównanie raw vs adjusted na common test set.
- [ ] Nie nadpisywać Player DNA przed promotion PR.

**Definition of Done:** 72% serve przeciw słabym returnerom nie jest automatycznie równoważne 72% przeciw elicie.

---

## LOGIC-07 — Player State

Status: `[ ] NOT STARTED`

Cel: oddzielić „kim gracz zwykle jest” od „jak gra teraz”.

- [ ] Current-season level.
- [ ] Recent form windows wybrane na podstawie LOGIC-01.
- [ ] Season delta vs previous baseline.
- [ ] Ranking momentum.
- [ ] Serve trend.
- [ ] Return trend.
- [ ] Opponent-adjusted performance trend.
- [ ] Surface state.
- [ ] Inactivity/comeback uncertainty bez zgadywania przyczyny.
- [ ] Matches-since-return state po walidacji definicji.
- [ ] Confidence/provenance.
- [ ] SHADOW comparison z obecnym Current Engine.

**Definition of Done:** system potrafi rozróżnić długoterminowy poziom od aktualnego stanu.

---

## LOGIC-08 — Readiness Engine

Status: `[ ] NOT STARTED`

Cel: koniec z jednym prostym `model_ready` dla wszystkiego.

- [ ] Identity readiness.
- [ ] Freshness readiness.
- [ ] Current-season readiness.
- [ ] Surface readiness.
- [ ] Serve/return readiness.
- [ ] PBP readiness.
- [ ] Opponent-context readiness.
- [ ] Market-specific readiness.
- [ ] Reason codes.
- [ ] UI bez wymyślania danych.
- [ ] Migration plan z obecnego boolean `model_ready`.

**Definition of Done:** system wie dokładnie, dla jakiego rynku ma wystarczające dane i dlaczego.

---

## LOGIC-09 — Learning Integrity / Prediction Ledger

Status: `[ ] NOT STARTED`

Cel: modele uczą się i są porównywane na uczciwej próbce.

- [ ] Zapisywać wszystkie wspierane pre-match predictions przed selection gate.
- [ ] Oddzielić `ALL`, `PLAYABLE`, `SELECTED`.
- [ ] Wspólny settled common test set Current/CatBoost/TabPFN.
- [ ] Walk-forward split bez leakage.
- [ ] Brier/calibration/accuracy na identycznej próbce.
- [ ] Market-specific metrics.
- [ ] Usunąć selection bias z telemetryki.
- [ ] Nie zmieniać wag ensemble przed wynikami audytu.

**Definition of Done:** wagi i oceny modeli wynikają z porównywalnych danych, nie z różnych podzbiorów.

---

## LOGIC-10 — Guard Ownership / Dead Logic Audit

Status: `[ ] NOT STARTED`

Cel: guardy chronią kontrakty, ale nie walczą z legalnym outputem innych modułów.

- [ ] Lista aktywnych guardów i owner każdego guardu.
- [ ] Input/output/reason code i kolejność wykonania.
- [ ] Wykrycie sprzecznych guardów.
- [ ] Audyt BO5 dead logic.
- [ ] Usunięcie/naprawa tylko po testach regresyjnych.
- [ ] Zero guardów naprawiających inne guardy.

**Definition of Done:** każdy guard ma jeden cel i nie blokuje legalnego kanonicznego outputu przez historyczny warunek.

---

## LOGIC-11 — Frontend Ownership / Data Provenance

Status: `[ ] NOT STARTED`

Cel: UI pokazuje dokładnie to, co backend faktycznie wyprodukował.

- [ ] Zmapować faktyczne importy/runtime obecnego UI.
- [ ] Jeden owner listy meczów i detail view.
- [ ] Jeden PLAYABLE gate w UI.
- [ ] Usunąć/oznaczyć martwe stare pliki po audycie.
- [ ] N/D zamiast sztucznego zero.
- [ ] SHADOW jawnie oznaczone.
- [ ] Timestamp = generated_at backendu.
- [ ] Żadnych frontendowych probability/H2H/odds fallbacków.
- [ ] Zaktualizować `ARCHITECTURE.md` po potwierdzeniu ownerów.

**Definition of Done:** liczba widoczna w UI ma jednoznaczne backendowe źródło i ownera.

---

## LOGIC-12 — iNeed$ Bet Builder Redesign

Status: `[ ] NOT STARTED`

Cel: iNeed$ ocenia rzeczywisty finalny Bet Builder, nie niezależne single.

- [ ] Potwierdzić final Symphony composition jako jednostkę wejścia.
- [ ] Joint probability całej kompozycji.
- [ ] Exact Superbet combined odds / jawne zasady, jeśli operator nie dostarcza combined price.
- [ ] EV całego buildera.
- [ ] Kelly/risk/stake całego buildera.
- [ ] Jedna rezerwacja bankroll per BB.
- [ ] Jeden settlement całego BB.
- [ ] Min. 2 nogi.
- [ ] SHADOW/DRY_RUN.
- [ ] Brak real-money execution.
- [ ] Backtest na zamrożonych ofertach/operator context, jeśli dane pozwalają.

**Definition of Done:** ekonomika iNeed$ odpowiada temu samemu produktowi, który użytkownik faktycznie może zbudować w Superbet.

---

# 4. CHECKPOINT PRZERWANIA — obowiązkowy przed zakończeniem/przerwą

Przed zakończeniem dłuższej sesji albo gdy istnieje ryzyko limitu/przerwania zapisz co najmniej:

- **ACTIVE LOGIC/TASK**,
- **SUBSTEP**,
- **BRANCH**,
- **PR**,
- **LAST VERIFIED MAIN**,
- **LAST COMPLETED WORK**,
- **CHANGED FILES**,
- **TEST STATUS**,
- **CI STATUS**,
- **BLOCKERS**,
- **DO NOT REDO**,
- **NEXT EXACT ACTION**,
- **RISKS / HARD BANS**.

Jeżeli nie można zaktualizować pliku przed nagłym przerwaniem, następny agent ma odtworzyć checkpoint z GitHub PR/commits/workflowów i dopiero wtedy kontynuować.

---

# 5. PROTOKÓŁ WZNOWIENIA NOWEGO CZATU

1. Odczytaj `AGENTS.md`.
2. Odczytaj `TENIS_AI_LOGIC_CONSTITUTION.md`.
3. Odczytaj `TENIS_AI_MODEL_DATA_REGISTRY.md`.
4. Odczytaj ten plik i `LIVE CHECKPOINT`.
5. Sprawdź żywy GitHub: `main`, branch, PR, CI, najnowsze commity.
6. Porównaj GitHub z checkpointem.
7. Jeśli bot przesunął `main`, oceń tylko drift względem aktywnego brancha; nie resetuj całej pracy.
8. Potwierdź checkboxy dowodami.
9. Kontynuuj od `NEXT EXACT ACTION`.
10. Nie rozpoczynaj wcześniejszego etapu od zera bez dowodu, że checkpoint był błędny.
11. Nie przeskakuj do kolejnego LOGIC, dopóki Definition of Done aktywnego etapu nie jest spełnione albo jawnie deferred/blocked przez właściciela projektu.

---

# 6. Zasada anty-chaos

Jeżeli podczas zadania pojawi się nowy problem:

- jeśli blokuje bieżący etap — wpisz jako blocker i napraw w jego ownerze,
- jeśli nie blokuje — dopisz do właściwego LOGIC/P0/P1/P2 w registry/checkliście,
- nie twórz nowej architektury na boku,
- nie zmieniaj kolejności programu bez zapisania powodu,
- nie uznawaj problemu za rozwiązany tylko dlatego, że UI przestało go pokazywać.

Celem checklisty jest to, żeby **stan projektu był w repo, a nie w pamięci pojedynczego czatu**.
