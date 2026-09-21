# LOGIC-12 — Builder reservation atomicity audit

## 1. Scope

**AUDIT / DESIGN + READ-CONTRACT CORRECTION ONLY.**

This step defines the smallest safe durable ownership and transaction boundary for a future SHADOW Bet Builder bankroll reservation. It does not create a Supabase table, view, migration, RPC, Edge write path, settlement path, or runtime caller.

The current V1 single-leg placement/settlement path remains authoritative and unchanged in production. Builder settlement remains `NOT_IMPLEMENTED`. Real-money execution remains disabled.

The only code correction allowed in this audit is the already-proven read-contract separation between V1 open statuses and builder open status: V1 uses `PENDING` / `SHADOW_PLACED`; a durable builder exposure must use `SHADOW_RESERVED` and must never masquerade as a V1 bet.

## 2. Evidence from the current live boundary

Current `ineed_system_place_bet(uuid)` is already one database transaction. It locks the target V1 signal and then locks the owning `ineed_experiments` row `FOR UPDATE` before reading the bankroll ledger, calculating exposure, inserting the V1 bet, inserting one `STAKE_RESERVED` ledger row, and updating the signal.

Live read-only `pg_get_functiondef(ineed_system_settle_bet(...))` proves production locks the V1 bet and the same owning experiment row `FOR UPDATE` before mutating the ledger and settlement state. Historical Git migration `20260910221444_ineed_v1.sql` is stale and omits the experiment lock; live migration history has no separate named migration for that correction. The experiment row is therefore the live canonical serialization mutex, and the later settlement source-parity migration must preserve it explicitly.

Current V1 exposure SQL reads only `ineed_shadow_bets`. Current `ineed-sync::activeState()` also calculates active exposure only from open `ineed_shadow_bets`. A builder-only RPC beside those readers would therefore be unsafe: later V1 placement could ignore the builder and over-allocate bankroll.

Live schema evidence also matters:

- `ineed_bankroll_ledger` has unique `(experiment_id, source_key)` and optional `bet_id` tied to `ineed_shadow_bets`.
- `STAKE_RESERVED` already exists as a ledger entry type.
- live `pgcrypto` 1.3 is available, so the database can own the immutable ticket digest.
- the current ACTIVE SHADOW experiment had `available_capital=191.2532`, zero open V1 exposure and zero open V1 bets at audit time. Historical reservation rows exist; these values are point-in-time evidence, not invariants.
- post-PR #443 `ineed-sync` remains ACTIVE v10 with unchanged source hash; no deployment occurred.

## 3. Atomicity decision

The future builder reservation must use the **same experiment-row lock** as V1 placement and V1 settlement:

`SELECT ... FROM ineed_experiments WHERE id = target_experiment_id FOR UPDATE`

No separate builder mutex, application lock, Edge-only lock, or two-step "persist then reserve" workflow is accepted. Every bankroll writer for one experiment must serialize through the same database owner.

The future builder transaction must either commit all of the following or commit none of them:

1. immutable durable builder owner,
2. open normalized builder exposure,
3. exactly one `STAKE_RESERVED` ledger debit.

A response lost after commit must be safely replayable without a second owner, exposure or debit.

## 4. Smallest durable builder owner

The smallest future physical owner is one table, proposed as `ineed_builder_tickets`. It is both the immutable ticket evidence owner and, while reserved, the builder exposure owner. A second reservation table would duplicate ownership and is not required.

Minimum logical fields:

- `id uuid` primary key,
- `experiment_id uuid` referencing `ineed_experiments`,
- `ticket_key text` = `builder-ticket:<composition_id>`,
- `ticket_digest text` = database-owned SHA-256 of immutable ticket evidence,
- `composition_id text`,
- `status text` with open reservation status `SHADOW_RESERVED`,
- `stake numeric` > 0 and `currency text`,
- `match_id text`, `p1 text`, `p2 text`,
- `market_dimensions text[]` containing all distinct constituent markets,
- `reservation_key text` = `builder:<composition_id>`,
- `ticket_snapshot jsonb` containing the frozen Phase-5 ticket evidence,
- `reservation_contract_version text`,
- `created_at` / `reserved_at` timestamps.

