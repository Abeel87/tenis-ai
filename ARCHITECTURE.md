# Tenis AI — kanoniczna architektura

> **Zasady nadrzędne:** przed zmianą kodu obowiązkowo przeczytaj `AGENTS.md`, `TENIS_AI_LOGIC_CONSTITUTION.md`, `TENIS_AI_MODEL_DATA_REGISTRY.md` oraz `TENIS_AI_EXECUTION_CHECKLIST.md`. Ten plik opisuje bieżącą architekturę techniczną. Jeżeli bieżący runtime lub poniższa mapa jest sprzeczna z konstytucją/rejestrem, nie wolno zgadywać ani tworzyć obejścia — rozjazd jest bugiem dokumentacji/architektury i musi zostać jawnie zbadany. `TENIS_AI_EXECUTION_CHECKLIST.md` określa natomiast aktywny etap, checkpoint i dokładny punkt wznowienia pracy.

## 1. Produkcja danych

Market publication explicitly dispatches `runtime-private-delivery` (`market`),
`ineed-shadow` and the existing fast-readiness path of `player-dna-shadow-refresh`.
These consumers no longer subscribe to market completion via `workflow_run`,
which GitHub stops beyond three chained levels. DNA explicitly dispatches its
private `dna` publication after successful, non-stale work. Full core completion
still triggers full DNA evaluation. Existing concurrency, freshness, main/PR,
OIDC and SHADOW boundaries remain authoritative. Cron remains best-effort; actual
source timestamps define freshness, never the configured interval.

Główny workflow `update-and-pages.yml` buduje analizę i publikację w jednej kontrolowanej kolejności. Najpierw aktualizowane są dane i modele bazowe, następnie PBP/historia/settlement, AutoLearn Ensemble i Adaptive Learning, później telemetryka oraz warstwy SHADOW. Superbet jest nakładany jako osobna warstwa operatorowa, a Symfonia 2.0 pracuje wyłącznie na bieżącej, zweryfikowanej ofercie operatora.

Kontrakt przepływu:

`DANE / MODEL RAW -> uczenie i walidacja -> SYMFONIA 2.0 -> bieżąca oferta Superbet -> PLAYABLE`

Brak oferty lub linii Superbet nie może usuwać ani zastępować analizy MODEL / RAW.

## 2. Modele i uczenie

- **Current Engine** — kanoniczny silnik statystyczny w `backend/model_core.py`; nie jest przedstawiany jako samouczący ML.
- **Context Engine SHADOW** — canonical evidence owner `backend/match_context_shadow.py`; strict-as-of context/provenance only, bez probability i bez PROD wiring.
- **Opponent Adjustment SHADOW** — canonical evidence owner `backend/player_dna_opponent_adjustment_audit.py`; opponent-strength i adjusted serve/return/hold/break pozostają evaluation-only.
- **Player State SHADOW** — canonical evidence owner `backend/player_dna_player_state_shadow.py`; descriptive current-state evidence oddzielone od long-term Player DNA, bez probability/runtime ownership.
- **Readiness Engine SHADOW** — canonical semantics owner `backend/readiness_engine_shadow.py`; komponuje istniejące evidence do `READY / NOT_READY / UNKNOWN` + reason codes, zachowując legacy `model_ready` read-only i bez runtime gating. Existing `Player DNA SHADOW refresh` is the canonical delivery host for exact-snapshot SHADOW readiness: it rebuilds local prerequisites after Update, verifies digest/alignment, uploads full run-local evidence, and publishes `frontend/data/readiness_engine_shadow.json` as an additive sidecar in its existing single SHADOW data commit. R12/R13 allow only one downstream projection: after writing current `results.json`, `backend/update.py` may publish additive `meta.semantic_readiness_shadow` from an already-published exact-aligned sidecar; stale/missing/misaligned/non-isolated evidence is `N/D`. Legacy `meta.model_ready`, UI behavior and all runtime/learning gates remain unchanged.
- **AutoLearn** — rzeczywiste uczenie na rozliczonej historii z chronologicznym podziałem całymi meczami na TRAIN/CAL/VAL. Current/CatBoost/TabPFN/Ensemble zachowują osobne wyniki.
- **Prediction Ledger SHADOW** - canonical prospective evidence owner `backend/prediction_ledger_shadow.py`; captures the first stable pre-match Current/CatBoost/TabPFN prediction per supported candidate before downstream selection. `backend/prediction_ledger_selection_shadow.py` adds exact positive PLAYABLE/Symphony population evidence only from frozen canonical owners with strict pre-match chronology; missing evidence is `N/D`. `backend/prediction_ledger_settlement_shadow.py` is the additive phase-3 common-set consumer: it joins only exact Live Tennis `id:<match_id>` + exact schedule to already-terminal canonical history and delegates hit/miss/void semantics to `signal_settlement.settle_signal_live`. All three layers are SHADOW-only, keep the source ledger immutable, and have zero runtime/learning/telemetry/weight ownership. LOGIC-09 Phase-4 remains inside this same settlement SHADOW owner and adds descriptive-only exact-common Brier/log-loss/accuracy, fixed 10-bin calibration, per-population/per-market diagnostics and complete-UTC-day chronological folds. Fold train labels must satisfy `settled_at < test_day_start`; the current UTC day is excluded from complete-day folds. Phase-4 never retrains/recalibrates probabilities, ranks models, selects a winner, defines a promotion threshold, mutates the immutable ledger or affects runtime/learning/telemetry/weights.
- **Adaptive PROD** — ograniczona meta-warstwa ucząca się z zamrożonych, rozliczonych prognoz. Nie nadpisuje RAW Ensemble.
- **Dynamic Weights** — używają poprzedniego snapshotu telemetryki i mają twarde limity przesunięć wag.
- **Early Hold / Serve / Form / Surface / Consensus** — specjalistyczne warstwy statystyczne lub agregujące; nie należy przedstawiać ich jako osobnych retrenowanych modeli ML, jeżeli nimi nie są.
- **Player / Ensemble learning / Surface Elo / Accuracy Lab / NEURO** — warstwy SHADOW pozostające odseparowane od PROD/PLAYABLE, dopóki ich własne bramki walidacyjne nie zostaną spełnione i świadomie zatwierdzone.
- **Symfonia 2.0** — supervised operator-line model z własną historią, exact-line probability i joint probability liczoną tylko na wspieranym wspólnym state-space.

