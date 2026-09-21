# LOGIC-12 — SHADOW builder reservation writer audit

## 1. Scope

This step implements the previously audited **database reservation writer only**.
It does not wire a runtime caller, does not enable the writer in the active experiment,
does not implement builder settlement, and does not enable real-money execution.

Repository owner:

- `supabase/migrations/20260921123000_ineed_builder_reservation_writer_shadow.sql`
- RPC: `public.ineed_system_reserve_builder_ticket(uuid,jsonb)`
- access: `service_role` only
- production deployment in this PR: **NO**

The existing V1 signal/place/settlement path remains authoritative and unchanged.

## 2. Enablement boundary

The RPC is fail-closed unless the locked experiment config contains both:

- `builder_reservation.enabled = true`
- `builder_reservation.contract_version = logic12-builder-reservation-shadow-v1`

The currently active production SHADOW experiment has no `builder_reservation` config block,
so even a future schema deployment would not by itself authorize a reservation.

## 3. Transaction and ownership

The RPC locks the target `ineed_experiments` row `FOR UPDATE`, the same serialization
mutex used by V1 placement and settlement. Under that lock it:

1. validates ACTIVE + SHADOW + `superbet.pl`,
2. requires real betting to remain disabled,
3. validates the frozen Phase-5 ticket and exact reservation proposal,
4. derives deterministic ticket/reservation identity,
5. computes the immutable SHA-256 digest in PostgreSQL,
6. resolves replay/conflict before any new debit,
7. reads latest available capital and shared open exposure,
8. revalidates the already-frozen stake against current unchanged iNeed$ caps,
9. inserts one `SHADOW_RESERVED` builder owner,
10. inserts exactly one `STAKE_RESERVED` ledger debit.

The owner and debit are in one PostgreSQL function transaction: either both commit or neither.

## 4. Replay contract

- same experiment + same `ticket_key` + same DB digest + valid reservation ledger row -> `IDEMPOTENT`,
- same identity + different digest -> `IMMUTABLE_TICKET_CONFLICT`,
- missing/inconsistent existing debit -> fail closed,
- no client retry id or inferred client-side success is used.

## 5. Risk revalidation

The writer does **not** recompute model probability, Symphony joint probability,
operator combined odds, EV, Kelly or the proposed stake.

It revalidates the immutable `final_stake` only against current bankroll state using
`ineed_open_risk_exposures` and the existing experiment configuration:

- available capital,
- risk state / drawdown,
- single-unit cap,
- total exposure cap,
- same-match cap,
- overlapping-player cap,
- each distinct constituent market cap.

A builder stake is counted once as one economic exposure. For concentration, that same
full stake must fit independently under every distinct market dimension in the ticket.
If the frozen stake no longer fits, the RPC rejects it instead of resizing the ticket.

## 6. Runtime isolation

No caller is added to `ineed-sync`, `ineed_scoped_runner`, workflows or frontend.
`open_bets` remains V1-only and builder settlement remains `NOT_IMPLEMENTED`.
The current V1 settlement runner must never consume a `SHADOW_RESERVED` builder owner.

`automatic_real_betting=false` remains mandatory in experiment and ticket evidence.

## 7. Acceptance boundary for this PR

Required before merge:

- writer contract tests GREEN,
- existing Phase-5/Phase-6/shared-exposure/V1 isolation tests GREEN,
- full iNeed pack GREEN,
- full repository pytest GREEN,
- UI static smoke GREEN,
- Project Health GREEN,
- exact-head GitHub CI GREEN,
- fresh-main equality immediately before merge.

No live Supabase DDL or Edge deployment is part of this PR.

## 8. Next step after merge

Do not enable the active experiment flag and do not add a runtime caller automatically.
A later controlled step must decide lifecycle semantics for an open reserved builder while
one-ticket settlement is still unavailable. Deployment/enablement needs its own explicit
proof and must preserve SHADOW-only behavior.

Builder one-ticket settlement and real-money execution remain out of scope.
