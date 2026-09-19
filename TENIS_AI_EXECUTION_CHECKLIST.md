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

**Ostatnia aktualizacja checkpointu:** 2026-09-19

**Aktywny program:** reorganizacja logiki/danych/modeli Tenis AI

**ACTIVE LOGIC/TASK:** `LOGIC-08 — Readiness Engine`

**SUBSTEP:** phase-4 exact-snapshot audit and docs closeout are merged. Active work is the separate SHADOW delivery implementation in the existing `Player DNA SHADOW refresh` host. The implementation remains additive sidecar/artifact delivery only; zero meta/UI/runtime gate replacement is approved.

**BRANCH:** `logic-08-readiness-shadow-delivery` based on post-closeout `main` `f52e4bf9419a5ae9a749b7037c1a553ac816acb1` (PR #409 merge).

**PR:** phase-4 audit PR #408 is merged as `4d626b2bd59f454773b350766f8207567460d07b`; docs closeout PR #409 is merged as `f52e4bf9419a5ae9a749b7037c1a553ac816acb1`. Active implementation PR is not opened yet.

**LAST VERIFIED MAIN:** `f52e4bf9419a5ae9a749b7037c1a553ac816acb1` - guarded merge of docs closeout PR #409; implementation branch is based on this exact main pending a fresh pre-push recheck.

**LAST COMPLETED WORK:** phase-4 audit/hardening is merged. Exact-head Point Tape run `35446260835` completed SUCCESS and artifact `player-dna-point-foundation` ID `10586677424` (`sha256:2d2e924777cd3c5552a3b58e8f772ac8db5c4a093a36e12bbde54455fdee5fe2`) carried exact `results.json`, stamped run-local history coverage and semantic readiness. Independent canonical digest verification produced `79645fe3f81bc628b7152f1597811a09f1d5dc3c29bce3bbde2c0a15f6a7d3bd` for all three sources; history/Player State alignment true, legacy mismatches 0, all isolation flags false, network_calls 0.

**MERGE EVIDENCE:** LOGIC-05 PR #394 → `bd01b3c9bc1685a36c8762a2fd3ea64871fdc801`; LOGIC-06 PR #397 → `c1d1328b38a9b71fc2b4b15f4dc5f34c86703200`; LOGIC-07 PR #399 → `7d5e66a07ba400473302966e40592a591dfd71c3`; docs closeout PR #400 → `f2de0e9b5ad4bdf7adf4a24c44d54c0c173fd980`; LOGIC-08 phase-1 PR #402 → `fd44c0546b3167554046a018b9fce1d02b35cbed`; consumer audit PR #403 → `01d52caca2ebba9a7856e13cd49f508e2a595a0f`; consumer-audit docs closeout PR #404 → `50b71c0b693feaa963b5435a13c84c1a667f6797`; phase-3 requirement matrix PR #406 final head `2937de67db7bed9bc3fcaea9f020d8720e53f5ef` → merge `777f48b87407b14937feb7d46ce97e707dca4f71`. Unrelated archive repair PR #405 → `eec6483ed942ebab9193ef4bd4681ac352f3490c`; phase-4 exact-snapshot delivery audit PR #408 final head `cccac2993ed05dd8fb75a4f9b57328dda2d12bd9` -> merge `4d626b2bd59f454773b350766f8207567460d07b`.

**TEST / CI BASELINE:** final phase-4 branch: targeted readiness/delivery + TASK-017 contract **37/37 GREEN**; FULL **1291/1291 GREEN**; `py_compile` and `git diff --check` GREEN. Exact-head PR CI all GREEN: CodeQL, Delivery/Security, LOGIC-01..04, UI & Project Health, Point Tape `35446260835`. Final diff did not modify `backend/history_coverage_audit.py`, `backend/update.py`, frontend runtime, Current Engine, learning gates, PLAYABLE or iNeed$.

**AUTHORITATIVE PHASE-1 ARTIFACT:** Point Tape #400 `player-dna-point-foundation` ID `10579342271`, digest `sha256:474b6fc22ca92a9010095669ee773bebc9253592fe1bc3729902982a7df677c0`, exact head `691ab2266...`; readiness status `READINESS_SEMANTICS_SHADOW_EVIDENCE_READY`, 156 aligned matches, zero legacy-reference mismatches.

**AUTHORITATIVE PHASE-4 ARTIFACT:** exact-head Point Tape `35446260835`, artifact ID `10586677424`, artifact digest `sha256:2d2e924777cd3c5552a3b58e8f772ac8db5c4a093a36e12bbde54455fdee5fe2`; verified canonical results/history/readiness digest `79645fe3f81bc628b7152f1597811a09f1d5dc3c29bce3bbde2c0a15f6a7d3bd`.

**BLOCKERS:** local implementation has no code/test blocker. Full cache-backed workflow proof is pending PR Actions because this local worktree has no restored Actions cache/derived Player DNA files. Meta/UI/runtime/learning migrations remain blocked; R07/R08/R11 -> LOGIC-09, R14 -> LOGIC-10.

**DO NOT REDO:** nie powtarzać LOGIC-00..07, phase-1, 21-file phase-2 inventory ani 22-token/19-line phase-3 requirement audit bez dowodu driftu. Nie usuwać/redefiniować legacy `model_ready`. Nie scalać PBP `market_ready`, Symphony `learning_model_ready` ani Superbet operator availability z semantic readiness. Nie wire'ować R12/R13 przez stale/cross-run artifact albo frontendową inferencję.

**RISKS / HARD BANS:** zero zmian model math, probability, progów, wag, treningu, Current Engine PROD, Player DNA PROD, Surface Elo, Symfonii, Neuronu, PLAYABLE, settlementu, SHADOW→PROD i iNeed$ calculations bez osobnej autoryzacji. Brak fuzzy matching, ręcznych aliasów, provider-ID namespace guessing i real-money execution.

### NEXT EXACT ACTION

1. Fresh-main check; if the active Player DNA SHADOW run moves `main`, audit drift and rebase/retest this implementation branch.
2. Commit/push `logic-08-readiness-shadow-delivery` and open the implementation PR.
3. Require exact-head Player DNA SHADOW PR workflow with restored real cache and independently verify artifact digest/alignment/isolation evidence.
4. Require full PR CI GREEN; fresh-main/rebase if needed; merge only GREEN.
5. Post-merge verify the existing one-commit Player DNA SHADOW publication publishes at most the additive `readiness_engine_shadow.json` sidecar and does not retrigger Update.
6. R12/R13 additive meta telemetry remains blocked until that real post-merge sidecar passes exact current-snapshot verification; missing/mismatch = `N/D`.

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

Status: `[x] COMPLETED — SHADOW evidence / PR #394 / merge bd01b3c9bc1685a36c8762a2fd3ea64871fdc801`

Cel: wynik/statystyka ma znaczenie względem klasy przeciwnika.

- [x] Leakage-safe opponent-own-profile strength z strict-prior snapshotu.
- [x] Opponent strength bez ręcznego prostego przelicznika rankingu.
- [x] Ranking tier / continuous rank jako oddzielny benchmark, nie strength definition.
- [x] Surface-aware opponent strength z jawna missingness.
- [x] Event/tour context tylko z hard provenance; brak event level nie jest zgadywany.
- [x] Performance-vs-expectation residual jako SHADOW evidence.
- [x] Chronological holdout + 3-fold walk-forward validation.
- [x] Common sample vs profile/rank i lean-stateful baseline.
- [x] Dedykowane evidence w istniejącym Point Tape artifact.
- [x] SHADOW only; candidate replacement/promotion pozostają false.

**Definition of Done:** spełnione dla SHADOW evidence; szczegóły i metryki: `TENIS_AI_CHECKPOINT_LOGIC_05.md`. Brak promocji do PROD.

## LOGIC-06 — Opponent-Adjusted Serve / Return / Hold / Break

Status: `[x] COMPLETED — SHADOW evidence / PR #397 / merge c1d1328b38a9b71fc2b4b15f4dc5f34c86703200`

Cel: Player DNA evidence rozróżnia surowe procenty od kontekstu siły rywali.

- [x] Expected serve z strict-prior player serve + opponent return counts.
- [x] Serve residual.
- [x] Expected return z strict-prior player return + opponent serve counts.
- [x] Return residual.
- [x] Hold residual.
- [x] Break residual.
- [x] Overall i same-surface split.
- [x] Jawne support/confidence metadata diagnostyczne, nie strength proxy.
- [x] Raw vs adjusted na jednym common chronological holdout + walk-forward.
- [x] Brak nadpisania Player DNA PROD; no runtime activation.

**Definition of Done:** spełnione dla SHADOW evidence; szczegóły i metryki: `TENIS_AI_CHECKPOINT_LOGIC_06.md`. Brak promocji do PROD.

## LOGIC-07 — Player State

Status: `[x] COMPLETED — SHADOW evidence / PR #399 / merge 7d5e66a07ba400473302966e40592a591dfd71c3`

Cel: oddzielić „kim gracz zwykle jest” od „jak gra teraz”.

- [x] Current-season level.
- [x] Recent form jako descriptive evidence; bez wymyślonego magic freshness cutoff i bez probability activation.
- [x] Previous-season baseline + season delta z missingness.
- [x] Ranking momentum/provenance.
- [x] Serve trend.
- [x] Return trend.
- [x] Opponent-adjusted performance trend reużywający LOGIC-06.
- [x] Current-surface state z jawnie nieznanym surface bez inferencji.
- [x] Inactivity/gap scenarios 30/60/90/180 bez zgadywania przyczyny medycznej.
- [x] Matches-since-observed-gap evidence bez diagnozy comeback cause.
- [x] Support/confidence/provenance.
- [x] Read-only comparison z obecnym Current Engine; no write/recompute/runtime activation.

**Definition of Done:** spełnione jako descriptive SHADOW evidence. Finalny artifact i isolation contract: `TENIS_AI_CHECKPOINT_LOGIC_07.md`.

## LOGIC-08 — Readiness Engine

Status: `[~] ACTIVE — phase-1/2/3 merged; phase-4 exact-snapshot observability delivery audit next`

Cel: koniec z jednym prostym `model_ready` dla wszystkiego.

- [S] Identity readiness — SHADOW semantics/reason codes gotowe; bez PROD migration.
- [S] Freshness readiness — brak zatwierdzonego cutoffu pozostaje jawnie `UNKNOWN`.
- [S] Current-season readiness — SHADOW evidence semantics gotowe.
- [S] Surface readiness — SHADOW evidence semantics gotowe.
- [S] Serve/return readiness — SHADOW evidence semantics gotowe.
- [S] PBP readiness — istniejący jawny PBP contract reużyty bez zmiany runtime.
- [S] Opponent-context readiness — SHADOW evidence semantics gotowe.
- [S] Market-specific readiness — tylko jawne PBP/Early Hold requirements; generic markets nadal `UNKNOWN`.
- [S] Reason codes — deterministic ordering + provenance/support w phase 1.
- [x] Legacy consumer inventory — 21 exact-token source files zamrożone i sklasyfikowane w PR #403; zero runtime wiring.
- [x] Consumer requirement matrix — 22 exact legacy tokeny na 19 source lines z wymaganiami, evidence ownerem, UNKNOWN semantics i ryzykiem; PR #406 merged GREEN.
- [S] Pierwszy observability candidate — R12/R13 additive SHADOW aggregate/meta w `backend/update.py`; delivery prerequisite wykryty, brak wiring do czasu exact snapshot proof; R18/R19 później.
- [~] Exact-snapshot observability delivery — phase-4 audit next; Point Tape artifact-only readiness nie może być traktowany jako current runtime snapshot.
- [ ] UI bez wymyślania danych — side-by-side dopiero po dowodzie exact alignment i backendowym provenance; stale/missing = N/D.
- [~] Migration plan z obecnego boolean `model_ready` — consumer-specific requirements zdefiniowane; żaden runtime/learning gate nie ma approval do replacement.

**Definition of Done:** jeszcze niespełnione. Phase-3 audit jest merged; phase-4 musi rozwiązać bezpieczne delivery/provenance observability, a późniejsze consumer migrations wymagają osobnych evidence gates/PR-ów.

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
