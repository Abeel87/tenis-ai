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

**Ostatnia aktualizacja checkpointu:** 2026-09-21

**Aktywny program:** reorganizacja logiki/danych/modeli Tenis AI

**ACTIVE LOGIC/TASK:** `LOGIC-12 - iNeed$ Bet Builder Redesign SHADOW`

**SUBSTEP:** dormant shared DB schema COMPLETE / MERGED via PR #445. Active bounded step: **migrate V1 placement + `ineed-sync` risk read-side to `ineed_open_risk_exposures` with exact V1-only equivalence**; repository candidate only, no live Supabase apply/deploy, no builder reserve writer, no builder settlement.

**BRANCH:** `logic-12-shared-exposure-readers`, rebased onto exact fresh main `1ad726112feedaacca36bfef958297e6e205203e`. Intervening bot drift after PR #445 was two generated-data commits only: `75c880d3` rebuilt Neuron SHADOW and `1ad72611` Player DNA SHADOW; zero overlap with this branch.

**PR:** #446 ? `LOGIC-12: migrate V1 risk readers to shared exposure view`; base `1ad726112feedaacca36bfef958297e6e205203e`; pre-checkpoint head `9be89c5ea8e718c79d30c7746e9b2043896355c4`.

**LAST VERIFIED MAIN:** `1ad726112feedaacca36bfef958297e6e205203e` ? bot `data: refresh Player DNA SHADOW`, parent `75c880d3510ac5a766177f9ebe2db91ceef59c19`; drift since PR #445 is generated `frontend/data/*` only.

**DORMANT-SCHEMA MERGE PROOF:** PR #445 exact head `766436fc76a5923ed6601a286adae722642a64d4` passed 8/8 GREEN workflows on base `9fd45f4938413f4e81bb9c701d3a6077ce75bf7d` and merged as `ab2d1034f8e34539fc1d905f95205567915f86bb`. Live Supabase was not migrated; `ineed-sync` remains ACTIVE v10 with unchanged hash `0752efcece199bcc69c5f8e0387dff756cac90b0afd369b5364c8657e8e696e4`.

**SHARED READER IMPLEMENTATION:** migration `supabase/migrations/20260921091005_ineed_shared_exposure_readers.sql` replaces only current-exposure reads inside `ineed_system_place_bet()` with `ineed_open_risk_exposures`. Signal/experiment `FOR UPDATE`, idempotent V1 bet ownership, V1 bet insert, V1 ledger debit and current stake/risk formulas remain unchanged.

**EDGE CANDIDATE:** repository `supabase/functions/ineed-sync/index.ts::activeState()` now reads `ineed_open_risk_exposures` into separate `risk_exposures` and calculates active exposure/equity from it. `open_bets` remains V1-only from `ineed_shadow_bets` for the settlement runner. Existing deployed-v10 SMTP/auth/persistence markers remain tracked. This source is a **candidate newer source and is NOT deployed**; live Edge remains v10.

**V1 EQUIVALENCE:** placement exposure metrics (total/match/market/player) are regression-compared old V1 SQL vs shared-view semantics across 500 deterministic randomized legal V1 states using exact decimal stake arithmetic. Previous DB-view vs backend normalization proof across 250 states remains valid.

**CURRENT LOCAL GATE:** full iNeed pack 114/114 GREEN; full repository pytest 1447/1447 GREEN; reader migration parses as 3 PostgreSQL statements; Deno check for candidate `ineed-sync` GREEN; new 500-state placement equivalence GREEN; UI static smoke PASS (377 current matches / all 101 Symphony); Project Health 0 FAIL / 1 existing WARN; `git diff --check` clean.

**NEWLY DISCOVERED PRE-WRITER BLOCKERS:** repo-wide reader audit found three additional V1-only consumers: `ineed_admin_start_experiment()` open-exposure guard, `ineed_system_settle_bet()` `other_exposure` bookkeeping, and `frontend/ineed.js` exposure presentation. They are **not changed in this step**. No builder reserve writer may be enabled until their required shared-exposure behavior is separately audited/migrated or explicitly proven irrelevant.

**RUNTIME / DEPLOY STATUS:** no `apply_migration`, no Edge deploy, no builder table write, no reserve RPC/caller and no builder settlement. The merged dormant schema and this reader migration both remain unapplied to live Supabase.

**SETTLEMENT:** builder settlement remains `NOT_IMPLEMENTED`; V1 settlement code and `open_bets` semantics remain unchanged in this branch.

**DO NOT REDO:** do not reopen LOGIC-11, LOGIC-12 phases 1-6, source parity, shared-exposure/read-model work, atomicity audit or dormant-schema design unless new evidence invalidates them.

**RISKS / HARD BANS:** zero changes to model probability math, thresholds, weights, training, Player DNA PROD, Surface Elo, Symphony probability, Neuron math, PLAYABLE, current V1 iNeed$ formulas, settlement semantics or SHADOW->PROD. No real-money execution. No live Supabase schema apply/deploy in this branch.

### NEXT EXACT ACTION

1. Run full repository pytest, UI static smoke, Project Health, SQL parse, Deno check and final scope review on this branch.
2. Push this checkpoint update to PR #446; the resulting head is the only valid exact-head CI target.
3. Require exact-head CI; immediately before merge fetch fresh `main`, audit/rebase any drift and rerun CI if needed.
4. Merge only all-green/mergeable. Do not `apply_migration` and do not deploy Edge without separate explicit authorization.
5. After merge, separately audit/migrate the remaining pre-writer consumers: admin experiment-start exposure guard, V1 settlement `other_exposure` bookkeeping and frontend exposure presentation.
6. Keep builder reserve writer, builder settlement and all real-money execution disabled.

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

