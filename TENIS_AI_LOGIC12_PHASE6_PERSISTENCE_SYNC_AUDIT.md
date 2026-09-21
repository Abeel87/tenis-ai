# LOGIC-12 Phase 6 — Builder-ticket persistence/sync audit

Status: **AUDIT + CONTRACT DESIGN ONLY — NO WRITE IMPLEMENTATION**

Audit base: `06d0b06579b95d4a23106f2173ccd4e991558aa3` (Phase-5 closeout merged).

## 1. Scope and non-goals

Phase 6 audits the real current iNeed$ V1 persistence boundary and defines the minimum safe contract for a future SHADOW builder-ticket persistence/sync path.

This phase does **not**:

- create or alter a Supabase table, RPC, trigger, policy or migration,
- deploy or alter an Edge Function,
- wire `backend/ineed_builder_ticket_shadow.py` into a runner/workflow,
- reserve bankroll or create exposure,
- define or execute builder settlement,
- change current single-leg iNeed$ calculations,
- change PLAYABLE, Symphony probability, Current Engine or any model math,
- promote SHADOW to PROD,
- enable real-money execution.

Phase-5 output remains immutable evidence with `persistence_ready=false`, `settlement_ready=false`, `settlement_contract_status=NOT_IMPLEMENTED` and `automatic_real_betting=false`.

## 2. Current V1 runtime truth

GitHub source and live Supabase were both inspected read-only. The live project is healthy on PostgreSQL 17 and the deployed `ineed-sync` Edge Function is ACTIVE version 10.

Current V1 remains structurally single-leg:

- `ineed_signals` is unique on `(experiment_id, fingerprint)` and stores one `match_id / market / selection` decision.
- `ineed_decision_snapshots` is unique on `(signal_id, snapshot_hash)`.
- `ineed_shadow_bets.signal_id` is a unique foreign key: one persisted V1 bet per signal.
- `ineed_bankroll_ledger` is unique on `(experiment_id, source_key)`.
- `ineed_email_events` is unique on `(signal_id, event_type, revision)`.
- all current iNeed$ tables have RLS enabled in the live database.
- the live insert trigger on `ineed_shadow_bets` permits only the approved single-leg scope: `set1_winner`, `set1_total/over`, or checkpoint-6 non-tied `game_state`.

Live `ineed_system_place_bet(target_signal_id)` requires one `QUALIFIED` V1 signal, checks existing `ineed_shadow_bets.signal_id` for idempotency, computes V1 exposure and inserts one bet plus one `STAKE_RESERVED` ledger row.

Live `ineed_system_settle_bet(target_bet_id, ...)` locks and settles one V1 bet, is terminal-status idempotent, writes `settle:<bet_id>` to the ledger and propagates the terminal status back to that bet's single `signal_id`.

Therefore the live database itself proves that a builder ticket cannot be represented faithfully as a fake V1 signal or fake `market=builder` row.

## 3. Current sync and replay semantics

The repository runner sends only V1 `evaluations[]` and `settlements[]`. The deployed Edge Function preserves the same persistence contract:

1. validate GitHub OIDC against the expected repository, `main` ref and iNeed$ workflow,
2. load the active experiment,
3. process `payload.settlements[]`,
4. upsert `payload.evaluations[]` by `(experiment_id, fingerprint)`,
5. automatically call `ineed_system_place_bet` for a non-protected `QUALIFIED` evaluation,
6. deduplicate decision snapshots and email events by their existing unique keys.

Current replay protection is therefore V1-specific and distributed across signal fingerprint, signal-to-bet uniqueness, snapshot hash, ledger source key, email key and terminal settlement status.

There is no durable builder-ticket identity, builder-ticket digest, builder reservation row or builder replay state in the current runtime.

A future builder sync must not append builder tickets to `payload.evaluations[]`: `QUALIFIED` has V1 auto-placement semantics, while Phase-5 deliberately emits `SHADOW_TICKET_PROPOSED` and no V1 `signal_id`, `fingerprint`, `market` or `selection`.

## 4. Deployed Edge Function source drift

The live `ineed-sync` version 10 contains non-core SMTP/env fallback and email metadata changes (`firstEnv`, extra Gmail env aliases and `operator_event_url`) that are not present in any currently fetched Git branch containing `supabase/functions/ineed-sync/index.ts`.

Its persistence core still matches the audited V1 contract, but the deployed source is not byte/source-identical to repository `main`.

**Hard precondition for any future Edge deployment:** first reconcile deployed v10 back into Git in a separate no-behavior-change source-parity PR and prove the persistence core plus current email behavior are preserved. Do not overwrite production from the older repository copy.

## 5. Future logical persistence identity

Phase 6 freezes a **logical contract**, not SQL names.

A future builder persistence object must be separate from V1 `ineed_signals` / `ineed_shadow_bets` and must preserve:

- `experiment_id` — experiment ownership,
- `ticket_key = builder-ticket:<composition_id>` — deterministic ticket identity from Phase 5,
- `composition_id` — canonical composition identity,
- `ticket_digest` — deterministic digest of the complete immutable Phase-5 ticket evidence,
- frozen exact legs and component UUIDs,
- frozen operator event / SGA-combination provenance,
- frozen joint probability and exact combined price,
- frozen Phase-4 economics and exactly one reservation proposal,
- explicit SHADOW-only and real-betting-disabled flags.

The logical uniqueness boundary is one `(experiment_id, ticket_key)`. `composition_id` and `ticket_key` must agree deterministically; aliases, nearest matching and name-based matching are forbidden.

