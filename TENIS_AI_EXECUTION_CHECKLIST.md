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

**Ostatnia aktualizacja checkpointu:** 2026-09-23

**Active program:** Tenis AI logic/data/model reorganization.

**ACTIVE LOGIC/TASK:** `LOGIC-09 - Learning Integrity / Prediction Ledger` remains observation-only after the first post-midnight audit reached two leakage-safe complete-day folds for ALL and PLAYABLE; market breadth is still too thin for ranking/promotion. `LOGIC-12 - iNeed$ Bet Builder Redesign SHADOW` remains a parallel observation-only track with blocker `BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE` unchanged. Training Archive GC remains gated by the existing 168h grace.

**SUBSTEP:** PR #476 (`Add grace-safe training archive GC apply`) merged as `f0c345723e4ba9ca13a1d1581d347a7ddc9b0baa`. The production Supabase migration is present as `training_archive_gc_apply`; Edge Function `training-archive-gc` v1 is ACTIVE with `verify_jwt=false` and matches the canonical source contract revision `sha256:35602d6b005e10d2fc56d566efc06c56b5fffed128a478ab9e4ffa80ca0ab331`. Manual `Training archive retention GC` run #2 / `35780215151` completed SUCCESS on `cfe4ed973f4c543c76b7396fed0ba5b5f86130af`.

**ACTIVE BRANCH:** none for runtime/model work. This checkpoint-only documentation update is isolated from runtime changes.

**ACTIVE PR:** none before this checkpoint-only documentation update; implementation work through PR #480 is merged and production-verified.

