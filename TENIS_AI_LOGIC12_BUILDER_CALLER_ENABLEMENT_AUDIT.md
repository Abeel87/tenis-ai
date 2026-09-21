# LOGIC-12 — Builder caller / enablement audit

Status: AUDIT ONLY. No caller wiring, no enable flag, no builder settlement.

## Live baseline

- `ineed_system_reserve_builder_ticket(uuid,jsonb)` is deployed and service-role-only.
- `builder_reservation.enabled` is absent on the active experiment, so the RPC fails closed.
- `ineed-sync` remains v11; no builder caller exists in Edge/workflow/frontend/scoped runner.
- Builder tickets/reservation ledger rows/open builder exposure are all zero at audit time.
- `automatic_real_betting=false`; builder settlement remains `NOT_IMPLEMENTED`.

## Finding 1 — Phase-4/5 has no runtime producer

`build_shadow_composition()`, `evaluate_builder_economics_shadow()` and
`build_builder_ticket_shadow()` are currently called only by tests. Production
`backend/ineed_scoped_runner.py` executes the legacy V1 evaluate/settlement path
and does not import the builder modules.

Therefore enabling the DB flag today would not create legal tickets; there is no
canonical runtime owner producing the frozen Phase-5 ticket envelope.
## Finding 2 — exact combined quote is not a runtime artifact

`superbet_direct.py` contains parsers for two exact builder quote sources:

- pre-priced combination market `238733`,
- dynamic `/betbuilder/v2/getSgaOddPrice`.

Those helpers are not called by production workflows/runners. The standard
`parse_event_payload()` intentionally excludes combination/BetBuilder rows.
The current `frontend/data/superbet_direct_current.json` contains normal exact
single-market selections only and has no `combination_quotes`, `builder_quotes`
or equivalent field.

At audit time the feed had 2 verified Direct matches and no combined-price
artifact. `scripts/publish_runtime_private.py` also publishes only the existing
Direct sidecar; there is no separate builder-quote source.

This is the first hard blocker before caller enablement. The RPC must never
receive a ticket whose exact combined operator price was reconstructed from
single-leg odds or inferred locally.
## Required ownership order before any enablement

1. Superbet refresh owns a new exact builder-quote artifact. It may contain only
   operator-provided combined quotes with event id, exact component selection ids,
   combined price, timestamp, source and operator combination id.
2. iNeed scoped SHADOW runner may consume that artifact plus final Symphony
   composition and shared bankroll state to run the existing pure Phase-4 economics.
3. The same runner may freeze a Phase-5 ticket with `build_builder_ticket_shadow()`.
4. Only a frozen valid Phase-5 ticket may be sent to the service-role reservation RPC.
5. `builder_reservation.enabled` stays false/absent until steps 1-4 have separate
   tests, CI and production read-only evidence.

No layer may recompute joint probability, synthesize combined odds, resize the
frozen stake after ticket creation, or infer missing operator provenance.

## Enablement gates

Before a future caller PR can enable reservation writes, all must be true:

- exact builder quote artifact exists and has a single canonical producer,
- quote artifact freshness and identity are fail-closed,
- Phase-4/5 runtime producer has deterministic replay tests,
- scoped runner remains SHADOW-only and `automatic_real_betting=false`,
- RPC replay/conflict behavior is proven against the runtime ticket shape,
- mail pipeline remains non-regressed,
- builder settlement is still treated as a separate later phase.
## Explicit hard stops

This audit does **not** authorize:

- adding an RPC caller,
- setting `builder_reservation.enabled=true`,
- creating builder rows or bankroll debits,
- changing V1 settlement,
- inventing builder settlement semantics,
- placing any real-money bet.

## Next exact implementation step

Implement the **quote-acquisition artifact only** in the canonical Superbet
refresh owner. It must be additive/read-only, publish no model probability,
and have zero iNeed runtime influence. After that artifact is independently
verified, a separate PR may wire the pure Phase-4/5 producer into the SHADOW
scoped runner while reservation writes remain disabled.
