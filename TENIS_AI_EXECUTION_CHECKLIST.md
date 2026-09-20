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

# 1. LIVE CHECKPOINT - od tego miejsca ma zaczynac kolejny czat

**Ostatnia aktualizacja checkpointu:** 2026-09-20

**Aktywny program:** reorganizacja logiki/danych/modeli Tenis AI

**ACTIVE LOGIC/TASK:** `LOGIC-10 - Guard Ownership / Dead Logic Audit`

**SUBSTEP:** phase 1 BO5 owner repair is MERGED and post-merge verified. Phase 2 legacy presentation-guard ownership cleanup is in PR #423; its pre-rebase head completed 10/10 exact-head CI GREEN and the branch is now rebased onto fresh main `3a7a8dbf...`. Full LOGIC-10 remains ACTIVE for phase-3 semantic closeout after phase-2 merge.

**BRANCH:** `logic-10-runtime-guard-semantics`, worktree `C:/Users/MaDRa/.copilot/worktrees/tenis-ai-logic10-phase2`, originally created from `80098542...` and finally rebased cleanly onto verified main `3a7a8dbfee3856b6e6fc447824746f575defdd85`.

**PR:** #423 `LOGIC-10: consolidate canonical UI guard ownership` is OPEN and MERGEABLE. Pre-rebase head `3240a877...` completed 10/10 CI GREEN; fresh rebased head requires a new exact-head CI cycle before merge. Phase-1 PR #422 is MERGED.

**LAST VERIFIED MAIN:** `3a7a8dbfee3856b6e6fc447824746f575defdd85` - `data: refresh Superbet market context`. Drift since `7f441a4b...` consists only of generated `frontend/data/**`: Neuron SHADOW `eb1c5f15...`, Player DNA SHADOW `fbbf8c11...` (refresh SUCCESS 34/34), scheduled Update `6c9c17e5...` (SUCCESS), then Superbet refresh `3a7a8dbf...`. No phase-2 workflow/test/doc owner changed upstream.

**LAST COMPLETED WORK:** PR #422 merged as `aada53ad34d6613fbe628ad0a66a11348526658b` after all exact-head CI GREEN. Post-merge Update #65 completed SUCCESS: Prediction integrity gate #20 GREEN, final full regression #75 GREEN, refreshed JSON commit #77 GREEN, Pages artifact and deploy GREEN. Bot publication moved main to `80098542d59f9ee402e33c997eb29200d286054c`; subsequent Superbet refresh GREEN moved main to `7f441a4b...`. Phase 2 then proved that five historical UI guard commands (`verify_v84d1.py`, `verify_v84d2.py`, `verify_v84e11.py`, `verify_v853_runtime_ui.py`, `verify_v87_decision_center.py`) are aliases of the same `verify_ui.main()` owner. Baseline RED proof found all five aliases active. Local workflow cleanup keeps canonical UI validation only at real payload mutation boundaries and preserves specific Decision Center / match-time owners. Active named guard/validation inventory drops from 97 to 94.

**CHANGED FILES FOR PHASE 2:** `.github/workflows/update-and-pages.yml`, `.github/workflows/ui-smoke.yml`, `tests/test_guard_owner_runtime_semantics.py`, `tests/test_guard_ownership_audit_contract.py`, `TENIS_AI_GUARD_OWNERSHIP_AUDIT.md`, `TENIS_AI_EXECUTION_CHECKLIST.md`, `TENIS_AI_MODEL_DATA_REGISTRY.md`. Compatibility wrapper files are intentionally retained but are no longer active owners in these workflows.

**TEST STATUS:** phase-2 baseline RED proof: 5 legacy UI aliases active. Focused ownership/doc contract pack 19/19 GREEN; canonical UI static smoke GREEN; actual match-time smoke GREEN; Decision Center smoke GREEN; audit-consistency smoke GREEN. Full local repository suite with writable worktree basetemp: **1345/1345 GREEN**, 755 warnings, zero failures/errors.

**CI STATUS:** phase-1 PR #422 all required CI GREEN and merged. Phase-2 PR #423 pre-rebase head completed 10/10 GREEN (CodeQL, Delivery/Security, LOGIC-01..04, UI & Project Health). Final rebase onto `3a7a8dbf...` invalidates that head for merge authority; fresh exact-head CI is required after push.

