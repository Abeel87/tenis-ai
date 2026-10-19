# Refresh contract repair — 2026-10-19

Owner authorized technical repairs after the GitHub health report. Base:
`3a7ee2d468839313e1b655b4b79f5ae4abe0f914`; branch
`fix/refresh-contracts-20261019`. This change does not alter model mathematics,
features, sample limits, training/evaluation parameters, probabilities, PLAYABLE
decisions, settlement, iNeed economics/scope or SHADOW/PROD authority.

## Reproductions and canonical repairs

1. `scripts/verify_superbet_market_semantics.py` used the last over and last
   under for a whole market ID. Alternative lines therefore produced false
   threshold mismatches depending on row order. It now counts exact common
   lines separately per market and player. One-sided operator lines remain
   explicitly unpaired; they are never matched to a nearby line or another
   player. Invalid/nonfinite lines still fail validation. This audit does not
   grant PLAYABLE or change operator selection data.
2. `backend/superbet_builder_quotes.py` rejected the entire Direct feed when
   its catalogue exceeded the existing 64-event read budget. Base main contains
   221 verified Direct matches (`2026-10-19T06:51:12.860155+00:00`) and the builder
   artifact at `06:52:24.015778+00:00` reports `DIRECT_INPUT_UNSAFE`, zero requests.
   The canonical collector now selects at most 64 verified, future events in
   deterministic schedule/identity order. Overflow is reported as
   `EVENT_REQUEST_BUDGET_EXHAUSTED`, with explicit coverage counters. Each
   selected event still requires a fresh exact fetch and identity proof.
   Started/undated events do not consume requests. Dynamic quotes and builder
   reservation/lifecycle gates are unchanged.
3. Player DNA job [117930428854](https://github.com/Abeel87/tenis-ai/actions/runs/39213017359/job/117930428854)
   stopped during recent-form/Player State generation after producing 1,888,361
   points and 30,472 profile snapshots. The log proves runner shutdown at
   07:16:13 UTC, not its cause; OOM is not asserted. The existing scorer and
   recent-form loaders unnecessarily retained all raw points, global state
   lookup and multiple feature populations simultaneously. They now read the
   canonical dataset one complete match at a time and reuse unchanged feature
   builders. The producer emits contiguous match groups; a repeated noncontiguous
   match fails explicitly. Output rows/order and diagnostics must equal the
   eager implementation. Player State makes two independent iterator passes
   instead of retaining all raw points. `/usr/bin/time -v` now records actual
   process memory in the two affected workflow steps; concurrency is unchanged.

## Validation

- Regression tests reproduced the original O/U ordering and whole-catalogue
  rejection before repair; new streaming tests initially failed for the absent
  streaming path. Negative cases retain invalid-line, stale/unsafe feed,
  identity, transport-failure, synthetic-price and SHADOW isolation checks.
- Final focused suite: **92 passed**. Full Python suite: **1712 passed in
  53.56 seconds**. UI static/runtime smoke: PASS on 370 real fixtures,
  preserving all 217 Symphony matches and scored events.
- Base-main availability fixture: 221 fixtures, 19,966 selections, 1,077
  handicap pairs, 3,465 exact total pairs, 84 unpaired total lines, 195 winner
  fixtures; `prices_used=false`. Counts are audit results for this snapshot,
  not current PLAYABLE or application availability.
- Synthetic memory comparison on 200 raw rows with 100 KB unused payload each:
  eager peak 20,316,128 bytes; streaming peak 614,302 bytes; output exactly equal.
  The 96.98% reduction describes this fixture only, not production peak RSS.
- Large-feed test: 70 verified future events produce exactly 64 requests and
  six explicit budget skips; started events produce zero requests.
- GitHub CI, merge and normal post-merge refresh verification remain required.
  A merge alone will not prove that the runner-shutdown problem is resolved.

## Remaining boundaries

Provider HTTP 410 for historical matches 196595/201913 has no new recovery
evidence. Zero in-scope iNeed match-winner candidates is not repaired by changing
its market scope. Unrelated open PRs, model gates and builder reservation remain
untouched. Normal live refreshes must establish source timestamps, exact quote
coverage and Player DNA completion after this change.
