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

**Ostatnia aktualizacja checkpointu:** 2026-09-17

**Aktywny program:** reorganizacja logiki/danych/modeli Tenis AI

**ACTIVE LOGIC/TASK:** `LOGIC-03 — Population / Priors Audit`

**SUBSTEP:** audit-only rozdzielenie produkcyjnych `_surface_priors` na ATP / CH / WTA i pomiar counterfactual wpływu population-specific priors przy niezmienionej historii graczy.

**BRANCH:** `brak` dla LOGIC-03 — utworzyć świeży branch dopiero ze zweryfikowanego `main` po wejściu tego checkpointu.

**PR:** `brak` dla LOGIC-03. PR #388 zakończony i zmergowany.

**LAST VERIFIED MAIN:** `7328c0ec666272abf2a73b3b2a93d06f87d05704` — merge PR #388; post-merge `Tenis AI UI & Project Health` run `35269915274` = GREEN, Delivery/Security run `35269915322` browser+dependencies = GREEN.

**LAST COMPLETED WORK:** `LOGIC-02 — Feature Provenance / Ranking Audit` zakończony. PR #388 został zmergowany po pełnym green CI. Audit zmapował ranking fixture Live Tennis API, historyczny `latest_rank` i `opponent_rank` TML, wiek/provenance i realne miejsca konsumpcji. Pierwszy łączny probe rank+opponent_rank został przed merge poprawiony, aby oba pola mierzyć osobno.

**CHANGED FILES w zakończonym PR #388:**

- `backend/ranking_provenance_audit.py`
- `tests/test_ranking_provenance_audit.py`
- `.github/workflows/ranking-provenance-audit.yml`

**LOGIC-02 EVIDENCE:**

- final head: `9d4200634afc22c9837da440d630e22c977c3f5e`;
- audit workflow: `35269552146` = GREEN;
- artifact: `10517338556`;
- digest: `sha256:ad49a0aba2a9d6a7e627d21bdb88f18c4d33cac0247319dbb180a509ca632344`;
- 161 widocznych meczów, 51 `model_ready`, 322 player-fixture profiles;
- oba fixture provider ranks: 137 meczów, 50/51 `model_ready`;
- historyczny profile rank: 197 profili;
- 102/102 `model_ready` profile ranks dokładnie odtworzyły stored `p_stats.rank`;
- wiek historycznego rankingu dla `model_ready`: median 11 dni, p90 72.8 dnia, max 340 dni; >30d=17, >90d=9, >180d=6, >365d=0;
- bezwzględna różnica fixture-vs-history rank dla `model_ready`: n=101, median 0, p90 44, max 486;
- fixture `p1_rank/p2_rank` counterfactual: 0/51 Current outputs changed;
- historyczny `latest_rank` counterfactual: 51/51 Current outputs changed;
- kanoniczne miejsce użycia historycznego rankingu: `model_core._historical_set_probability` rank term, 10% korekta historycznej set probability przed dalszym blendingiem Current;
- historyczny `opponent_rank` counterfactual: 0/51 Current outputs changed;
- Player DNA Current: `SHADOW_CURRENT_ONLY`, `production_influence=false`, `rank_features_used=false`.

**TEST STATUS:** dedykowane testy LOGIC-02 zielone, w tym time-leakage, head(20) latest-rank semantics, opponent-rank coverage, passthrough-safe output view, rozdzielone rank/opponent-rank probes i audit-only contract. Pełny wymagany pytest na finalnym PR i po merge = GREEN.

**CI STATUS:**

- PR #388 final head `9d4200634afc22c9837da440d630e22c977c3f5e`: LOGIC-02 audit `35269552146` = GREEN, CodeQL `35269552039` = GREEN, Delivery/Security `35269552040` = GREEN, UI & Project Health `35269552027` = GREEN.
- merge commit: `7328c0ec666272abf2a73b3b2a93d06f87d05704`.
- post-merge UI & Project Health `35269915274` = GREEN: full pytest, wszystkie SHADOW/runtime/health guardy = GREEN.
- post-merge Delivery/Security `35269915322` = GREEN: browser E2E i dependency/security checks = GREEN.

**BLOCKERS:** brak blockerów.