`symphony2_tracker` captures only before an explicit start, then settles frozen
legs using exact archived operator labels or the existing canonical final scorer.
It continues filling unresolved legs after a composition loss without rewriting
that terminal result. Fixture identity, ordered participants, exact schedule and
terminal provenance are mandatory; conflicts remain pending. Calibration uses
only complete binary pre-match evidence and publishes exclusions. This tracker
does not settle operator tickets or iNeed bankrolls. New historical results carry
their source/version; Live API HTTP 410 has a visible seven-day recheck backoff.

Semantyczne granice modeli, sezonów, Player DNA/Player State, opponent context, probability ownership i readiness definiuje `TENIS_AI_LOGIC_CONSTITUTION.md`. Bieżące znane problemy i plan ich napraw definiuje `TENIS_AI_MODEL_DATA_REGISTRY.md`. Aktywny etap, checklisty i punkt wznowienia definiuje `TENIS_AI_EXECUTION_CHECKLIST.md`.

Player DNA scorer and recent-form file ingestion process complete contiguous
match groups from the canonical point dataset, reusing the existing feature
builders without changing row order or model calculations. Noncontiguous repeats
fail explicitly. Player State rereads the iterator for each independent consumer.
This bounds raw-input memory; it is not a training/sample-policy change.
The opponent-strength audit uses the same match-local point ingestion while
building opponent and adjustment indexes once from all profile snapshots.
Immutable per-match/direction feature maps preserve original adjustment-field
precedence; each enriched point has its own writable overlay.
`player_dna_point_scorer.PointDataset` is the repeatable canonical file input for
current scoring and downstream evaluators. Feature joins, match-local enrichment
and label input grouping release each raw match after processing it. Profiles,
rank context and labels can reread the source independently; no shared exhausted
generator or raw-population cache is retained. Reconstruction and model functions
continue to use their existing semantics. The canonical `_frame` helper builds
shared feature mappings column by column, preserving pandas column order, types,
index and missing values without re-expanding every point into another full dict.

## 3. Superbet i PLAYABLE

The market-semantics audit counts exact O/U pairs per market/player/line and
reports one-sided lines separately. It has no PLAYABLE authority. The pre-priced
builder artifact collector keeps its 64-event request budget by selecting verified
future events in deterministic schedule/identity order and recording budget skips;
catalogue growth alone no longer invalidates all exact quotes. Freshness, event
identity and the separate dynamic-quote/reservation gates retain their owners.

