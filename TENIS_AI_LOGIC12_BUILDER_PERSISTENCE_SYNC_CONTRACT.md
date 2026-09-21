# LOGIC-12 - Builder persistence/sync caller contract

Status: **SHADOW SOURCE CONTRACT IN PROGRESS - PRODUCTION GATE REMAINS DISABLED**

## Scope

This step connects the already-production-proven Phase-5 `builder-ticket` envelope to the already-deployed atomic SHADOW reservation writer without changing V1 single-bet semantics. It introduces no model/probability/risk-math changes, no schema migration, no builder settlement and no real-money execution.

## Existing durable owner

`public.ineed_system_reserve_builder_ticket(uuid,jsonb)` remains the only builder reservation writer. It is service-role-only, serializes on the active `ineed_experiments` row, validates immutable ticket evidence, rechecks shared exposure limits, and is idempotent for the same ticket digest. This step does not create a second writer.

## Credential boundary

The GitHub runner must never receive a Supabase service-role key. Builder persistence can travel only through the existing GitHub OIDC trust boundary:

`ineed-shadow.yml -> backend/ineed_scoped_runner.py -> OIDC ineed-sync -> service-role RPC`

The Edge function remains the only layer allowed to hold service-role credentials.

## Runner gate

`sync_builder_ticket_reservations()` performs zero POSTs unless the active experiment has:

- `builder_reservation.enabled == true`, and
- `builder_reservation.contract_version == logic12-builder-reservation-shadow-v1`.

A missing/false flag returns `BUILDER_RESERVATION_DISABLED`; a mismatched version returns `BUILDER_RESERVATION_CONTRACT_MISMATCH`. The repository production config intentionally contains no `builder_reservation` block, so the current production path is zero-write.

The builder action is separate from the unchanged V1 action. Builder tickets are never added to V1 `payload.evaluations` or `payload.settlements`.

## Edge gate

The new source action is `reserve_builder_tickets`. Before any RPC call, `ineed-sync` revalidates:

- active experiment id,
- operator `superbet.pl`,
- mode `SHADOW`,
- exact reservation contract version,
- `automatic_real_betting == false`,
- the same experiment-level enable flag/version,
- array shape, maximum batch size and unique non-empty ticket keys.

Only then may it call `ineed_system_reserve_builder_ticket`. Returned writer states are limited to `RESERVED` or `IDEMPOTENT`; anything else fails closed.

## Isolation invariants

- V1 `sync` request/response shape remains separate.
- V1 `ineed_system_place_bet` behavior is unchanged.
- V1 settlement runner is unchanged and has no builder-ticket consumer.
- Builder action does not call `flushEmails`; the existing QUALIFIED Gmail path stays V1-only.
- `automatic_real_betting=false` remains mandatory at runner, Edge and writer boundaries.
- No builder settlement is inferred from V1 single-leg settlement.

## Why enablement remains blocked

The database writer creates durable `SHADOW_RESERVED` ownership and subtracts reserved stake from the shared bankroll ledger. Builder whole-ticket settlement/cancel/release semantics are still `NOT_IMPLEMENTED`. Enabling reservations before that lifecycle exists could strand SHADOW capital/exposure indefinitely.

Therefore this PR may add the caller/sync source contract, but it must not add `builder_reservation.enabled=true` to production. Edge deployment, if performed after merge, must keep the flag disabled and prove zero builder writes.

## Rollout gates

1. Focused caller/persistence tests.
2. Full iNeed regression pack.
3. Full repository pytest + normal CI/security/UI gates.
4. Fresh-main check immediately before merge.
5. Post-merge Edge deployment with reservation flag still disabled.
6. Normal SHADOW proof: builder persistence reports disabled/no writes; builder rows/exposure remain zero; V1/email/runtime health unchanged.
7. Separate future settlement/lifecycle design and validation before any reservation enablement.

## Hard bans

No changes to model math, probability, thresholds, weights, training, Player DNA, Surface Elo, Symphony, Neuron, PLAYABLE, V1 risk calculations or current settlement semantics. No real-money execution.
