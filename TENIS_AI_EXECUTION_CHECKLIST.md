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

**ACTIVE LOGIC/TASK:** `LOGIC-04 — Context Engine SHADOW`

**SUBSTEP:** zbudować jeden audit/SHADOW history-context owner, który składa istniejące fakty fixture/TML w spójny schema z provenance i strict as-of/identity guards. Context Engine nie tworzy probability, nie zmienia Current/Player DNA/Symfonii i nie zgaduje kontuzji ani event level.

**BRANCH:** `brak` dla LOGIC-04 — świeży branch `logic-04-context-engine-shadow` utworzyć dopiero z ponownie zweryfikowanego `main` po wejściu tego checkpointu.

**PR:** `brak` dla LOGIC-04. PR #390 jest zakończony i zmergowany.

**LAST VERIFIED MAIN:** `abc13dd7204f69bcf32160c6e1f533f5e1ccc566` — merge PR #390. W momencie closeoutu brak otwartych PR-ów. Post-merge Project Health, Delivery/Security/browser/dependencies i CodeQL = GREEN.

**LAST COMPLETED WORK:** `LOGIC-03 — Population / Priors Audit` zakończony. PR #390 został dwukrotnie przebudowany na świeżym `main`, gdy boty przesuwały wyłącznie `frontend/data/*`; finalny head `bc26a40895aecd599eb63f22b3e61c7bbc9e8ff3` przeszedł cały gate i został zmergowany jako `abc13dd7204f69bcf32160c6e1f533f5e1ccc566`. Audit porównał produkcyjny mixed `_surface_priors` z ATP/CH/WTA population-specific priors przy identycznej historii graczy. Nie wdrożono population split ani nowego fallbacku do PROD.

**CHANGED FILES w zakończonym PR #390:**

- `backend/population_priors_audit.py`
- `tests/test_population_priors_audit.py`
- `.github/workflows/population-priors-audit.yml`

**LOGIC-03 EVIDENCE:**

- final PR head: `bc26a40895aecd599eb63f22b3e61c7bbc9e8ff3`;
- final audit workflow: `35272062180` = GREEN;
- artifact: `10519247060`;
- digest: `sha256:26b0f80f1c5dcac55e56da039a6fa12b80824c044e2462b19ea3cf067d996456`;
- snapshot: 159 widocznych meczów / 51 `model_ready`;
- dokładnie zmapowane `model_ready`: ATP=23, CH=19, WTA=6; eligible counterfactuals=48, errors=0;
- 3 `model_ready` ITF pozostają świadomie unmapped — brak zgadywania population namespace;
- 23 ATP `model_ready` miały brak surface i są jawnie oznaczone `surface_missing`, nie „mała próbka”;
- fallback reasons dla 48 eligible: `surface_missing`=23, `surface_specific`=25; żaden eligible fixture w tym snapshotcie nie wymagał fallbacku z powodu `<100` surface rows;
- population-specific priors zmieniły numeric Current output dla 48/48 eligible fixture'ów i profile metrics dla 96/96 profili;
- ATP: 23/23 output changed, max output delta 2.5 pp, max profile metric delta 0.021452962354;
- CH: 19/19 output changed, max output delta 0.4 pp, max profile metric delta 0.004498676539;
- WTA: 6/6 output changed, max output delta 3.9 pp, max profile metric delta 0.042544245195;
- produkcyjny surface-support threshold `100` nie został zmieniony;
- candidate hierarchy/fallback ma status `EVIDENCE_ONLY_NOT_PROD`.

**TEST STATUS:** finalny PR #390 miał zielone testy jednostkowe LOGIC-03, restore dokładnego produkcyjnego cache, strict pre-cut support semantics, future-row leakage test, brak surface vs low-support reason test, population split summary oraz hard audit-only contract. `Tenis AI UI & Project Health` run `35272062125` = GREEN z pełnym pytest i wszystkimi guardami.

**CI STATUS:**

- final head `bc26a40895aecd599eb63f22b3e61c7bbc9e8ff3`: LOGIC-03 audit `35272062180` = GREEN; CodeQL `35272062140` = GREEN; Delivery/Security `35272062116` = GREEN; UI & Project Health `35272062125` = GREEN;
- merge commit: `abc13dd7204f69bcf32160c6e1f533f5e1ccc566`;
- post-merge UI & Project Health `35272542877` = GREEN: full pytest, wszystkie SHADOW/runtime/health guardy = GREEN;
- post-merge Delivery/Security `35272542906` = GREEN: browser E2E + dependencies/security = GREEN;
- post-merge CodeQL `35272542830` = GREEN: Python i JavaScript/TypeScript = GREEN.

**BLOCKERS:** brak blockerów.

**DO NOT REDO:** nie powtarzać LOGIC-01/02/03 bez nowego dowodu, że evidence jest błędne. Nie promować population-specific priors, fallback hierarchy ani zmiany progu 100 do PROD na podstawie samego LOGIC-03. Nie zgadywać population dla ITF. Nie traktować `surface_missing` jak low-support. Nie aktywować fixture rank/opponent adjustment ani freshness policy. Nie fabricować Brier/calibration bez bezstronnego settled common ledger — owner LOGIC-09.

**RISKS / HARD BANS:** zero zmian model math, probability, progów, wag, treningu, Player DNA, Surface Elo, Symfonii, Neuronu, PLAYABLE, settlementu, SHADOW→PROD i iNeed$ calculations. LOGIC-04 nie może produkować probability. Brak fuzzy matching, brak zgadywania aliasów, event level, kontuzji albo medycznej przyczyny przerwy.