The canonical Direct collector (`backend/superbet_direct.py`) shares one incremental
DOM/public-v3 prematch catalogue discovery path with iNeed. Listing JSON is candidate
identity evidence only; exact event payloads still pass the existing participant/time/
ambiguity resolver. `superbet_direct_current.json` retains price-free identity bindings
for current fixtures and diagnostic reason counts. Every quote in `matches` is freshly
read; failure can publish an empty feed with retained identity hints, never renew old
prices. The conservative feed timestamp is refresh start; each included event also has
`observed_at`. A bounded one-time transient transport retry excludes rate limits and
permanent errors. Admin presentation reads the diagnostic projection in existing
`delivery/diagnostics.json`; it does not infer operator availability or PLAYABLE.


Kanoniczne backendowe wejścia operatora to:

- `backend/superbet_market_context.py`
- `backend/superbet_line_coverage.py`
- `backend/superbet_playable.py`

Superbet PR validation is network-free. `Superbet Direct Source Probe` runs only syntax/parser isolation checks on pull requests; its live browser listing probe and selected-match sidecar refresh are guarded with `github.event_name != 'pull_request'`. `superbet_refresh_guard.py` likewise returns `refresh=false` / `pull_request_validation_only` for PR-triggered `Superbet hourly market refresh`, so all refresh-dependent Direct/operator/API/model-refresh/publish steps are skipped. Live operator probing/refresh remains reserved for explicit or other eligible non-PR workflow execution.

PLAYABLE jest warstwą fail-closed: brak zweryfikowanego operator context, brak dokładnej linii albo brak dopasowania selekcji oznacza brak PLAYABLE. Nie wolno używać najbliższej linii ani RAW jako operatorowego fallbacku.

`backend/superbet_playable.py` jest projekcją addytywną. Może dopisać osobne `superbet_playable_v912` i dedykowane warstwy historii PLAYABLE, ale nie może nadpisywać `match_win`, `first_set_win`, `over_under`, `match_over_under`, exact score, `autolearn_v84` ani źródłowych feedów SHADOW. MODEL / RAW pozostaje niezależny od tego, czy Superbet ma dany rynek lub dokładną linię.

Historia PLAYABLE przechowuje wyłącznie zamrożone selekcje operatorowo zweryfikowane. Brak score nie jest interpretowany jako `0`.

### iNeed$ Bet Builder SHADOW contract

Current production iNeed$ remains single-leg economics in `backend/ineed_money.py`; the V1 Supabase signal/place/settlement path is intentionally unchanged.

The V1 intake in `backend/ineed_scope.py` now selects only exact final PLAYABLE match-winner signals; its existing DB insert guard must be migrated to the same market before the runner is activated. Bet Builder SHADOW explicitly selects its separate historical first-set/over/after-six composition scope. Both paths consume upstream probability and exact current Superbet offer without changing the underlying calculations, and neither executes real-money bets.

`backend/ineed_builder_shadow.py` is the additive non-runtime LOGIC-12 owner for the final Bet Builder composition and whole-builder economics. It consumes only final `symphony2_playable`, preserves upstream joint probability, requires canonical match/operator leg identity, accepts only an exact verified + fresh operator combined quote, and never synthesizes combined odds from leg prices.

Phase 2 proves exact pre-priced Superbet `superbets` composition rows and exact component UUID identity. Phase 3 adds the read-only public `v2/getSgaOddPrice` provenance path for arbitrary exact UUID compositions, retaining event, SGA id, component ids and canonical source URL. `backend/superbet_builder_dynamic_quotes.py` is the bounded Phase-3 artifact owner: it intersects final Symphony compositions with the already-verified current Direct feed, requires every exact component UUID, makes at most 8 exact public quote requests per refresh and fails closed before any request if that cap would be exceeded. Its sidecar is metadata-only SHADOW evidence with zero PROD/PLAYABLE/Symphony/iNeed/settlement influence. The hourly Superbet refresh is its delivery host on eligible non-PR runs; pull requests remain network-free through the canonical refresh guard. The sidecar still has no iNeed$/runner consumer and cannot influence runtime, settlement or real betting.

