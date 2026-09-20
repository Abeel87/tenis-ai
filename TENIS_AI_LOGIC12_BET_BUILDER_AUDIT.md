# LOGIC-12 — iNeed$ Bet Builder Redesign SHADOW — Phase 1 audit

Status: **SHADOW CONTRACT ONLY**

Base audited: `53036abdaa586cfda5b4198b489751abe583abec`.

## Current production behavior

Current iNeed$ owner remains `backend/ineed_money.py`, invoked through
`backend/ineed_scoped_runner.py`. It consumes final `symphony2_playable.signals`
one signal at a time. Each signal receives its own Direct quote, EV/risk/stake
calculation and settlement record.

Therefore current iNeed$ economic unit is a **single leg**, not one final
same-match Bet Builder ticket.

This behavior is frozen by tests during LOGIC-12 phase 1. It is not replaced,
rewired or promoted by this phase.

## Existing upstream composition authority

Symphony already owns the final composition. `symphony2_playable` publishes:

- final authority `SYMPHONY2_FINAL_PLAYABLE`,
- at least two fixture-line-verified legs,
- `recommended_leg_count`,
- `joint_probability` from the supported shared state-space,
- operator market/outcome IDs for each published leg.

## Exact current snapshot proof

On the audited snapshot:

- `frontend/data/results.json`: 108 current rows,
- final Symphony PLAYABLE rows: 33,
- valid new SHADOW composition records: 33/33,
- rejected final PLAYABLE rows: 0,
- final compositions carrying combined odds: 0,
- `frontend/data/superbet_direct_current.json`: 13 resolved Direct matches,
- Direct match objects expose no builder/combined quote field.

Direct data contains exact prices for individual canonical selections. Those
single-leg prices are not a Bet Builder ticket price and must never be
multiplied to manufacture one for correlated same-match selections.

## Phase-1 canonical SHADOW contract

`backend/ineed_builder_shadow.py` is a pure, non-runtime contract owner for the
future final-ticket economic unit. It:

- accepts only one unambiguous canonical match identity,
- accepts only final Symphony authority with at least two verified legs,
- requires operator market/outcome identity on every leg,
- preserves the upstream `joint_probability` without recalculation,
- creates a deterministic `composition_id`,
- defaults combined price to `NOT_AVAILABLE`,
- computes no EV, Kelly, stake, settlement or execution action.

A combined quote may attach only when an adapter supplies an exact matching
`composition_id`, operator `superbet.pl`, quote kind `BET_BUILDER_COMBINED`,
`operator_verified=true`, `freshness_verified=true`, positive combined odds,
timestamp and source provenance.

Anything else remains `combined_odds=None`, `economic_ready=false` and NO BET
for the future SHADOW economic path.

## Hard isolation

Phase 1 does **not** change:

- Current Engine / model probability,
- Symphony probability or ranking,
- PLAYABLE,
- current single-leg iNeed$ calculations,
- bankroll/risk/stake math,
- settlement,
- SHADOW/PROD state,
- real-money execution.

## Next proof

The next phase may build an additive quote adapter only after proving how the
operator exposes an exact combined Bet Builder price for the exact composition.
If that proof is unavailable, the correct result is N/D / NO BET, not a
synthetic product of leg odds.