**LAST VERIFIED MAIN:** `4eed7d0a306b3603e880ccaf2664b4cd7d8754b4` (PR #480 merge). Post-merge Project Health #2844 is GREEN. Manual Runtime private delivery `core` run `35800379357` is GREEN for both publish and GC, and no open PRs were present at verification time.

**INFRASTRUCTURE REPAIR CHECKPOINT:** PR #474/#475/#476 remain complete. PR #478 (`60ee8d56...`) fixed iNeed$ rejected-decision snapshots without changing calculations and was production-proven 20/20. PR #479 (`8470fd4b...`) added bounded retry/cache for transient runtime publisher GitHub OIDC failures and was production-proven on `market`. PR #480 merged as `4eed7d0a306b3603e880ccaf2664b4cd7d8754b4`, bounded `runtime-data-publish` signed-URL generation in batches of 8 and raised the client Edge response timeout from 60s to 120s without timeout retry. Edge Function `runtime-data-publish` v3 is ACTIVE; production `core` run `35800379357` activated generation `f308e99e-cb0a-464e-8644-48b0243d683d` with `311/311` physical objects and GC GREEN.

**TRAINING ARCHIVE CURRENT BLOCKER:** the 250,000,000 B archive hard cap remains intentionally unchanged. Production GC apply audits prove pre-grace safety: apply #1 and apply #2 both completed with `expired_manifests=0`, `planned_objects=0`, `deleted_objects=0`, `deleted_bytes=0`. Current retention observation has `grace_ready_now=0`; earliest eligible grace maturity is `2026-09-23T14:05:13.238755Z`. Current eligible candidate inventory is 1035 objects / `147406562` B. No destructive deletion is legal before grace maturity.

**LOGIC-09 CURRENT EVIDENCE:** canonical source artifact `frontend/data/prediction_ledger_settlement_shadow.json` generated `2026-09-22T23:07:57.982774+00:00` has `rows=9854`, exact three-model common `960`, naturally settled common binary `308`, common void `75`, status `HAS_SETTLED_COMMON_ROWS`. Probability snapshots remain frozen and this remains descriptive SHADOW evidence only.

**LOGIC-09 TEMPORAL EVIDENCE:** deterministic read-only recomputation after UTC rollover (`as_of_utc_date=2026-09-23`) over the same frozen artifact rows gives `fold_count=2` for ALL and PLAYABLE. ALL fold 1: train `2026-09-20`, `train_rows=102`, late-settlement exclusions `15`, test `2026-09-21`, `test_rows=81`, overlap `0`. ALL fold 2: train through `2026-09-21`, `train_rows=190`, late exclusions `8`, test `2026-09-22`, `test_rows=110`, overlap `0`. PLAYABLE fold 1: train `48`, late exclusions `3`, test `10`, overlap `0`; fold 2: train `61`, late exclusions `0`, test `58`, overlap `0`. SYMPHONY_SELECTED and PLAYABLE_AND_SYMPHONY remain at `fold_count=1`.

**LOGIC-09 SAFETY:** Current/CatBoost/TabPFN probability snapshots stay frozen. `retraining_enabled=false`, `recalibration_enabled=false`, `ranking_enabled=false`, `promotion_enabled=false`; zero changes to probability/weights/thresholds/training/PLAYABLE/Symphony/Player DNA/Neuron/iNeed$.

**LOGIC-09 REMAINING GATE:** full DoD is NOT met. The chronology gate now has multiple folds for ALL/PLAYABLE, but market breadth remains thin: ALL common binary is `set1_total=181`, `match_total=112`, `match_winner=5`, `set2_winner=4`, and only `n=2` each for `set1_winner`, `set3_winner`, `total_sets`; PLAYABLE is `set1_total=91`, `match_total=22`, `match_winner=5`, `set2_winner=1`. Do not rank models, select a winner, change weights or migrate telemetry/runtime. Continue natural accumulation and keep small-N explicit.

**LOGIC-12 PARALLEL OBSERVATION / operator-evidence:** canonical `frontend/data/superbet_builder_terminal_evidence.json` generated `2026-09-22T20:29:18.033665+00:00` has 3 frozen candidates and still `settlement_result_available=false`, `payout_computed=false`, `result_inferred=false`. Events `15059409`, `15059413`, and `15063427` are all now `finished/finished`, but all remain `EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE`. Missing exact whole-ticket settlement stays `N/D`; inference from offer disappearance, event state or per-leg evidence remains forbidden.

### NEXT EXACT ACTION

1. Do not redo PR #476, the Supabase migration, Edge Function deployment, or the pre-grace manual GC; all are already proven complete.
2. Until `2026-09-23T14:05:13.238755Z`, Training Archive GC must remain a factual no-delete state. Any deletion before that timestamp is a blocker.
3. After the 168h grace matures, let/dispatch `Training archive retention GC`, verify latest-2 complete manifests, active pins and all staged/in-flight references remain intact, reconcile reclaimed bytes and object counts against `training_archive_gc_apply_audit`, then rerun Training Archive. Do not raise the 250 MB archive cap or shorten grace as a workaround.
4. Let normal Update/settlement runs continue natural LOGIC-09 accumulation. Do not backfill or recompute historical probabilities for Phase-4 evidence.
5. UTC day `2026-09-22` is now closed and the same frozen rows yield two leakage-safe folds for ALL/PLAYABLE. Let the next normal Update persist the post-midnight canonical artifact, then verify the persisted fold counts match the deterministic audit. Continue factual per-market/per-population N accumulation; do not rank/promote models while market breadth remains thin.
6. Continue LOGIC-12 observation-only for the same 3 frozen operator-settlement identities. Missing exact whole-ticket terminal evidence remains `N/D`; never infer settlement or payout.
7. Without separate authorization do not change model math/probability/thresholds/weights/training/Player DNA/Surface Elo/Symphony/Neuron/PLAYABLE/current V1 risk/iNeed$ calculations or SHADOW->PROD.

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
- [x] tour/event level tylko jeśli istnieje.
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

Status: `[~] ACTIVE - phases 0-4 merged and production-proven; natural common-set evidence is binary n=308; two closed complete-day folds exist for ALL/PLAYABLE, while market breadth remains too thin for robust ranking/promotion`

Goal: compare frozen prospective model outputs on the same exact population without selection leakage.

- [x] Phase-0 owner/population inventory + real selection-bias proof (`TENIS_AI_LEARNING_INTEGRITY_AUDIT.md`, PR #414; docs closeout #415).
- [x] Minimal frozen-ledger/common-test-set invariants documented and contract-tested.
- [x] Phase-1 immutable pre-selection prediction ledger for all supported prospective candidates (PR #416).
- [x] Phase-2 exact PLAYABLE/Symphony population evidence with strict chronology; missing evidence = `N/D` (PR #418/#419).
- [x] Phase-3 exact terminal settlement common-set owner using existing canonical terminal/scorer semantics; zero network, zero source-ledger mutation (PR #420).
- [x] Natural evidence maturity refreshed through the 2026-09-22 source artifact: `rows=9854`, exact common `960`, common binary settled `308`, common void `75`, status `HAS_SETTLED_COMMON_ROWS`; PLAYABLE common binary `119`. Zero retroactive prediction/backfill/recompute.
- [x] Phase-4 PR #470 merged as `361e279e83ebb25a2986374906da215dd350ccaa`: descriptive Brier/log-loss/accuracy + fixed 10-bin calibration on the identical common sample, per population and per market; no ranking/winner/promotion. Post-merge Update #841 and generated-artifact guard are GREEN.
- [x] Leakage-safe chronological audit implemented and production-proven: complete UTC days only, expanding prior-day train -> next complete-day test; train labels require `settled_at < test_day_start`. Post-midnight deterministic audit has two folds for ALL/PLAYABLE with zero train/test match-key overlap; fold 2 tests `2026-09-22` with ALL `test_rows=110` and PLAYABLE `test_rows=58`.
- [~] Market evidence is not broad yet: ALL common binary `set1_total=181`, `match_total=112`, `match_winner=5`, `set2_winner=4`, with `set1_winner`/`set3_winner`/`total_sets` at `n=2`; PLAYABLE is concentrated in `set1_total=91` and `match_total=22`. Keep small-N explicit.
- [x] Accumulate enough full UTC days / natural exact settlements to establish multiple temporal folds for ALL and PLAYABLE (2 folds as of UTC 2026-09-23 rollover).
- [ ] Continue natural exact settlement accumulation for broader market coverage and additional periods/populations.
- [ ] Audit/migrate telemetry only after broader evidence and separate authorization.
- [ ] Do not change ensemble weights or SHADOW->PROD; Phase-4 defines no minimum promotion threshold and no model winner.

**Definition of Done:** infrastructure, factual common-set metrics and multiple complete-day folds now exist for ALL/PLAYABLE, but full LOGIC-09 DoD is NOT met because market breadth outside `set1_total`/`match_total` remains too thin and Symphony-selected chronology still has only one fold. No ranking or promotion follows from current Phase-4 evidence.

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

Status: `[~] ACTIVE - Phase-4/5 runtime evidence and guarded persistence/sync contract are merged/production-proven; exact pricing/terminal evidence collection is active; reservation enable flag remains OFF; settlement is blocked by `BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE`

Cel: iNeed$ ocenia rzeczywisty finalny Bet Builder, nie niezależne single.

- [x] Potwierdzono current state: iNeed$ ocenia/stakuje/rozlicza pojedyncze playable signals, nie finalną kompozycję BB.
- [x] Potwierdzono final Symphony composition jako jednostkę wejścia.
- [x] Zdefiniowano additive SHADOW composition record: composition id + min. 2 legs + canonical match/operator provenance.
- [x] Joint probability jest wyłącznie passthrough z Symfonii; iNeed$ SHADOW nie liczy nowej probability.
- [x] Exact verified Superbet combined odds: phase 2 curated pre-priced rows + phase 3 dynamic `v2/getSgaOddPrice`; zero leg-odds multiplication.
- [x] Phase 4: EV/Kelly/risk/stake całego buildera + jedna niepersistowana `SHADOW_PROPOSED` reservation per `composition_id`; PR #437 merged as `9a0ad2fe84298e847a2af7a6bc5afabdafee6963`.
- [x] Phase 5: pure `builder-ticket` SHADOW envelope freezes exact composition, quote provenance, Phase-4 economics and one reservation proposal; output cannot resemble current V1 signal and explicitly claims no persistence/settlement readiness.
- [x] Phase 1-5 remain SHADOW and are runtime-produced by the canonical Superbet refresh/scoped runner; PR #456 merged and normal production workflow proved summary-only evidence with zero builder rows/reservation writes and no V1/email regression.
- [x] Separate builder-ticket persistence/sync contract merged in PR #457: dedicated OIDC Edge action + existing atomic writer, double-gated by `builder_reservation.enabled=true` and exact contract version. Production flag remains absent/false, so current runtime performs zero builder writes.
- [x] Exact pricing/reprice evidence plumbing is merged and production-proven through PR #465-#469: separate bounded dynamic sidecar, no leg-odds multiplication, fail-closed first non-PR delivery `NO_ELIGIBLE_COMPOSITIONS` with 0 external requests.
- [~] Bounded read-only terminal operator-evidence observation is active for the same 3 frozen identities through their 96h windows; latest published sample still has 0 exact whole-ticket result hits. Missing evidence = `N/D`; no result/payout inference.
- [ ] One whole-ticket BB settlement with exact operator semantics for WIN/LOSS/VOID/PUSH/CANCEL/retirement and leg-void behavior remains blocked until exact whole-ticket operator evidence exists.
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