**DO NOT REDO:** nie powtarzać LOGIC-01 ani LOGIC-02 bez nowego dowodu błędu. Nie interpretować fixture provider rank jako używanego przez Current — finalny counterfactual wykazał 0/51 wpływu. Nie interpretować `opponent_rank` jako obecnego Current feature — 0/51 wpływu. Historyczny `latest_rank` jest realnym Current inputem. Nie aktywować fixture rank, opponent adjustment ani nowej freshness policy bez późniejszego SHADOW/validation/promotion. Nie fabricować Brier/calibration bez bezstronnego settled common ledger (LOGIC-09).

### Co zakończono wcześniej

- [x] LOGIC-00 — Project Constitution / Operating Contract — PR #384 / merge `5269f6c467c3602fd6d557ed3385bc951008f07d`.
- [x] LOGIC-01 — Freshness Counterfactual — PR #386 / merge `c9292b630c918f7fde0c9c48231629a10819c09f`.
- [x] TASK 019 / PR #383 evidence zostało skonsumowane przez LOGIC-01; #383 zamknięty bez merge.
- [x] LOGIC-02 — Feature Provenance / Ranking Audit — PR #388 / merge `7328c0ec666272abf2a73b3b2a93d06f87d05704`.

### NEXT EXACT ACTION

1. Sprawdź ponownie świeży `main`, wszystkie otwarte PR-y i ostatnie CI; bot może przesunąć `main` po tym checkpointcie.
2. Przeczytaj aktualny `model_core._surface_priors`, `update.TML_SOURCES` i wynik LOGIC-02; nie zakładaj semantyki z pamięci.
3. Utwórz świeży branch `logic-03-population-priors-audit` z aktualnego `main`.
4. Audit-only: na dokładnym cache TML zmierz produkcyjny mixed `_surface_priors` per surface i osobno ATP / CH / WTA z zachowaniem as-of cutoff.
5. Dla każdego segmentu raportuj support: pre-cut rows, surface rows i czy produkcyjny próg `>=100` wybrał surface-specific prior czy fallback all-surfaces.
6. Dla jednoznacznie zmapowanych fixture'ów policz SHADOW counterfactual: identyczne player history i identyczny model, ale zamrożone population-specific priors; raportuj profile/output deltas. Nie zgaduj nieznanych `tour`.
7. Zaprojektuj hierarchy/fallback jako evidence-only candidate; nie wdrażaj do PROD i nie zmieniaj progu 100.
8. Zero zmian model math, probability, progów, wag, treningu, Player DNA, Surface Elo, Symfonii, Neuronu, PLAYABLE, settlementu, SHADOW→PROD ani iNeed$ calculations.
9. PR → dedykowane CI + artifact → pełne zielone CI → fresh-main check → merge → post-merge verification → checkpoint do LOGIC-04.

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
- [ ] Zapisz źródła wejściowych danych.
- [ ] Zapisz konsumentów wyniku.
- [ ] Zapisz guardy/walidatory przed i za modułem.
- [ ] Odtwórz bug/problem testem, raportem lub audytem.
- [ ] Rozdziel: bug implementacyjny / problem danych / problem modelowy / debt dokumentacyjny.
- [ ] Jeśli zakres dotyczy probability/wag/progów/modelu — najpierw SHADOW/counterfactual i osobna autoryzacja.

## C. Implementacja

- [ ] Popraw kanonicznego ownera **w miejscu**.
- [ ] Nie twórz nowego `vXXX`, wrappera ani równoległej ścieżki jako obejścia.
- [ ] Usuń/zdezaktywuj zastępowaną aktywną logikę, gdy migracja jest bezpieczna.
- [ ] Nie zmieniaj downstream UI, aby ukryć zły upstream.
- [ ] Nie zmieniaj guardu, jeśli bug należy do producenta danych/modelu — i odwrotnie.
- [ ] Zachowaj provenance i reason codes.
- [ ] Dodaj test regresyjny.
- [ ] Zaktualizuj registry/architekturę/checklistę, jeśli zmieniła się odpowiedzialność lub pipeline.

## D. Walidacja

- [ ] Test jednostkowy reprodukujący problem jest zielony.
- [ ] Testy sąsiednich modułów są zielone.
- [ ] Pełny wymagany pytest jest zielony.
- [ ] UI smoke jest zielony, jeśli zakres dotyczy UI/runtime danych.
- [ ] Project Health jest zielony.
- [ ] Security/CodeQL wymagane dla PR są zielone.
- [ ] Brak niezamierzonej zmiany probability/model math/settlement/PROD-SHADOW poza zakresem.
- [ ] Porównano output przed/po tam, gdzie może zmienić wyniki.

