# Tenis AI — kanoniczna architektura

> **Zasady nadrzędne:** przed zmianą kodu obowiązkowo przeczytaj `AGENTS.md`, `TENIS_AI_LOGIC_CONSTITUTION.md`, `TENIS_AI_MODEL_DATA_REGISTRY.md` oraz `TENIS_AI_EXECUTION_CHECKLIST.md`. Ten plik opisuje bieżącą architekturę techniczną. Jeżeli bieżący runtime lub poniższa mapa jest sprzeczna z konstytucją/rejestrem, nie wolno zgadywać ani tworzyć obejścia — rozjazd jest bugiem dokumentacji/architektury i musi zostać jawnie zbadany. `TENIS_AI_EXECUTION_CHECKLIST.md` określa natomiast aktywny etap, checkpoint i dokładny punkt wznowienia pracy.

## 1. Produkcja danych

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
- **Prediction Ledger SHADOW** - canonical prospective evidence owner `backend/prediction_ledger_shadow.py`; captures the first stable pre-match Current/CatBoost/TabPFN prediction per supported candidate before downstream selection. `backend/prediction_ledger_selection_shadow.py` adds exact positive PLAYABLE/Symphony population evidence only from frozen canonical owners with strict pre-match chronology; missing evidence is `N/D`. `backend/prediction_ledger_settlement_shadow.py` is the additive phase-3 common-set consumer: it joins only exact Live Tennis `id:<match_id>` + exact schedule to already-terminal canonical history and delegates hit/miss/void semantics to `signal_settlement.settle_signal_live`. All three layers are SHADOW-only, keep the source ledger immutable, and have zero runtime/learning/telemetry/weight ownership.
- **Adaptive PROD** — ograniczona meta-warstwa ucząca się z zamrożonych, rozliczonych prognoz. Nie nadpisuje RAW Ensemble.
- **Dynamic Weights** — używają poprzedniego snapshotu telemetryki i mają twarde limity przesunięć wag.
- **Early Hold / Serve / Form / Surface / Consensus** — specjalistyczne warstwy statystyczne lub agregujące; nie należy przedstawiać ich jako osobnych retrenowanych modeli ML, jeżeli nimi nie są.
- **Player / Ensemble learning / Surface Elo / Accuracy Lab / NEURO** — warstwy SHADOW pozostające odseparowane od PROD/PLAYABLE, dopóki ich własne bramki walidacyjne nie zostaną spełnione i świadomie zatwierdzone.
- **Symfonia 2.0** — supervised operator-line model z własną historią, exact-line probability i joint probability liczoną tylko na wspieranym wspólnym state-space.

Semantyczne granice modeli, sezonów, Player DNA/Player State, opponent context, probability ownership i readiness definiuje `TENIS_AI_LOGIC_CONSTITUTION.md`. Bieżące znane problemy i plan ich napraw definiuje `TENIS_AI_MODEL_DATA_REGISTRY.md`. Aktywny etap, checklisty i punkt wznowienia definiuje `TENIS_AI_EXECUTION_CHECKLIST.md`.

## 3. Superbet i PLAYABLE

Kanoniczne backendowe wejścia operatora to:

- `backend/superbet_market_context.py`
- `backend/superbet_line_coverage.py`
- `backend/superbet_playable.py`

PLAYABLE jest warstwą fail-closed: brak zweryfikowanego operator context, brak dokładnej linii albo brak dopasowania selekcji oznacza brak PLAYABLE. Nie wolno używać najbliższej linii ani RAW jako operatorowego fallbacku.

`backend/superbet_playable.py` jest projekcją addytywną. Może dopisać osobne `superbet_playable_v912` i dedykowane warstwy historii PLAYABLE, ale nie może nadpisywać `match_win`, `first_set_win`, `over_under`, `match_over_under`, exact score, `autolearn_v84` ani źródłowych feedów SHADOW. MODEL / RAW pozostaje niezależny od tego, czy Superbet ma dany rynek lub dokładną linię.

Historia PLAYABLE przechowuje wyłącznie zamrożone selekcje operatorowo zweryfikowane. Brak score nie jest interpretowany jako `0`.

### iNeed$ Bet Builder SHADOW contract

Current production iNeed$ remains single-leg economics in `backend/ineed_money.py`; the V1 Supabase signal/place/settlement path is intentionally unchanged.

`backend/ineed_builder_shadow.py` is the additive non-runtime LOGIC-12 owner for the final Bet Builder composition and whole-builder economics. It consumes only final `symphony2_playable`, preserves upstream joint probability, requires canonical match/operator leg identity, accepts only an exact verified + fresh operator combined quote, and never synthesizes combined odds from leg prices.

Phase 2 proves exact pre-priced Superbet `superbets` composition rows and exact component UUID identity. Phase 3 adds the read-only public `v2/getSgaOddPrice` provenance path for arbitrary exact UUID compositions, retaining event, SGA id, component ids and canonical source URL. No runner/frontend/settlement consumer is introduced.

