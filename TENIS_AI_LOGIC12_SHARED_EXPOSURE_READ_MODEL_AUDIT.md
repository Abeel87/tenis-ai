# LOGIC-12 — Shared V1 + Builder Bankroll/Exposure Read-Model Audit

Status: **AUDIT + CONTRACT DESIGN ONLY — NO WRITE IMPLEMENTATION**

Audit base: `54c0c84e1e37fc8905a26993b1464ee1d6d4d48e` after PR #441 restored `ineed-sync` v10 source parity in Git.

## 1. Scope

This audit defines the logical read contract required before any future persisted Bet Builder reservation may affect iNeed$ risk state.

This phase does **not**:

- add or alter a Supabase table, view, RPC, trigger, migration or policy,
- persist a builder ticket or reservation,
- deploy an Edge Function,
- alter current V1 placement or settlement,
- wire builder tickets into `payload.evaluations[]` or `ineed_shadow_bets`,
- change iNeed$ thresholds, caps, tax, Kelly, drawdown or stake math,
- define builder settlement,
- enable SHADOW -> PROD or real-money execution.

The required outcome is a stable logical interface that can later be implemented without making V1-only risk calculations change on identical V1 state.

## 2. Current V1 bankroll truth

Current V1 has two related but different concepts:

- **available capital** = latest `ineed_bankroll_ledger.bankroll_after`,
- **open exposure** = stake of open `ineed_shadow_bets` (`SHADOW_PLACED` / `PENDING`).

Current equity is reconstructed as:

`bankroll_equity = available_capital + open_exposure`

This is intentional because placement immediately debits the reserved stake from available capital through a `STAKE_RESERVED` ledger row while the open bet still owns that stake economically.

The current risk guard derives total, match, player and market exposure exclusively from `ineed_shadow_bets`. `ineed-sync::activeState()` likewise returns only V1 open bets.

Point-in-time live evidence during this audit: the ACTIVE SHADOW experiment had zero open V1 bets. The ledger contained no `STAKE_RESERVED` row without a linked V1 bet. This is evidence of current state only, not a schema invariant.

## 3. Current Phase-4 builder behavior

`evaluate_builder_economics_shadow()` already models combined risk correctly **inside one pure evaluation call**:

- it starts from `state.open_bets`,
- it counts one builder stake once toward total/match/player exposure,
- it counts the full builder stake against each constituent `builder_market`,
- after qualifying one composition it appends an in-memory synthetic `PENDING / BET_BUILDER` row to `allocated`,
- later candidates in the same call therefore see the proposed builder exposure.

That synthetic row is deliberately nonpersistent. On the next runtime cycle, current Supabase state would contain only V1 `ineed_shadow_bets`; the prior builder proposal would no longer be visible.

Therefore Phase-4 logic is not the blocker. The missing boundary is durable **shared exposure state** after a builder reservation eventually exists.

## 4. Non-negotiable accounting invariants

A future shared read model must preserve all of these:

1. `available_capital` remains derived from the bankroll ledger.
2. Every open reserved stake is added back exactly once when reconstructing equity.
3. The same economic stake is counted exactly once in total exposure.
4. The same stake is counted exactly once per matching match/player correlation dimension.
5. A builder stake is counted once in each constituent market bucket, matching Phase-4 semantics.
6. A ledger reservation and its exposure owner must never be counted as two independent exposures.
7. V1-only input must produce the same risk state and headroom as today.

## 5. Logical normalized exposure unit

The audit freezes a logical exposure record, independent of physical schema:

- `experiment_id` — bankroll/risk ownership,
- `economic_unit` — `V1_SINGLE_BET` or `BET_BUILDER_COMPOSITION`,
- `owner_key` — deterministic durable owner identity,
- `status` / `is_open` — whether stake remains economically reserved,
- `stake` and currency,
- `match_id`,
- the two frozen player correlation values used by current risk semantics,
- `market_dimensions` — one V1 market or all builder constituent markets,
- immutable provenance back to the owning V1 bet or builder ticket/reservation.

For builders, `owner_key` must derive from the already-frozen deterministic ticket/composition identity. A random retry identifier is not sufficient ownership.

The read model may later be implemented as a database view/union over separate owner tables or as a dedicated normalized exposure registry. This audit intentionally does **not** select the physical schema. Any implementation must prove the same logical output and atomic ownership rules.

## 6. Required shared state interface

A future risk-state response needs two separate concepts:

- `open_bets` — keep the existing V1 bet-shaped collection for current settlement compatibility,
- `risk_exposures` — normalized open economic exposures across V1 + builder.

Do **not** overload `open_bets` with builder records. `backend/ineed_settlement_runner.py` consumes `state.open_bets` as V1 settlement input; placing builders there before settlement semantics exist would create a new unsafe settlement path.

The shared risk summary should be derivable from `risk_exposures`:

- `active_exposure = sum(open stake once per economic unit)`,
- `bankroll_equity = available_capital + active_exposure`,
- per-match exposure,
- per-player correlation exposure,
- per-market concentration exposure.

Until builder settlement exists, peak/drawdown history remains based on existing settled V1 evidence plus current shared equity. A builder must not fabricate a settled bankroll snapshot.

## 7. Market attribution rule

V1 exposure contributes its full stake to its one current `market` bucket.

A builder contributes its full ticket stake to **each distinct constituent market** frozen in `builder_markets`, while contributing the stake only once to total/match/player exposure.

This deliberately matches current Phase-4 SHADOW economics. It prevents a builder containing (for example) `set1_winner` + `set1_total` from bypassing either market concentration limit without falsely doubling total exposure.

## 8. Reservation ownership and idempotency

A future builder reservation may reduce available capital only when it has a durable builder economic owner created in the same atomic transaction or equivalently proven state machine.

Required properties:

- one deterministic builder owner -> at most one open exposure,
- one deterministic builder owner -> at most one `STAKE_RESERVED` debit,
- identical retry -> idempotent response, no second debit/exposure,
- conflicting immutable ticket evidence -> fail closed before money state changes,
- failed transaction -> neither durable reservation nor durable exposure,
- lost client response after commit -> retry reconstructs committed state from the database.

A naked ledger row is insufficient because it reduces available capital without giving risk calculations an open exposure owner to add back into equity and concentration accounting.

A naked builder row without the ledger debit is also insufficient because available capital would remain overstated.

## 9. Consumer migration boundary

When implementation is later authorized, the minimum coordinated consumers are:

- Supabase state/RPC layer: produce shared `risk_exposures` and shared aggregate risk state,
- `backend/ineed_money.py`: use normalized risk exposure for V1 allocation while preserving V1-only outputs,
- `backend/ineed_builder_shadow.py`: use the same normalized exposure input rather than ephemeral-only builder shape,
- staff iNeed$ presentation: stop independently implying V1-only exposure is total system exposure once builders can reserve bankroll.

`backend/ineed_settlement_runner.py` must remain V1-only until builder settlement is separately designed and authorized.

## 10. Acceptance proofs required before any reservation write

A future implementation PR must prove at minimum:

- V1-only frozen fixtures return exactly the same available/equity/risk/cap/headroom outputs as before,
- adding one open builder reduces available capital once and restores that stake once in shared equity,
- total/match/player exposure counts the builder stake once,
- every distinct constituent market receives the full builder stake once,
- duplicate/replayed builder reservation does not change available capital or exposure twice,
- builder exposure never enters the V1 settlement runner,
- closing/cancelling an exposure cannot occur without separately authorized lifecycle semantics,
- frontend/admin totals agree with the shared backend risk state.

No reservation write should be implemented before these proofs have executable tests.

## 11. Audit decision

The safe next implementation boundary is **not** “add a builder ledger debit”. It is first to introduce a shared risk-exposure read contract that can represent both current V1 bets and future builder reservations while leaving V1 settlement isolated.

This audit authorizes no schema or runtime change. It only freezes the target semantics and the proof obligations for a later explicitly scoped implementation.

### Next bounded action

1. Merge this audit-only contract after focused/full CI and fresh-main verification.
2. Then design the smallest implementation of the normalized shared exposure interface with V1-only equivalence tests.
3. Keep builder persistence/reservation writes disabled until that interface is proven.
4. Keep builder settlement `NOT_IMPLEMENTED` and real-money execution disabled.

## 12. Local validation evidence

On exact base `54c0c84e1e37fc8905a26993b1464ee1d6d4d48e`:

- focused shared-exposure / V1 money / builder economics / settlement / source-parity / docs pack: **47/47 GREEN**,
- full repository pytest: **1413/1413 GREEN**,
- UI static smoke: **PASS**; current feed preserved 389 matches and all 103 Symphony matches,
- Project Health: **0 FAIL / 1 existing WARN**,
- `git diff --check`: clean.

The audit changes only documentation plus a contract/isolation test. No backend runtime, Supabase schema/function, workflow or frontend file is modified.