## E. Merge

- [ ] PR zawiera wyłącznie zakres zadania.
- [ ] Wszystkie wymagane CI = GREEN.
- [ ] Świeży `main` sprawdzony bezpośrednio przed merge.
- [ ] Jeśli `main` się przesunął — branch przebudowany/rebase i CI uruchomione ponownie.
- [ ] Merge wykonany.
- [ ] Merge commit zapisany w checkpointcie.

## F. Po merge

- [ ] Sprawdź produkcyjny workflow/snapshot.
- [ ] Potwierdź, że funkcja działa na `main`, nie tylko w teście.
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
- [x] Final CI green.
- [x] Fresh-main check.
- [x] Merge #384.
- [x] Post-merge verification.

**Definition of Done:** spełnione.

---

## LOGIC-01 — Freshness Counterfactual

Status: `[x] COMPLETED — PR #386 / merge c9292b630c918f7fde0c9c48231629a10819c09f`

Cel: ustalić na danych, jak świeżość wpływa na jakość modeli; bez zmiany PROD.

- [x] Przenieść wynik TASK 019 jako baseline evidence.
- [x] Zmierzyć baseline produkcyjny bez cutoffu.
- [x] Przeliczyć 30/60/90/120/180/365 dni dla Current player history.
- [x] Osobno zmierzyć PBP/Early Hold freshness.
- [x] Zamrozić global surface priors w pierwszym eksperymencie.
- [x] Raport profile retained / >=5 / model-ready retained-lost.
- [x] Raport probability/output deltas na tych samych fixture'ach.
- [x] Brier/calibration/accuracy: `N/A`, bo brak unbiased settled common ledger; owner = LOGIC-09.
- [x] Lista konkretnych meczów/profili zależnych od starej historii.
- [x] Zero zmian PROD.
- [x] CI + artifact.

**Definition of Done:** spełnione; cutoff nie został wybrany „na oko”.

---

## LOGIC-02 — Feature Provenance / Ranking Audit

Status: `[x] COMPLETED — PR #388 / merge 7328c0ec666272abf2a73b3b2a93d06f87d05704`

Cel: wiedzieć skąd pochodzi każda ważna cecha rankingowa i czy jest aktualna.

- [x] Zmapować ranking fixture z Live Tennis API.
- [x] Zmapować `latest_rank` z TML/history.
- [x] Porównać current vs historical ranking dla wszystkich dostępnych model-ready profiles.
- [x] Zmierzyć wiek używanego historycznego rankingu.
- [x] Zidentyfikować miejsca, gdzie obecny fixture ranking jest ignorowany.
- [x] Zmapować `opponent_rank` dla historycznych meczów.
- [x] Zbudować provenance report per match/player.
- [x] Rozdzielić counterfactual fixture rank / historical latest_rank / historical opponent_rank.
- [x] Zero zmian model math i zero promocji w fazie audytu.
- [x] Dedykowane CI + artifact + full PR CI + post-merge verification.

**Definition of Done:** spełnione. Dla każdej badanej cechy rankingowej znamy źródło, obserwowaną datę tam gdzie istnieje, wiek oraz faktyczne miejsce użycia/nieużycia.

---

## LOGIC-03 — Population / Priors Audit

Status: `[~] ACTIVE — NEXT: MIXED VS ATP/CH/WTA PRIORS AUDIT`

Cel: sprawdzić mieszanie ATP/WTA/Challenger i wpływ globalnych priors.

- [ ] Zmierzyć current `_surface_priors` per surface.
- [ ] Rozbić priory na ATP / CH / WTA.
- [ ] Zmierzyć różnice hold/break/serve/return.
- [ ] Zmierzyć, ile profili/fixture outputs zmienia się przez mixed-population prior.
- [ ] Sprawdzić fallback, gdy segment ma mało danych.
- [ ] Zaprojektować hierarchy/fallback bez wdrażania do PROD.
- [ ] SHADOW comparison.
- [ ] Zero zmian model math / progu surface support 100 / PROD.

**Definition of Done:** wiemy, czy i jak populacje muszą być rozdzielone oraz jakie dane wspierają późniejszą decyzję o fallbacku; żadnej promocji w tym etapie.

---

## LOGIC-04 — Context Engine SHADOW

Status: `[ ] NOT STARTED`