Required uniqueness is at least `(experiment_id, ticket_key)`. `(experiment_id, reservation_key)` and `(experiment_id, composition_id)` should also be unique so one deterministic composition cannot acquire alternate durable identities.

This table must not use V1 `signal_id`, V1 single-market identity or V1 terminal settlement statuses.

## 5. Ledger ownership extension

The existing ledger remains the single source of available capital. Future schema may add nullable `builder_ticket_id uuid` referencing `ineed_builder_tickets(id) ON DELETE RESTRICT`; it must not create a second bankroll ledger.

For `STAKE_RESERVED`, exactly one economic owner is allowed:

- V1: `bet_id` non-null and `builder_ticket_id` null,
- builder: `bet_id` null and `builder_ticket_id` non-null.

A partial unique index on non-null `builder_ticket_id` for `entry_type='STAKE_RESERVED'` should enforce at most one reservation debit per builder owner. Existing unique `(experiment_id, source_key)` remains an independent replay barrier.

Builder reservation ledger identity is frozen as:

- `source = 'ineed_builder_ticket'`,
- `source_key = 'reserve:' || reservation_key`, therefore `reserve:builder:<composition_id>`.

The builder row and this ledger row must be inserted inside the same transaction while the experiment row lock is held.

## 6. Shared DB exposure source

Before any builder debit is enabled, the database needs one normalized shared open-exposure source, proposed as `ineed_open_risk_exposures`.

Logical columns mirror the merged backend contract:

`experiment_id, economic_unit, status, stake, match_id, players, markets, source_id, composition_id`.

The source is a `UNION ALL` of:

- V1 open `ineed_shadow_bets`: `economic_unit='V1_SINGLE_BET'`, status `PENDING`/`SHADOW_PLACED`, players from frozen placement snapshot, `markets=ARRAY[market]`, no composition id.
- builder rows from `ineed_builder_tickets` only when `status='SHADOW_RESERVED'`: `economic_unit='BET_BUILDER_COMPOSITION'`, players `[p1,p2]`, all distinct `market_dimensions`, `source_id=ticket_key`, and canonical `composition_id`.

Every economic stake appears exactly once in this view. A builder stake appears once as an economic row, while market concentration tests the same full stake against each distinct market in its `markets` array.

The current V1-only population must produce exactly the same total/match/player/market exposure and equity as current SQL. That equivalence is a blocking acceptance test for any future migration.

## 7. Required V1 migration boundary

A future builder reservation RPC cannot be enabled while `ineed_system_place_bet()` reads only `ineed_shadow_bets`.

Before enabling builder writes, current V1 placement must calculate:

- total exposure from the shared exposure source,
- same-match exposure from the shared exposure source,
- player correlation from the shared exposure source,
- same-market concentration from the shared exposure source.

The V1 stake formula, limits, thresholds and risk profiles remain unchanged. Only the open-exposure source changes, and V1-only fixtures must prove exact equivalence.

V1 settlement remains V1-only. Its experiment lock continues to serialize ledger mutation, while builder exposure must only affect the shared current-equity/exposure calculation; builder settlement is not introduced.

## 8. Future reserve RPC contract

A future security-definer RPC may be named `ineed_system_reserve_builder_ticket(target_experiment_id uuid, ticket_snapshot jsonb)`. This name is design-only in this audit.

Required transaction order:

1. lock the target experiment `FOR UPDATE` and require ACTIVE + SHADOW + `superbet.pl`,
2. require an explicit server-side builder-reservation enable flag; absence is fail-closed,
3. validate Phase-5 immutable identity/provenance and `automatic_real_betting=false`,
4. derive `ticket_key`, `composition_id` and `reservation_key` deterministically and require exact agreement with the ticket,
5. calculate `ticket_digest` in PostgreSQL using `pgcrypto`, e.g. SHA-256 over canonical `ticket_snapshot::text`,
6. resolve replay before any debit,
7. read latest available capital plus the shared exposure source under the experiment lock,
8. revalidate the proposed stake against current unchanged iNeed$ risk caps; do not recompute model probability, joint probability, odds, EV or Kelly,
9. atomically insert the `SHADOW_RESERVED` builder owner and exactly one `STAKE_RESERVED` ledger row,
10. return the committed owner/reservation identity.