Phase 4 evaluates the whole composition as one SHADOW economic unit: exact combined odds + upstream joint probability -> existing tax/risk semantics -> EV/Kelly/risk/stake -> at most one nonpersisted `SHADOW_PROPOSED` reservation keyed by `builder:<composition_id>`. It emits only `SHADOW_QUALIFIED/SHADOW_REJECTED`, remains `runtime_publishable=false`, and never enters current `ineed-sync`.

Phase 5 adds `backend/ineed_builder_ticket_shadow.py::build_builder_ticket_shadow()` as a pure deterministic envelope owner. It accepts only an exact Phase-4 `SHADOW_QUALIFIED` result matched to the same composition and one whole-builder reservation, then freezes legs, match/player identity, joint probability, exact combined-price provenance, economics snapshot and reservation evidence into `builder-ticket:<composition_id>`.

The Phase-5 ticket is explicitly non-runtime and nonpersistent: `status=SHADOW_TICKET_PROPOSED`, `persistence_ready=false`, `settlement_ready=false`, `settlement_contract_status=NOT_IMPLEMENTED`, `automatic_real_betting=false`. It has no V1 `signal_id` and must not be projected into current `payload.evaluations`, `ineed_signals`, `ineed_shadow_bets` or the existing single-bet settlement RPC.

Phase 6 audits persistence/sync ownership without adding a write path. Any future builder persistence must use a separate experiment-scoped `builder-ticket:<composition_id>` identity plus immutable ticket digest; it must never project the ticket into V1 `ineed_signals` / `ineed_shadow_bets` or current `QUALIFIED` auto-placement.

Replay of identical immutable evidence must be idempotent; an identity/evidence mismatch must fail closed. Ticket persistence and any later reservation require an atomic durable boundary. Reservation remains blocked until shared bankroll/exposure accounting can see both current V1 open bets and builder reservations; current V1 exposure queries see only `ineed_shadow_bets`.

Phase 6 found that deployed `ineed-sync` v10 contains non-core SMTP/email source changes that were absent from Git. The active source-parity step tracks those already-live v10 semantics in Git without deploying the Edge Function: env aliases/fallback sender selection, configuration-state detail and `operator_event_url` email metadata. V1 placement, settlement and exposure semantics remain unchanged.

Source parity and the shared-exposure audit are merged. `backend/ineed_money.py` now owns the normalized backend-only `risk_exposures` read model. If explicit `risk_exposures` is absent, it derives open `V1_SINGLE_BET` rows from current V1 `open_bets`, preserving the existing runtime path. Explicit read-only state can additionally carry `BET_BUILDER_COMPOSITION` rows, and `backend/ineed_builder_shadow.py` consumes this same owner instead of maintaining duplicate exposure parsing.

`open_bets` remains V1-only because the settlement runner consumes it. Available capital remains ledger-derived; when explicit shared exposures are present, equity is reconstructed as available capital plus each open economic stake exactly once. Builder stake counts once toward total/match/player exposure and once against each distinct constituent market. Builder-shaped rows in V1 `open_bets` fail closed. Supabase schema/RPCs, `ineed-sync` and settlement are unchanged; no durable builder exposure, reservation write or Edge deployment is introduced by the read-model step.

The post-read-model atomicity audit freezes the database ownership boundary. Current V1 placement and settlement already serialize bankroll mutation by locking the same `ineed_experiments` row `FOR UPDATE`; any future builder reservation must use that same experiment lock. The repository now carries a **dormant, not-yet-deployed** schema migration defining `ineed_builder_tickets` as the durable owner, the existing `ineed_bankroll_ledger` as the only ledger with optional builder ownership, and `ineed_open_risk_exposures` as a `security_invoker` read source spanning V1 open bets plus builder `SHADOW_RESERVED` owners.

The dormant schema has no writer/RPC and grants no builder-table write path. The current repository candidate now migrates two risk readers to the shared source without enabling writes: `ineed_system_place_bet()` reads total/match/player/market exposure from `ineed_open_risk_exposures`, and `ineed-sync::activeState()` reads the same view into `risk_exposures` for exposure/equity. `open_bets` deliberately remains V1-only from `ineed_shadow_bets` because the settlement runner consumes full V1 bet rows. The candidate Edge source is not deployed; live remains v10.

A repo-wide consumer audit also identifies three remaining pre-writer readers: `ineed_admin_start_experiment()` still checks V1-only open exposure, V1 settlement `other_exposure` bookkeeping is V1-only, and `frontend/ineed.js` presents V1 bet exposure only. These are explicit blockers before any builder reserve writer is enabled; they are not silently changed by the placement/Edge reader step.

Builder settlement remains `NOT_IMPLEMENTED` until a separate operator-evidence audit proves one-ticket outcome/void/cancel/payout semantics. Real-money execution remains out of scope.

## 4. Frontend

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
