# LOGIC-12 — Exact Bet Builder quote artifact

Status: READ-ONLY SHADOW artifact. No iNeed caller, no reservation enablement, no settlement.

## Ownership

The canonical owner is the existing `Superbet hourly market refresh` workflow.
`backend/superbet_builder_quotes.py` runs immediately after the verified Direct
sidecar refresh and writes `frontend/data/superbet_builder_quotes_current.json`.

The artifact consumes only Direct matches with `direct_match_verified=true` and
`prices_used=false`. It re-fetches the exact public Superbet event JSON and
re-verifies player identity + scheduled time through the canonical cached-fixture
matcher before accepting any combination row.

## Quote contract

Only operator-provided pre-priced combination market `238733` rows are accepted.
The artifact preserves exact component selection IDs, operator combination ID,
combined odds, source event ID, observation time and source provenance.

It never multiplies single-leg prices, never computes joint probability, EV,
Kelly or stake, and never calls iNeed$ reservation or settlement code.
Dynamic SGA requests remain outside this phase (`dynamic_sga_requests=0`).

## Fail-closed freshness

Unsafe, stale, missing or failed upstream data cannot leave an old quote artifact
looking current. The workflow invalidates the artifact to `SOURCE_UNAVAILABLE`
when Direct refresh fails, and `refresh-current` overwrites stale prior quotes
with an empty `SOURCE_UNAVAILABLE` artifact when exact quote acquisition fails.

## Hard boundaries

- `prices_used=false`
- `synthetic_prices=false`
- `production_influence=false`
- `playable_influence=false`
- `symphony_influence=false`
- `ineed_runtime_influence=false`
- `automatic_real_betting=false`
- no `builder_reservation.enabled=true`
- no reservation RPC caller
- builder settlement remains `NOT_IMPLEMENTED`

## Verification

Local Termux proof before PR:
- Python syntax guard: GREEN
- focused artifact/caller audit pack: 15/15 GREEN
- Direct/fixture/quote regression pack: 107/107 GREEN
- `git diff --check`: clean

Full repository/CI proof is required on the PR exact head before merge.