Phase 4 evaluates the whole composition as one SHADOW economic unit: exact combined odds + upstream joint probability -> existing tax/risk semantics -> EV/Kelly/risk/stake -> at most one nonpersisted `SHADOW_PROPOSED` reservation keyed by `builder:<composition_id>`. It emits only `SHADOW_QUALIFIED/SHADOW_REJECTED`, remains `runtime_publishable=false`, and never enters current `ineed-sync`.

Phase 5 adds `backend/ineed_builder_ticket_shadow.py::build_builder_ticket_shadow()` as a pure deterministic envelope owner. It accepts only an exact Phase-4 `SHADOW_QUALIFIED` result matched to the same composition and one whole-builder reservation, then freezes legs, match/player identity, joint probability, exact combined-price provenance, economics snapshot and reservation evidence into `builder-ticket:<composition_id>`.

The Phase-5 ticket is explicitly non-runtime and nonpersistent: `status=SHADOW_TICKET_PROPOSED`, `persistence_ready=false`, `settlement_ready=false`, `settlement_contract_status=NOT_IMPLEMENTED`, `automatic_real_betting=false`. It has no V1 `signal_id` and must not be projected into current `payload.evaluations`, `ineed_signals`, `ineed_shadow_bets` or the existing single-bet settlement RPC.

Phase 6 audits persistence/sync ownership without adding a write path. Any future builder persistence must use a separate experiment-scoped `builder-ticket:<composition_id>` identity plus immutable ticket digest; it must never project the ticket into V1 `ineed_signals` / `ineed_shadow_bets` or current `QUALIFIED` auto-placement.

Replay of identical immutable evidence must be idempotent; an identity/evidence mismatch must fail closed. Ticket persistence and any later reservation require an atomic durable boundary. Reservation remains blocked until shared bankroll/exposure accounting can see both current V1 open bets and builder reservations; current V1 exposure queries see only `ineed_shadow_bets`.

Phase 6 found that deployed `ineed-sync` v10 contains non-core SMTP/email source changes that were absent from Git. The active source-parity step tracks those already-live v10 semantics in Git without deploying the Edge Function: env aliases/fallback sender selection, configuration-state detail and `operator_event_url` email metadata. V1 placement, settlement and exposure semantics remain unchanged.

Source parity and the shared-exposure audit are merged. `backend/ineed_money.py` now owns the normalized backend-only `risk_exposures` read model. If explicit `risk_exposures` is absent, it derives open `V1_SINGLE_BET` rows from current V1 `open_bets`, preserving the existing runtime path. Explicit read-only state can additionally carry `BET_BUILDER_COMPOSITION` rows, and `backend/ineed_builder_shadow.py` consumes this same owner instead of maintaining duplicate exposure parsing.

`open_bets` remains V1-only because the settlement runner consumes it. Available capital remains ledger-derived; when explicit shared exposures are present, equity is reconstructed as available capital plus each open economic stake exactly once. Builder stake counts once toward total/match/player exposure and once against each distinct constituent market. Builder-shaped rows in V1 `open_bets` fail closed. Supabase schema/RPCs, `ineed-sync` and settlement are unchanged; no durable builder exposure, reservation write or Edge deployment is introduced by the read-model step.

The post-read-model atomicity audit freezes the database ownership boundary. Live Supabase verifies that V1 placement and settlement serialize bankroll mutation by locking the same `ineed_experiments` row `FOR UPDATE`; historical Git settlement source was stale and omitted that lock. Any future builder reservation must use the same experiment lock. Production now contains `ineed_builder_tickets` as the durable SHADOW owner, the existing `ineed_bankroll_ledger` as the only ledger with optional builder ownership, and `ineed_open_risk_exposures` as a service-only normalized read source spanning V1 open bets plus future builder `SHADOW_RESERVED` owners.

Production now has the dormant fail-closed SHADOW writer RPC from `20260921123000_ineed_builder_reservation_writer_shadow.sql`, deployed as live migration `20260921134348 ineed_builder_reservation_writer_shadow`; no runtime caller or enable flag was added. The RPC uses the same experiment-row `FOR UPDATE` mutex, validates the immutable Phase-5 ticket, revalidates only the frozen stake against `ineed_open_risk_exposures`, and requires an explicit experiment `builder_reservation` enable flag/version. `ineed_system_place_bet()` and live `ineed-sync::activeState()` continue to use the shared view while preserving V1-only `open_bets` for settlement. At that writer-only checkpoint the production Edge was v11; the later guarded caller rollout is documented below.