Status: `[x] COMPLETE - PR #422 / #423 / #424 merged; final post-merge publication evidence recorded in closeout`

Cel: guardy chronia kontrakty, ale nie walcza z legalnym outputem innych modulow ani nie udaja roznych ownerow, gdy wywoluja ten sam verifier.

- [x] Lista aktywnych named workflow guard/validation invocations i owner kazdego: phase-3 local inventory = 92 invocations across 28 workflows, exact-set contract enforced by `tests/test_guard_ownership_audit_contract.py`.
- [x] Input/output/reason code i kolejnosc wykonania: BO5, presentation guards, 52 inline Python validators, PLAYABLE/Superbet runtime validation and quota-state exception mapped.
- [x] Wykrycie sprzecznych/duplikowanych guardow: BO5 collision fixed in #422; legacy presentation aliases fixed in #423; producer-vs-validator naming fixed in #424.
- [x] Audyt BO5 dead logic: canonical Current Engine BO5 output, Market Lab BO5 boundary and Serve Props BO5 boundary mapped, merged and post-merge verified.
- [x] Usuniecie/naprawa tylko po testach regresyjnych: phase 3 focused 24/24 and full local 1349/1349 GREEN; exact-head PR CI GREEN before merge.
- [x] Zero guardow naprawiajacych inne guardy / zero fake-owner aliases: semantic scan and phase-3 contract are merged in #424.

**Definition of Done:** COMPLETE. Every audited named guard has one explicit purpose/owner; historical guards no longer erase legal canonical output, fake-owner aliases are removed, and producer-vs-validator semantics are contract-tested.

---

## LOGIC-11 — Frontend Ownership / Data Provenance

Status: `[x] COMPLETE - phases 1-7 merged through PR #432; exact-head CI and post-merge production proof GREEN`

Cel: UI pokazuje dokładnie to, co backend faktycznie wyprodukował.

- [x] Runtime/import ownership mapped: `scripts/build_delivery.mjs` producer; `frontend/app.js` shell/list/detail; `presentation-data.js` presentation/data entrypoint; history/admin/iNeed$ feature owners explicit.
- [x] One shell owner for match list/detail: `frontend/app.js`; feature extensions remain separate and explicit.
- [x] Jeden effective PLAYABLE presentation gate: `TenisPresentation.availability()` composes backend final authority with `playable-ui.js` operator/signature validation; no competing active UI decision path found.
- [x] Historical frontend owners are physically absent; phase 6 removed ghost workflow/health references and phase 7 stops booting six no-consumer calculation helpers.
- [x] N/D zamiast sztucznego zero.
- [x] SHADOW jawnie oznaczone.
- [x] Timestamp = backend `generated_at`; phase 5 merged in PR #430.
- [x] Żadnych frontendowych probability/H2H/odds/identity fallbacków.
- [x] `ARCHITECTURE.md` owner map corrected in merged phase 1.

**Definition of Done:** COMPLETE. PR #432 merged as `5ad329b0...`; exact-head 10/10 GREEN. Post-merge Update+Pages #815 passed canonical UI, Symphony/PLAYABLE and final full regression, published refreshed data and deployed Pages. Follow-up Superbet publication and iNeed$ SHADOW are GREEN on the resulting current line.

---

## LOGIC-12 — iNeed$ Bet Builder Redesign

Status: `[~] ACTIVE - phases 1-5 merged; Phase 6 persistence/sync audit is next; no runtime persistence/settlement migration`

Cel: iNeed$ ocenia rzeczywisty finalny Bet Builder, nie niezależne single.

- [x] Potwierdzono current state: iNeed$ ocenia/stakuje/rozlicza pojedyncze playable signals, nie finalną kompozycję BB.
- [x] Potwierdzono final Symphony composition jako jednostkę wejścia.
- [x] Zdefiniowano additive SHADOW composition record: composition id + min. 2 legs + canonical match/operator provenance.
- [x] Joint probability jest wyłącznie passthrough z Symfonii; iNeed$ SHADOW nie liczy nowej probability.
- [x] Exact verified Superbet combined odds: phase 2 curated pre-priced rows + phase 3 dynamic `v2/getSgaOddPrice`; zero leg-odds multiplication.
- [x] Phase 4: EV/Kelly/risk/stake całego buildera + jedna niepersistowana `SHADOW_PROPOSED` reservation per `composition_id`; PR #437 merged as `9a0ad2fe84298e847a2af7a6bc5afabdafee6963`.
- [x] Phase 5: pure `builder-ticket` SHADOW envelope freezes exact composition, quote provenance, Phase-4 economics and one reservation proposal; output cannot resemble current V1 signal and explicitly claims no persistence/settlement readiness.
- [x] Phase 1-5 remain SHADOW/non-runtime; no current iNeed-sync/Supabase/runner/frontend consumer and no real-money execution.
- [ ] Separate builder-ticket persistence/sync contract.
- [ ] Jeden settlement całego BB z exact operator semantics dla WIN/LOSS/VOID/PUSH/CANCEL/retirement i leg-void behavior.
- [ ] Backtest na zamrożonych ofertach/operator context, jeśli dane pozwalają.

**Phase-5 merge proof:** PR #438 exact head `ac9d6d02...` passed 8/8 GREEN required workflows and merged as `73926853e4439f41a97c08ffd4be93f55e16c24f`. Post-merge isolation proves zero runtime/Supabase/settlement consumer.

**Definition of Done:** ekonomika iNeed$ odpowiada temu samemu finalnemu produktowi, który użytkownik faktycznie może zbudować w Superbet, z jawnie zweryfikowanym combined price i one-ticket settlement. Phase 5 closes only the pure ticket-envelope contract; persistence and settlement remain separate future phases.

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