Replay rules:

- same `(experiment_id,ticket_key)` + same DB digest + existing reservation => `IDEMPOTENT`,
- same identity + different digest => `IMMUTABLE_TICKET_CONFLICT`,
- any validation/risk/insert failure => rollback both owner and ledger effects.

Concurrent V1 placement, V1 settlement and builder reservation are serialized by the same experiment lock.

## 9. `ineed-sync` and runtime enablement boundary

Current `ineed-sync::activeState()` still returns exposure from V1 `ineed_shadow_bets` only. A dormant schema/RPC is not enough to enable builder reservation runtime.

Before any caller may create `SHADOW_RESERVED` rows, `activeState()` must read the shared exposure source and return normalized `risk_exposures` while continuing to return `open_bets` as V1-only settlement input. Available capital remains ledger-derived; equity becomes `available_capital + sum(risk_exposures.stake)` exactly once.

The staff UI must not present builder reservation/equity as truth until it consumes that shared state. It may remain explicitly V1-only before that migration, but it must not silently omit live builder exposure.

Current Phase-5 tickets remain `runtime_publishable=false` and `persistence_ready=false`. This audit does not silently promote them. A future schema/RPC implementation must be dormant/fail-closed until a separate explicit authorization enables the reservation contract and its caller.

## 10. Settlement boundary

Builder settlement remains `NOT_IMPLEMENTED`.

No builder terminal statuses (`WIN`, `LOSS`, `VOID`, `CANCELLED`, `SETTLED`), payout logic, settlement ledger entries or operator-outcome interpretation are designed here. `backend/ineed_settlement_runner.py` and `ineed_system_settle_bet(...)` remain V1-only.

A reserved builder is therefore only an open SHADOW economic exposure. Runtime reservation must not be enabled until there is an explicitly accepted lifecycle policy for how such reservations are cleared if settlement is still unavailable.

## 11. Acceptance proofs before any write implementation can be enabled

A future implementation PR must prove, at minimum:

- V1-only shared-view outputs are exactly equivalent to current V1 exposure SQL,
- V1 placement still produces the same decision/stake on identical V1-only state,
- a builder reservation lowers available capital once and adds one shared exposure once,
- its stake counts once total/match/player and once per distinct constituent market,
- concurrent identical builder reserve calls create one owner and one debit,
- same identity/different digest fails closed without mutation,
- failure after owner insert but before commit leaves neither owner nor debit,
- response loss after commit replays as `IDEMPOTENT`,
- concurrent V1 placement/settlement/builder reserve cannot observe a partially committed bankroll state,
- builder exposure never enters V1 `open_bets` or V1 settlement,
- `ineed-sync` shared state includes builder exposure before runtime reserve enablement,
- real-money execution remains disabled.

## 12. Audit decision

The smallest safe path is **not** a builder ledger debit by itself. The future implementation boundary is one coordinated database change containing:

1. one durable `ineed_builder_tickets` owner,
2. one shared `ineed_open_risk_exposures` source,
3. V1 placement switched to that source with exact V1-only equivalence,
4. one atomic/idempotent builder reserve RPC using the same experiment lock and existing ledger,
5. `ineed-sync` switched to shared risk state before runtime builder reservation is enabled.

No second bankroll ledger, no builder row in `ineed_shadow_bets`, no fake V1 signal, no V1 settlement reuse, and no Edge-only transaction coordinator are allowed.

## 13. Next exact action

This branch remains audit/design plus the `SHADOW_RESERVED` read-contract correction only. It must not add the proposed table, view, ledger column, RPC or Edge wiring.

After this audit PR is fully green and merged, the next separately controlled step may implement the **dormant database schema/read source + V1 equivalence tests**. The builder reserve RPC/runtime caller must remain disabled until the shared DB read source, V1 placement migration and `ineed-sync` shared state are proven together and explicitly authorized.

Builder settlement and real-money execution remain disabled.