**OPERATIONAL SIDE EFFECTS / NON-LOGIC BLOCKERS:** post-Update child `Runtime private delivery staging` failed on external publisher transport: attempt 1 signed upload HTTP 520; one failed-job retry reached publisher `prepare` and returned HTTP 500. `Training archive inventory` failed the initial durable publisher step with HTTP 500 and its single failed-job retry failed again at `prepare_batch` with HTTP 500. These failures happened on unmodified bot publication `80098542...`, not on the local phase-2 branch; upstream inventory/rebuild steps were GREEN. Do not attribute them to LOGIC-10 without evidence.

**BLOCKERS:** no local code/test blocker for phase 2. Player DNA and the scheduled Update are complete SUCCESS and the branch is rebased to `3a7a8dbf...`. Merge is blocked only on rerunning targeted local contracts plus fresh exact-head PR CI and the mandatory immediate pre-merge main check. Publisher issues remain separate operational work.

**DO NOT REDO:** do not repeat the 94-row phase-2 named workflow inventory unless workflows change or the exact-inventory contract reports drift. Do not reactivate legacy UI alias commands as distinct guard owners. Do not remove compatibility wrapper files merely because workflow ownership moved. Do not re-open BO5 N/D behavior already fixed by PR #422.

**RISKS / HARD BANS:** zero changes to Current Engine probability math, thresholds, weights, training, Player DNA PROD, Surface Elo, Symfonia probability, Neuron, PLAYABLE, production settlement semantics, SHADOW->PROD or iNeed$ calculations without separate authorization. No fuzzy identity, manual aliases, provider namespace guessing, post-start prediction reconstruction or real-money execution.

### NEXT EXACT ACTION

1. Rerun phase-2 targeted ownership/doc/UI contracts on rebased head `3a7a8dbf...`, amend checkpoint docs, and force-push PR #423 with lease.
2. Require all exact-head PR #423 CI GREEN again.
3. Fresh-main check immediately before merge; rebase/retest only if main moved again.
4. Merge #423 and post-merge verify Update/UI Health boundaries.
5. Open a separate phase-3 owner-scoped closeout: rename the two `player_dna_market_walk_forward.py` producer steps so they no longer masquerade as validators, add a contract that all remaining inline guards are read-only, and document `Central API Quota Guard` as the sole intentional stateful named guard.
6. If phase-3 CI/post-merge verification is GREEN, close LOGIC-10 and advance checkpoint to LOGIC-11.

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

## LOGIC-08 - Readiness Engine

Status: `[x] COMPLETE - approved audit / SHADOW observability scope merged and post-merge verified`

Cel: koniec z jednym prostym `model_ready` dla wszystkiego, bez nieautoryzowanej migracji PROD.

- [S] Identity readiness - SHADOW semantics/reason codes gotowe; bez PROD migration.
- [S] Freshness readiness - brak zatwierdzonego cutoffu pozostaje jawnie `UNKNOWN`.
- [S] Current-season readiness - SHADOW evidence semantics gotowe.
- [S] Surface readiness - SHADOW evidence semantics gotowe.
- [S] Serve/return readiness - SHADOW evidence semantics gotowe.
- [S] PBP readiness - istniejacy jawny PBP contract reuzyty bez zmiany runtime.
- [S] Opponent-context readiness - SHADOW evidence semantics gotowe.
- [S] Market-specific readiness - tylko jawne PBP/Early Hold requirements; generic markets nadal `UNKNOWN`.
- [S] Reason codes - deterministic ordering + provenance/support.
- [x] Legacy consumer inventory - PR #403.
- [x] Consumer requirement matrix - 22 legacy tokens / 19 source lines; PR #406.
- [x] Exact-snapshot sidecar delivery - PR #410 + post-merge Player DNA proof.
- [x] R12/R13 additive meta observability - PR #411 + post-merge Update proof; stale/missing/misaligned = explicit `N/D`.
- [x] UI bez wymyslania danych - R18/R19 merged in PR #412; admin/diagnostics show backend SHADOW tri-state counts or N/D only; R16 remains legacy/NO MIGRATION.
- [x] Migration plan from legacy boolean - consumer-specific requirements are documented; runtime/learning migrations are explicitly deferred to LOGIC-09 and guard ownership to LOGIC-10 rather than silently promoted.

**Definition of Done:** met for LOGIC-08 approved scope. Exact-snapshot SHADOW evidence, provenance, fail-closed metadata observability and additive UI observability are merged and verified. No runtime/learning gate replacement was authorized in this logic. R07/R08/R11 continue in LOGIC-09; R14 continues in LOGIC-10.

---

## LOGIC-09 - Learning Integrity / Prediction Ledger

Status: `[~] ACTIVE - phases 0-3 infrastructure merged/post-merge verified; prospective common-set evidence collection active (binary n=0)`