The exact builder-quote artifact and ephemeral Phase-4/5 scoped-runner producer are now merged and production-proven. The next persistence/sync boundary is deliberately separate from V1: `backend/ineed_scoped_runner.py` may submit only frozen Phase-5 tickets through the OIDC-authenticated `ineed-sync` action `reserve_builder_tickets`; the runner never receives a Supabase service-role key. `ineed-sync` revalidates the active experiment, `SHADOW`/`superbet.pl`, `automatic_real_betting=false`, the exact `logic12-builder-reservation-shadow-v1` contract version and a bounded unique ticket batch before calling the existing service-role-only `ineed_system_reserve_builder_ticket()` RPC.

Caller source does not mean production enablement. The runner performs zero builder reservation POSTs unless the active experiment contains `builder_reservation.enabled=true` with the exact contract version, and the Edge action independently enforces the same gate. The repository production config intentionally contains no `builder_reservation` block, so the normal runtime remains zero-write for builder persistence. Current V1 `sync`, email, single-bet placement and settlement payloads remain separate and unchanged.

Reservation enablement remains blocked until the whole-ticket settlement/cancel/release contract exists. Persisting `SHADOW_RESERVED` builder stake without a matching lifecycle could strand SHADOW bankroll/exposure even though real-money betting is disabled. Builder settlement therefore remains a mandatory later gate, not something inferred from V1 single-leg semantics.

PR #447 merged the admin-start exposure guard onto `ineed_open_risk_exposures`. PR #448 then repaired the DB-to-Git settlement source-parity drift while preserving the live bet + experiment mutex and V1 settlement semantics; only `other_exposure` moved to the shared view. The final repository-side presentation step keeps `ineed_open_risk_exposures` service-only and exposes only a staff-authorized aggregate RPC for total exposure/open-unit counts, which `frontend/ineed.js` consumes. Before those dormant DB objects are deployed, the frontend falls back to the existing V1-only calculation only for a genuinely missing RPC; all other RPC errors fail closed.



PR #449 merged the staff-only aggregate presentation boundary and PR #450 froze the rollout contract. On 2026-09-21 production received the shared-exposure DB bundle in dependency order, the advisor-driven `builder_ticket_id` FK index, and `ineed-sync` v11. Normal SHADOW workflow run `35596941111` completed GREEN with 41 evaluations, all rejected, zero placements, zero open/risk exposure and `automatic_real_betting=false`.

`TENIS_AI_LOGIC12_DEPLOYMENT_READINESS_AUDIT.md` records the shared-read deployment closeout, and `TENIS_AI_LOGIC12_BUILDER_RESERVATION_WRITER_AUDIT.md` records the later source-only writer boundary. The existing iNeed$ email path (`ineed_email_events` + `QUALIFIED` Gmail SMTP delivery in `ineed-sync`) remains intact. The writer is deployed and remains service-role-only and disabled by absent experiment config. PR #457 later added the guarded caller and the production v12 rollout described below; builder settlement remains absent.

Builder settlement remains `NOT_IMPLEMENTED` until a separate operator-evidence audit proves one-ticket outcome/void/cancel/payout semantics. Real-money execution remains out of scope.

PR #457 merged the separate guarded persistence caller as `3fa6fc5602a1c1cfebbe86a68d6425a8e5c20e2d`. Production `ineed-sync` is ACTIVE v12. Normal SHADOW workflow run `35641902429` proved the absent production gate yields `builder_persistence=DISABLED` / `BUILDER_RESERVATION_DISABLED`, zero builder writes, zero open risk/bets, healthy V1 sync/email and `automatic_real_betting=false`.

The lifecycle operator-evidence audit keeps settlement blocked. Market `238733` and the exact quote artifact are authoritative for pre-match pricing/identity only; active combination rows contain no terminal payout/result field, while sampled completed public events returned no retained `odds`/`oddsResults`. Published generic Bet Builder and later tennis-specific Superbet communications currently describe different void-selection treatment. Therefore V1 settlement, generic leg scoring and Symphony aggregation must not be promoted into a builder ticket result. Missing exact operator terminal evidence is `N/D` and the reservation gate remains OFF.