A future persisted status must remain explicitly SHADOW. It must not reuse V1 `QUALIFIED`, `PENDING`, `WIN`, `LOSS`, `VOID` or `CANCELLED` to imply semantics that have not been implemented for a builder ticket.

The immutable Phase-5 ticket itself is not rewritten to claim `persistence_ready=true`; persistence state belongs to a separate future persistence record.

## 6. Replay and conflict contract

Required behavior for a future transactional persistence endpoint:

- same `(experiment_id, ticket_key)` + same `ticket_digest` -> `IDEMPOTENT`, zero duplicate write and zero second reservation,
- same `(experiment_id, ticket_key)` + different `ticket_digest` -> fail closed as `IMMUTABLE_TICKET_CONFLICT`, never overwrite,
- ticket/composition identity disagreement -> fail closed before any durable side effect,
- two concurrent requests for the same ticket -> exactly one durable ticket and at most one reservation,
- failure before transaction commit -> no durable ticket/reservation effect,
- response loss after commit -> retry returns `IDEMPOTENT` from durable state,
- retry after a partial external/network failure must never infer success from client memory,
- no replay may re-price, re-run Symphony, resize stake or mutate frozen evidence.

Ticket persistence and any bankroll reservation must eventually cross one atomic database transaction boundary or an equivalently proven state machine. A two-step "insert ticket, then reserve" path without durable recovery semantics is rejected because a retry can double-reserve or strand a ticket.

## 7. Reservation and shared-bankroll blocker

Phase-5 `reservation_key = builder:<composition_id>` is a deterministic proposal identity, not a persisted reservation.

The current V1 economic state cannot safely accept an independent builder reservation ledger beside it:

- V1 `activeState()` derives open exposure from `ineed_shadow_bets`,
- V1 placement derives total/match/player/market exposure from `ineed_shadow_bets`,
- V1 equity is `available + V1 open exposure`,
- a builder reservation stored only elsewhere would be invisible to those exposure queries.

Using only a separate builder ledger would therefore risk double allocation or distorted equity/drawdown. Using only the current ledger with no builder exposure owner would also make the builder stake disappear from open-exposure accounting.

**Required future invariant:** one shared bankroll/exposure view must account for both V1 single-leg open bets and builder-ticket reservations before builder reservation writes are enabled. Phase 6 does not choose or implement that schema.

## 8. Future sync boundary

A future builder sync path must be distinguishable from current V1 `payload.evaluations[]` / `payload.settlements[]` before data reaches V1 auto-placement logic.

Minimum contract:

- retain or tighten the existing GitHub OIDC trust boundary,
- accept only Phase-5 builder-ticket schema/economic unit and explicit SHADOW mode,
- reject `automatic_real_betting != false`,
- reject missing/mismatched exact operator provenance,
- persist by deterministic ticket identity and digest, not a generated client retry ID,
- never call current `ineed_system_place_bet(target_signal_id)`,
- never emit or consume a V1 `signal_id`,
- never project a builder ticket into current `ineed_shadow_bets`,
- never send builder tickets through current single-leg email/settlement semantics without a separately approved contract.

No workflow wiring is approved in Phase 6. The existing `iNeed$ SHADOW bankroll` workflow remains V1-only.

## 9. Settlement stays separate

Builder settlement remains `NOT_IMPLEMENTED`.

Phase 6 does not define leg aggregation, correlated-leg void handling, retirement/push/cancel behavior, operator ticket-result provenance, payout tax semantics or one-ticket final outcome.

No persisted builder record may be interpreted as settlement-ready until a separate operator-evidence audit proves exact one-ticket settlement semantics.

## 10. Phase-6 decision and next gates

Phase 6 approves **design only**:

1. builder ticket persistence must be separate from V1 signal/bet persistence,
2. identity is deterministic ticket/composition identity scoped by experiment,
3. immutable evidence needs a durable digest and fail-closed conflict rule,
4. replay/concurrency must be idempotent and transaction-safe,
5. reservation cannot be implemented safely until shared bankroll/exposure ownership includes builder reservations,
6. deployed `ineed-sync` v10 source must be reconciled into Git before any Edge deploy,
7. settlement remains a later independent audit/implementation phase.

### Next bounded action

Before any builder write implementation:

- reconcile the currently deployed `ineed-sync` v10 source into Git without changing production behavior,
- define and test the shared V1 + builder bankroll/exposure read model,
- then create a separate explicitly authorized implementation PR for immutable SHADOW ticket persistence and atomic idempotency,
- keep reservation disabled until shared exposure accounting is proven,
- keep settlement and real-money execution disabled.

**NO SCHEMA MIGRATION, NO EDGE DEPLOY, NO RUNTIME WIRING and NO REAL-MONEY EXECUTION are authorized by this audit.**

## 11. Local validation evidence

On the Phase-6 audit branch from exact base `06d0b06579b95d4a23106f2173ccd4e991558aa3`:

- Phase-6/V1-isolation/Phase-5/docs focused pack: **30/30 GREEN**,
- full repository pytest: **1405/1405 GREEN**,
- UI static smoke: **PASS**; real feeds retained 426 matches and all 102 Symphony matches,
- Project Health: **0 FAIL / 1 existing WARN**,
- `git diff --check`: clean.

The audit changes only documentation plus an isolation/contract test. No backend runtime, Supabase migration/function, workflow or frontend file is modified.
