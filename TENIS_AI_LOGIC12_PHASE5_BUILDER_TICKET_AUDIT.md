# LOGIC-12 Phase 5 — Builder Ticket SHADOW audit

Status: **LOCAL FULL GREEN / NON-RUNTIME — EXACT-HEAD PR CI PENDING**

## Current V1 ownership proof

Current iNeed$ persistence is structurally single-leg:

- `supabase/migrations/20260910221444_ineed_v1.sql` stores `ineed_shadow_bets.signal_id` as a unique foreign key to `ineed_signals`.
- `supabase/migrations/20260910222554_ineed_v1_risk_guards.sql::ineed_system_place_bet(target_signal_id)` requires one V1 signal with status `QUALIFIED`, creates one shadow bet and reserves bankroll for that signal.
- `supabase/functions/ineed-sync/index.ts` upserts each `payload.evaluations[]` row as an `ineed_signal`; any `QUALIFIED` evaluation is immediately passed to `ineed_system_place_bet`.
- `ineed_system_settle_bet()` settles one `ineed_shadow_bets` row and propagates the outcome back to its one `signal_id`.
- `backend/ineed_settlement_runner.py` and `backend/ineed_money.py::build_settlements()` currently settle individual open V1 bets.

Therefore a final Bet Builder must not be represented as a fake V1 signal or fake `market=BET_BUILDER` row. Doing so would preserve the wrong economic/persistence/settlement unit.

## Phase-5 bounded objective

Phase 5 defines only a pure SHADOW **builder-ticket envelope**. It is not persistence and it is not settlement.

Input must be both:

1. the exact final builder composition containing canonical legs and exact combined-price provenance, and
2. the matching Phase-4 whole-builder `SHADOW_QUALIFIED` economics result containing exactly one reservation proposal.

The ticket retains, without recomputation:

- deterministic identity `builder-ticket:<composition_id>`,
- operator/match/player identity,
- exact canonical legs,
- upstream Symphony joint probability,
- exact operator combined odds and timestamp,
- exact source event, SGA/combination selection ID and component UUIDs,
- Phase-4 economics/risk snapshot,
- exactly one whole-ticket reservation proposal.

## Canonical owner

`backend/ineed_builder_ticket_shadow.py::build_builder_ticket_shadow()` is the sole Phase-5 owner.

It only freezes already-verified Phase-4 evidence. It has no database, network, runner, settlement, workflow or frontend dependency and creates no side effect.

## RED → GREEN evidence

The test-only commit `846818991a9f1d0c26c3d4d380d25c1dfb463e17` intentionally omitted the owner module. Executing `tests/test_ineed_builder_ticket_shadow.py` in isolation failed during collection exactly as designed:

`ModuleNotFoundError: No module named 'backend.ineed_builder_ticket_shadow'`

The same exact test file executed with the implementation from commit `ff9b1479aacaaf033352e58108f855046f414d9b` passes **11/11 GREEN**.

The isolated executable proof validates:

- one deterministic ticket from exact Phase-4 evidence,
- rejection of V1 `QUALIFIED` and all non-Phase-4 statuses,
- identity/joint/odds mismatch rejection,
- exactly one whole-builder reservation,
- exact operator quote provenance and unique component UUIDs,
- complete verified leg contract,
- no V1 signal-shaped or settlement-shaped top-level fields,
- deterministic deep-copy behavior.

After `MaDMachiN` returned online, the branch was rebased onto fresh data-only main `e7cf3153...`. Local validation is GREEN: Phase 4+5 focused **38/38**, broad iNeed$/Superbet/Symphony **410/410**, and full repository **1399/1399**. The previous remote Phase-5 head `89e2f2f7...` also has iNeed$ SHADOW bankroll, CodeQL, Delivery/Security and UI/Project Health GREEN. Because the branch was rebased and documentation updated afterward, PR #438 is **not merge-ready** until the final pushed exact head receives all required GREEN CI and fresh `main` still equals the PR base.

## Fail-closed rules

Do not create a ticket if any of these are false:

- composition and economics identity agree exactly,
- evaluation status is exactly `SHADOW_QUALIFIED`, never V1 `QUALIFIED`,
- operator is `superbet.pl`, mode is `SHADOW`,
- at least two verified legs have exact operator market/outcome identity,
- quote provenance is operator-verified and freshness-verified,
- component UUID count equals leg count and UUIDs are unique,
- exact SGA/combination selection ID, source event and source URL are present,
- final stake is positive and equals the one reservation amount,
- reservation key is exactly `builder:<composition_id>`,
- source evidence remains non-runtime and real betting remains disabled.

## Explicit non-goals

Phase 5 does **not**:

- add/alter Supabase schema or RPCs,
- alter `ineed-sync`,
- alter current single-leg iNeed$ calculations,
- alter current settlement logic,
- define WIN/LOSS/VOID/CANCELLED rules for a multi-leg ticket,
- publish to frontend/runtime,
- reserve bankroll,
- execute any real-money transaction.

Ticket output explicitly states:

- `runtime_publishable=false`,
- `persistence_ready=false`,
- `settlement_ready=false`,
- `settlement_contract_status=NOT_IMPLEMENTED`,
- `automatic_real_betting=false`.

Settlement semantics, especially void/push/cancel/retirement behavior for correlated builder legs, require a separate audited phase and operator evidence before implementation.
