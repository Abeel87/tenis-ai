# LOGIC-12 Phase 5 — Builder Ticket SHADOW audit

Status: **RED CONTRACT / NON-RUNTIME**

## Current V1 ownership proof

Current iNeed$ persistence is structurally single-leg:

- `supabase/migrations/20260910221444_ineed_v1.sql` stores `ineed_shadow_bets.signal_id` as a unique foreign key to `ineed_signals`.
- `supabase/migrations/20260910222554_ineed_v1_risk_guards.sql::ineed_system_place_bet(target_signal_id)` requires one V1 signal with status `QUALIFIED`, creates one shadow bet and reserves bankroll for that signal.
- `supabase/functions/ineed-sync/index.ts` upserts each `payload.evaluations[]` row as an `ineed_signal`; any `QUALIFIED` evaluation is immediately passed to `ineed_system_place_bet`.
- `ineed_system_settle_bet()` settles one `ineed_shadow_bets` row and propagates the outcome back to its one `signal_id`.
- `backend/ineed_settlement_runner.py` and `backend/ineed_money.py::build_settlements()` currently settle individual open V1 bets.

Therefore a final Bet Builder must not be represented as a fake V1 signal or fake `market=BET_BUILDER` row. Doing so would preserve the wrong economic/persistence/settlement unit.

## Phase-5 bounded objective

Phase 5 first defines only a pure SHADOW **builder-ticket envelope**. It is not persistence and it is not settlement.

Input must be both:

1. the exact final builder composition containing canonical legs and exact combined-price provenance, and
2. the matching Phase-4 whole-builder `SHADOW_QUALIFIED` economics result containing exactly one reservation proposal.

The ticket must retain, without recomputation:

- deterministic identity `builder-ticket:<composition_id>`,
- operator/match/player identity,
- exact canonical legs,
- upstream Symphony joint probability,
- exact operator combined odds and timestamp,
- exact source event, SGA/combination selection ID and component UUIDs,
- Phase-4 economics/risk snapshot,
- exactly one whole-ticket reservation proposal.

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
- all source rows remain `runtime_publishable=false` and `automatic_real_betting=false`.

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

Ticket output must explicitly state:

- `runtime_publishable=false`,
- `persistence_ready=false`,
- `settlement_ready=false`,
- `settlement_contract_status=NOT_IMPLEMENTED`,
- `automatic_real_betting=false`.

Settlement semantics, especially void/push/cancel/retirement behavior for correlated builder legs, require a separate audited phase and operator evidence before implementation.