The active evidence-capture step uses `backend/superbet_builder_terminal_evidence.py` plus `audits/logic12_builder_terminal_evidence_manifest.json` to follow three exact frozen market-238733 identities from Git blob `3f7b5821...` through a bounded post-start observation window. The collector only preserves exact operator UUID-bearing raw evidence or `N/D`; it never interprets a result, computes payout, calls iNeed/Supabase/Edge, or changes settlement authority. Its SHADOW sidecar is `frontend/data/superbet_builder_terminal_evidence.json` and has zero production/PLAYABLE/Symphony/iNeed influence.

## 4. Frontend

The shell also owns the shared readable-report presenter: source values become
escaped labeled fields, expandable groups and bounded pages without changing
source data. Report references are cleared on rerender/logout. Solar is implemented
in the existing canonical stylesheet and shares the existing PWA asset delivery.
No second report source, theme loader or model owner is introduced.

The canonical runtime map is based on the actual `frontend/index.html` imports and delivery producers, not historical filenames.

- `scripts/build_delivery.mjs` - canonical producer of the lightweight UI projection: `data/delivery/index.json`, content-addressed `data/delivery/matches/<sha>.json`, `data/delivery/symphony.json`, and delivery diagnostics.
- `frontend/presentation-data.js` - single presentation/data API `window.TenisPresentation`: JSON reads, exact identity joins, event mapping, operator-price presentation metadata, and final UI availability checks.
- `frontend/runtime-data-transport.js` - transport-only public/dual/private wrapper around `TenisPresentation.json()`; it must not change data meaning or PLAYABLE semantics.
- `frontend/app.js` - owner of the main shell, match list, match detail routes, Symphony presentation, coupon shell, and technical/admin shell. Normal users start from delivery index; full `results.json` remains a technical/admin path.
- `frontend/match-detail-data.js` - read-only helper owner for detail comparison, form, winner-label interpretation, and H2H/history filtering. It must consume published identity/provenance rather than invent cross-provider identity.
- `frontend/account.js` - authentication/profile/role owner used by the shell and feature modules.
- `frontend/neuron-data-bridge.js` - read-only Neuron presentation bridge; Neuron model/training ownership remains backend-side.
- `frontend/history-ui.js` - feature owner of rich snapshot/settlement history on `#history`; `app.js` provides only the host/fallback render.
- `frontend/admin-users.js` - feature owner of the user/staff panel and staff RPC surface mounted into the shell.
- `frontend/ineed.js` - separate staff-only owner of the iNeed$ SHADOW view; iNeed$ calculations remain outside LOGIC-11 and belong to LOGIC-12.
- `frontend/playable-ui.js` - read-only validation of exact Superbet offer/signature and composition. Final authority remains backend `symphony2_playable`; `TenisPresentation.availability()` cannot create PLAYABLE by itself.

Identity joins between current delivery layers must use canonical `id` / `match_id` / `match_key` only. A join is valid only when exactly one matching row exists; missing identity or duplicate/ambiguous identity means no join / N-D. Player names and approximate time are not identity authority for current delivery.

Missing numeric values must stay missing/N-D, never become a real zero. The frontend must not create probability, H2H, odds, complements, or identity that the backend did not explicitly publish. Superbet price is presentation of exact verified operator evidence only and cannot grant PLAYABLE.

Data-freshness timestamps must come from backend `generated_at` / `source_generated_at`. A client clock or decorative date must not be presented as data publication time.

Historical files `project-ui.js`, `match-browser.js`, `match-detail.js`, and `symphony2.js` are not part of the current runtime and must not be cited as current owners.

## 5. Historia i settlement

`rontend/data/history.json` jest głównym źródłem rozliczonych predykcji. Prognozy są zamrażane przed startem meczu, a settlement wykorzystuje jednoznaczny, końcowy wynik. Przy niejednoznacznym dopasowaniu wynik pozostaje nierozliczony zamiast być zgadywany.

`backend/live_history_settle.py` jest kanonicznym ownerem terminalnego wyniku/provenance historii, a `backend/signal_settlement.py::settle_signal_live` kanonicznym scorerem rynku. Prediction Ledger nie redefiniuje tych reguł: phase-3 SHADOW sidecar może wyłącznie konsumować już istniejący terminalny wynik po exact `id:<match_id>` + exact scheduled-time proof. `game_state` nie jest rekonstruowany z finalnych setów; brak dowodu pozostaje `N/D`.


Osobne warstwy SHADOW i Symfonia 2.0 mogą mieć własne historie, ale nie wolno mieszać ich skuteczności z głównym PROD ani ze starą Symfonią.