### Co zakończono wcześniej

- [x] LOGIC-00 — Project Constitution / Operating Contract — PR #384 / merge `5269f6c467c3602fd6d557ed3385bc951008f07d`.
- [x] LOGIC-01 — Freshness Counterfactual — PR #386 / merge `c9292b630c918f7fde0c9c48231629a10819c09f`.
- [x] TASK 019 / PR #383 evidence skonsumowane przez LOGIC-01; #383 zamknięty bez merge.
- [x] LOGIC-02 — Feature Provenance / Ranking Audit — PR #388 / merge `7328c0ec666272abf2a73b3b2a93d06f87d05704`.
- [x] LOGIC-03 — Population / Priors Audit — PR #390 / merge `abc13dd7204f69bcf32160c6e1f533f5e1ccc566`.

### NEXT EXACT ACTION

1. Sprawdź ponownie świeży `main`, otwarte PR-y i ostatnie CI; bot może przesunąć `main` po tym checkpointcie.
2. Odczytaj aktualne `model._dated_history`, `model._resolve_history_player_key`, `model_core.normalize_matches`, `player_dna_match_context.py`, `player_dna_context_time_audit.py` i `player_dna_opponent_context_audit.py`; reużyj istniejących semantyk zamiast tworzyć równoległe.
3. Utwórz świeży branch `logic-04-context-engine-shadow` z aktualnego `main`.
4. Zbuduj audit/SHADOW Context Engine bez runtime wiring: fixture as-of + resolved player identity + current-season / previous-season / career-prior buckets + `days_old` / opisowy freshness bucket + surface / same_surface + source_tour + jawny event-level tylko jeśli istnieje w źródle + player rank / opponent rank / rank gap + inactivity gaps + provenance/reason codes.
5. Jeśli źródło nie daje event level, zwróć `null/unavailable`; nie inferuj go z nazwy turnieju ani touru.
6. Nie diagnozuj „comeback po kontuzji”. Mierz wyłącznie obserwowalne przerwy i pozycję meczu względem przerwy; ewentualne progi pozostają opisowymi audit windows, nie prawdą medyczną ani PROD policy.
7. Strict as-of: żadnych przyszłych rekordów; dla danych tylko z rozdzielczością dnia nie dopuszczaj niejawnego same-day leakage i raportuj granularity/provenance.
8. Identity fail-closed: bez fuzzy matching i bez ręcznych aliasów. Nie zwiększaj coverage przez zgadywanie.
9. Context Engine nie tworzy probability i nie zmienia Current/Player DNA/Surface Elo/Symfonii/Neuronu/PLAYABLE/settlement/iNeed$.
10. Dodaj testy identity/time leakage, season buckets, freshness boundaries, missing event-level, rank gap, inactivity i brak probability/injury inference.
11. Dedykowany workflow ma używać wyłącznie istniejącego TML cache i current results snapshot, z `LIVE_TENNIS_API_KEY=''`, bez production cache writes.
12. PR → artifact → pełne zielone CI → fresh-main check → merge → post-merge verification → checkpoint do LOGIC-05.

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
- [x] Artifact + pełne CI + dwa fresh-main rebases po data-only bot drift + merge + post-merge green.

**Definition of Done:** spełnione dla fazy audytowej. Wiemy, że population-specific priors materialnie zmieniają profile/outputy na bieżącym snapshotcie; nie autoryzuje to jeszcze wdrożenia do PROD.

---

## LOGIC-04 — Context Engine SHADOW

Status: `[~] ACTIVE — SHADOW CONTEXT ENGINE`

Cel: jeden kanoniczny producent kontekstu meczu/historycznego rekordu, bez probability i bez runtime promotion.

- [ ] Zdefiniować schema contextu.
- [ ] current season / previous season / career prior.
- [ ] days_old / opisowy freshness bucket.
- [ ] surface / same_surface z missingness.
- [ ] source tour i raw event level tylko jeśli istnieje.
- [ ] player rank / opponent rank / rank gap.
- [ ] opponent tier wyłącznie jako opisowy rank band, nie strength score.
- [ ] inactivity gap i obserwowalne położenie rekordu względem przerw bez diagnozy comeback/injury.
- [ ] provenance/reason code dla każdego pola.
- [ ] reużyć deterministic fail-closed identity resolution.
- [ ] strict as-of i jawna date granularity.
- [ ] brak zgadywania kontuzji/event level/aliasów.
- [ ] SHADOW only; brak probability.
- [ ] testy identity/time leakage.
- [ ] artifact na dokładnym production cache/current snapshot.

**Definition of Done:** istnieje jeden spójny SHADOW context schema z provenance, który może być później walidowany jako wspólne wejście modeli; w LOGIC-04 nie jest podłączany do Current/Player DNA/Symfonii ani PROD.

---

## LOGIC-05 — Opponent Strength Engine

Status: `[ ] NOT STARTED`

Cel: wynik/statystyka ma znaczenie względem klasy przeciwnika.

- [ ] Dostępne historyczne informacje o jakości rywala.
- [ ] Opponent strength bez ręcznego prostego przelicznika rankingu.
- [ ] Ranking tier / continuous transform do walidacji.
- [ ] Surface-aware opponent strength.
- [ ] Event/tour context.
- [ ] Performance-vs-expectation residual.
- [ ] Walk-forward validation.
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