Cel: jeden kanoniczny producent kontekstu meczu/historycznego rekordu.

- [ ] Zdefiniować schema contextu.
- [ ] current season / previous season / career prior.
- [ ] days_old / freshness bucket.
- [ ] surface.
- [ ] tour/event level.
- [ ] player rank / opponent rank / rank gap.
- [ ] opponent tier.
- [ ] inactivity gap / matches-since-return.
- [ ] provenance dla każdego pola.
- [ ] brak zgadywania kontuzji.
- [ ] SHADOW only.
- [ ] testy identity/time leakage.

**Definition of Done:** każdy model może konsumować jeden spójny kontekst zamiast własnych lokalnych interpretacji czasu/rankingu/surface.

---

## LOGIC-05 — Opponent Strength Engine

Status: `[ ] NOT STARTED`

Cel: wynik/statystyka ma znaczenie względem klasy przeciwnika.

- [ ] Ustalić dostępne historyczne informacje o jakości rywala.
- [ ] Zbudować opponent strength feature bez prostego ręcznego przelicznika rankingu.
- [ ] ranking tier / continuous transform do walidacji.
- [ ] surface-aware opponent strength.
- [ ] event/tour context.
- [ ] performance-vs-expectation residual.
- [ ] walk-forward validation.
- [ ] SHADOW only do czasu przewagi nad baseline.

**Definition of Done:** przegrana z Top 20 i przegrana z #500 nie są identycznymi obserwacjami treningowymi.

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
- [ ] surface split.
- [ ] sample/confidence handling.
- [ ] porównanie raw vs adjusted na common test set.
- [ ] nie nadpisywać Player DNA przed promotion PR.

**Definition of Done:** 72% serve przeciw słabym returnerom nie jest automatycznie równoważne 72% przeciw elicie.

---

## LOGIC-07 — Player State

Status: `[ ] NOT STARTED`

Cel: oddzielić „kim gracz zwykle jest” od „jak gra teraz”.

- [ ] Current-season level.
- [ ] Recent form windows wybrane na podstawie LOGIC-01.
- [ ] Season delta vs 2025 baseline.
- [ ] ranking momentum.
- [ ] serve trend.
- [ ] return trend.
- [ ] opponent-adjusted performance trend.
- [ ] surface state.
- [ ] inactivity/comeback uncertainty.
- [ ] matches-since-return state.
- [ ] confidence/provenance.
- [ ] SHADOW comparison z obecnym Current Engine.

**Definition of Done:** system potrafi rozróżnić dobrego zawodnika w słabej formie od przeciętnego zawodnika w mocnym progresie.

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
- [ ] reason codes dla każdej blokady.
- [ ] UI prezentuje reason codes bez wymyślania danych.
- [ ] migration plan z obecnego boolean `model_ready`.

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
- [ ] Usunąć selection bias z interpretacji telemetryki.
- [ ] Nie zmieniać wag ensemble przed wynikami audytu.

**Definition of Done:** wagi i oceny modeli wynikają z porównywalnych danych, nie z różnych podzbiorów.

---

## LOGIC-10 — Guard Ownership / Dead Logic Audit

Status: `[ ] NOT STARTED`

Cel: guardy chronią kontrakty, ale nie walczą z legalnym outputem innych modułów.

- [ ] Lista wszystkich aktywnych guardów.
- [ ] Owner każdego guardu.
- [ ] Input/output/reason code.
- [ ] Kolejność wykonania.
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
- [ ] Ustalić jednego ownera listy meczów.
- [ ] Ustalić jednego ownera detail view.
- [ ] Ustalić jeden PLAYABLE gate w UI.
- [ ] Usunąć/oznaczyć martwe stare pliki po audycie.
- [ ] N/D zamiast sztucznego zero.
- [ ] SHADOW wyraźnie oznaczone.
- [ ] timestamp = generated_at backendu.
- [ ] żadnych frontendowych probability/H2H/odds fallbacków.
- [ ] zaktualizować `ARCHITECTURE.md` po potwierdzeniu ownerów.

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

Przed zakończeniem dłuższej sesji albo gdy istnieje ryzyko limitu/przerwania należy zaktualizować `LIVE CHECKPOINT` i zapisać co najmniej:

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
7. Jeśli bot przesunął `main`, nie resetuj całej pracy — oceń tylko drift względem aktywnego brancha.
8. Potwierdź, które checkboxy mają dowody i są nadal ważne.
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