## 6. Zasada konsolidacji

Nie tworzymy kolejnych plików/modułów `vXXX` jako łat na aktywny runtime. Naprawa trafia do jednego kanonicznego właściciela funkcji, a stara aktywna ścieżka jest usuwana po migracji i zabezpieczeniu testem.

Historyczne nazwy wersji mogą pozostać wyłącznie tam, gdzie są świadomie utrzymanym kontraktem danych, polityką albo odseparowanym eksperymentem. Nie są pretekstem do uruchamiania równoległych hotfixów.

## 7. Kolejność autorytetu dokumentacji

W sprawach pracy agentów i zmiany kodu:

1. `AGENTS.md` — proces i zakazy pracy,
2. `TENIS_AI_LOGIC_CONSTITUTION.md` — znaczenie danych i niezmienne granice odpowiedzialności,
3. `TENIS_AI_MODEL_DATA_REGISTRY.md` — bieżący właściciel, status, known debt i kolejność napraw,
4. `TENIS_AI_EXECUTION_CHECKLIST.md` — aktywny etap, dowody ukończenia, `LIVE CHECKPOINT` i `NEXT EXACT ACTION`,
5. `ARCHITECTURE.md` — bieżąca mapa techniczna,
6. historyczne audyty/plany — materiał dowodowy, nie automatycznie obowiązujący runtime.

Każdy konflikt między dokumentami ma być jawnie rozwiązany w dokumentacji; nie wolno wybierać wygodniejszej wersji po cichu.


### Exact-byte repository publication transport

`scripts/history_publication_chunks.py` owns Git-safe storage for `history.json` and `prediction_ledger_shadow.json`. Its existing workflow restore/pack boundaries preserve each complete source byte-for-byte using separate SHA-256 manifests and 16 MiB parts. Core/market generation restores before consumers and packs before Git staging. Pages restores canonical JSON before runtime snapshot creation and excludes the redundant chunk directories from its artifact. Existing prediction/settlement owners and JSON paths remain unchanged.


The existing Superbet watchdog also accepts successful main Neuron/Player DNA workflow completion as a wakeup when cron is delayed. It checks out main and validates source eligibility before querying Actions; the unchanged orchestration guard decides whether a refresh is actually stale and suppresses concurrent/redundant work. It never consumes source artifacts or changes model/PLAYABLE semantics.


## Self Evolution SHADOW research (proposed, 2026-10-08)

A separate **research-only** read path consumes exact `prediction_ledger_shadow.json` plus `prediction_ledger_settlement_shadow.json`, joins on frozen exact prediction ID and canonical match/schedule, and refuses mismatched SHA/provenance. It trains bounded convex ensembles from Current/CatBoost/TabPFN probabilities on chronologically disjoint whole UTC fixture days with strict settlement-as-of cutoffs. Validation picks a research candidate; holdout only reports descriptive quality against the frozen Current baseline. This module cannot change probability owners, Dynamic Weights, production models, Symfonia, PLAYABLE, iNeed$ or frontend. Daily dedicated GitHub Actions runs produce a short-lived report artifact, not a public PROD data feed. See `docs/SELF_EVOLUTION_SHADOW.md`.


## Self Evolution Phase 2a — market-scoped read-only SHADOW experiment

The canonical `backend/self_evolution_shadow.py` extends its already-frozen global folds into bounded per-market studies, preserving independent fixture-balanced Brier evaluation and strict train/validation/holdout temporal cuts. Separate market IDs are sourced only from frozen ledger fields; missing or unsupported market labels remain absent. The report explicitly declares operator historical quotes N/D and forbids financial P&L, real-money execution, automatic production promotion and changes to probability owners. It remains an isolated Actions artifact, not a new prod pipeline.


## Self Evolution phase 2b — auditable SHADOW memory transport

The same research-only backend/self_evolution_shadow.py extends the nightly
read-only workflow. A prior main-branch success artifact is downloaded
using GitHub CLI with actions:read (no repository write permission), then
the exact frozen ledger and canonical settlement compute two reports.
A bounded versioned research registry and 14-day prospective trial comparison
are persisted as a new 60-day Actions artifact; a candidate may become an
internal SHADOW-only champion after strict independent-fixture validation.
No output affects production model, weights, Symphony, PLAYABLE, iNeed,
Superbet price authority or live betting. No bookmaker EV/ROI is inferred.