Cel: modele uczą się i są porównywane na uczciwej, identycznej próbce prospective evidence.

- [x] Phase-0 owner/population inventory + real selection-bias proof documented in `TENIS_AI_LEARNING_INTEGRITY_AUDIT.md` (PR #414 merged; docs closeout #415).
- [x] Minimal frozen-ledger/common-test-set invariants documented and contract-tested.
- [x] Phase-1: zapisywać wszystkie wspierane pre-match predictions przed selection gate w immutable append-only `prediction_ledger_shadow.json` (PR #416).
- [x] Phase-2 audit: exact owner/identity/chronology contracts dla PLAYABLE, Symphony i iNeed$ bez fuzzy/backfill (PR #418).
- [x] Phase-2 implementation: addytywny exact PLAYABLE/Symphony selection sidecar; brak dowodu = `N/D`; iNeed$ pozostaje N/D (PR #419 + Update #808).
- [x] Oddzielone i opublikowane populacje `ALL`, exact `PLAYABLE`, exact `SYMPHONY_SELECTED` oraz exact `PLAYABLE_AND_SYMPHONY`; `GENERATOR_SELECTED`/`INEED_SELECTED` pozostaj? jawnie niedost?pne do czasu istnienia ich kanonicznego prospective owner evidence.
- [x] Wsp?lny settled common test set Current/CatBoost/TabPFN ma zako?czon? infrastruktur? phase-3: PR #420 merged jako `bf959fa23f83025851a5b6db8a329d6443836547`; post-merge Update #809, dedicated guard, final regression i Pages GREEN. Published snapshot: rows=2460, common=220, PLAYABLE=585/common=83, Symphony=2/common=2, common binary settled `n=0`.
- [~] Zbiera? naturalnie dojrzewaj?ce exact common `hit/miss` rows przez normalny settlement; obecnie `n=0`, zero retroactive prediction/backfill/recompute.
- [ ] Walk-forward split bez leakage na prospective common set, gdy próbka będzie wystarczająca do sensownego audytu.
- [ ] Brier/log-loss/calibration/accuracy na identycznej próbce i osobno per population/market po pojawieniu się settled common rows.
- [ ] Market-specific metrics na tej samej exact prospective population.
- [ ] Audyt/migracja telemetryki i usunięcie selection bias dopiero po zebraniu evidence i osobnej autoryzacji.
- [ ] Nie zmieniać wag ensemble ani SHADOW->PROD przed wynikami audytu i jawną decyzją właściciela.

**Definition of Done:** wagi i oceny modeli wynikaj? z por?wnywalnych prospective danych; brak dowodu przewagi nie uruchamia promocji. Infrastructure phases 0-3 s? kompletne, ale pe?ny LOGIC-09 DoD nie jest spe?niony przy common binary settled `n=0`.
---

## LOGIC-10 - Guard Ownership / Dead Logic Audit

Status: `[~] ACTIVE - phase 1 merged/verified; phase 2 local 1345/1345 GREEN, PR pending`

Cel: guardy chronia kontrakty, ale nie walcza z legalnym outputem innych modulow ani nie udaja roznych ownerow, gdy wywoluja ten sam verifier.

- [x] Lista aktywnych named workflow guard/validation invocations i owner kazdego: phase-2 local inventory = 94 invocations across 28 workflows, exact-set contract enforced by `tests/test_guard_ownership_audit_contract.py`.
- [~] Input/output/reason code i kolejnosc wykonania: BO5 path and presentation-guard mutation boundaries mapped; remaining inline/high-risk guards still require semantic review.
- [~] Wykrycie sprzecznych/duplikowanych guardow: BO5 stale N/D collision fixed in PR #422; phase 2 confirmed five legacy presentation aliases mapped to one `verify_ui.main()` owner and removed them from distinct active ownership.
- [x] Audyt BO5 dead logic: canonical Current Engine BO5 output, Market Lab BO5 boundary and Serve Props BO5 boundary mapped, merged and post-merge verified.
- [~] Usuniecie/naprawa tylko po testach regresyjnych: phase 1 merged; phase 2 has RED proof + focused GREEN + full local 1345/1345 GREEN, PR CI pending.
- [~] Zero guardow naprawiajacych inne guardy / zero fake-owner aliases: phase-2 workflow cleanup uses canonical UI owner directly; remaining guard chains still require audit.

**Definition of Done:** kazdy guard ma jeden cel i nie blokuje legalnego kanonicznego outputu przez historyczny warunek ani nie duplikuje tego samego ownera bez realnej granicy mutacji. Nie jest jeszcze spelnione dla calego LOGIC-10.

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