## Self Evolution phase 2c — quote evidence transport (research only)

Canonical price owners remain superbet_direct.py,
superbet_builder_quotes.py and superbet_builder_dynamic_quotes.py.
Passive archivist superbet_quote_evidence.py consumes their post-refresh
read-only JSON, requires exact event/selection identity and observed
pre-match operator odds, then emits run-scoped GitHub Actions evidence
artifact (60-day retention). It does not query bookmaker endpoints, change
model, operator authority, Symphony, PLAYABLE, iNeed, settlement or real
bets. Join to a prospectively frozen prediction-decision ledger and
economic outcomes is NOT yet authorized.

## Self Evolution UI — administrator research status

An admin-only route `#admin/evolution` lives inside the existing authenticated
`frontend/app.js` shell. Public Actions metadata and actual research evidence are
separate sources. The existing private-runtime publisher now has a `research`
provenance layer triggered by a successful main Self Evolution run, or manually
backfilled from its last success. `scripts/project_self_evolution_ui.py` verifies
run identity, report/memory digest, timestamps and isolation flags, then copies
only bounded scalar metrics and retained trial decisions. The single resulting
`data/self_evolution_ui.json` is tier C and always uses the private reader, even
when ordinary app data transport is public; it has no public fallback. The
existing authenticated reader enforces admin access. Raw research artifacts,
weights and training samples are not copied into the UI report.

The UI distinguishes historical Brier from prospective trials and shows the
original report date, sample sizes, deadline and decision. Missing evidence stays
N/D and ROI stays unevaluated. Research/training, model authority and promotion
rules are unchanged. No new trainer, real bets or probability owner is introduced.

## App reliability and presentation preferences — 2026-10-16

The canonical app commits a new match publication only after its bounded index
read validates. Failed reads retain the previous view with an explicit unconfirmed
status; they never change source timestamps. Retries are bounded, and online/
foreground events recheck old snapshots. Logout/account-generation checks discard
late responses. Availability explanations annotate the unchanged existing
PLAYABLE expression; they do not introduce a second decision gate.

Admin report routes use existing content-addressed per-match bundles on selection
instead of loading `results.json`. The small index includes original Direct and
AutoLearn timestamps for the shared status panel. `ui_preferences` stores one
owner-scoped key per filter/favourite with RLS and no anonymous access. Pending
device changes merge by key and survive network errors; account epochs prevent
late cross-account writes into the UI. Optional problem notices are off by
default and work while the app is running; background push delivery is not claimed.


## Exact participant-name settlement boundary (2026-10-12)

The shared `signal_settlement.resolve_player_side` matches all normalized full-name tokens against exactly one of two distinct fixture participants. Named winner, handicap and player-total scorers use this single resolver; `ineed_settlement_runner` delegates its compatibility input projection to the same owner. Partial, unknown and ambiguous names cannot become a loss by default.

The existing history reconciliation stage applies the authorized display-order-only correction to affected archived labels before downstream training. Original label/source and correction provenance are retained on each changed signal; prediction inputs and archived terminal result are unchanged. It never calls Supabase or changes iNeed bankroll records. Symphony training rejects unresolved named identities and publishes correction counts. No additional prediction/settlement path exists.


### Private-runtime compression deployment
Large-file transport accepts legacy base64 and gzip-base64 manifests while preserving exact source bytes and original SHA-256 verification. The canonical reader bounds gzip expansion to the declared chunk size, at most 20 MiB. Roll out the compatible frontend and its PWA cache revision first, confirm Pages deployment, then enable compressed writes in the existing OIDC publisher. Existing atomic generation activation and GC stay authoritative. Rollback republishes the same canonical source through the prior writer while retaining the backward-compatible reader.

Compressed history chunks use `json-array-gzip-base64-chunks-v1`; the compatible reader retains the legacy array format, verifies each original chunk hash/length and entry count, and decodes sequentially to bound transient memory. Both history and oversized exact-JSON chunks use one bounded decoder. Original source files and their record order are unchanged.

The writer applies deterministic gzip (level 6, mtime 0) to the original history chunk bytes and oversized exact-JSON blocks through one envelope encoder. History manifest hashes/lengths continue describing the original uncompressed chunk, and `entries` retains the original array count. Deployment uses the unchanged single-layer OIDC workflow: DNA, existing GC, core, existing GC. No authorization or workflow changes are needed.
