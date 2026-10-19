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

## First GitHub validation and opponent-audit follow-up

PR [#550](https://github.com/Abeel87/tenis-ai/pull/550), initial head
`b5947f6508ab1bad2f9f8d45495410dd6a736902`, passed eight of ten workflows.
UI health [39217141650](https://github.com/Abeel87/tenis-ai/actions/runs/39217141650)
ran all 1712 tests successfully in 55.73 seconds, plus browser/runtime and
publication checks. The unchanged snapshot retains existing payload-size
warnings; project health reports zero failures.

Player DNA [39217141663](https://github.com/Abeel87/tenis-ai/actions/runs/39217141663)
passed recent-form/Player State generation and scorer training/evaluation.
This confirms progress beyond the earlier failing step, not full workflow or
production completion.

Point Tape [39217141673](https://github.com/Abeel87/tenis-ai/actions/runs/39217141673/job/117943537486)
failed at the opponent-strength challenger: runner shutdown at 07:58:22 UTC,
after entering that step at 07:50:04. It retained all raw points, a complete
base-feature population and a flattened enriched population with repeated
per-match/direction feature names. The follow-up streams complete point groups
and shares immutable direction features with private per-row overrides.
Global opponent-context and adjustment indexes still use the complete profile
population; they are never built from a single match. Original adjustment-field
precedence, including missing values overriding raw profile values, is preserved.
The workflow now records `/usr/bin/time -v` for this step too.

Independent comparison with the committed previous implementation on 3000 points
from 30 matches proves exact row values/order, counters and pandas values/dtypes.
Measured enrichment allocation: 14,357,093 versus 4,410,680 bytes. This is a local
fixture measurement, not production RSS or proof of the shutdown cause. Added
regressions cover global prior history despite nonchronological file groups,
missing-value precedence, row-write isolation and bounded raw-input allocation.
Updated CI and normal refresh verification remain required; PR #550 is unmerged.


## Current-card and shared-input follow-up

Player DNA run `39217141663`, job `117943537647`, subsequently stopped during
`Score current card in SHADOW`, with runner shutdown at 08:02:25 UTC and cancellation
at 08:02:27. Again, the log does not prove OOM. Before that, the repaired recent-form /
Player State step completed in 4:58.78 with peak RSS 4,089,540 KB, and the scorer
completed in 2:36.89 with peak RSS 4,755,876 KB; both exited zero. These are CI
measurements for the initial PR head, not current production success.

The current-card CLI still retained every raw point while building all features.
A regression reproduced a 20,306,690-byte allocation for 200 rows with 100 KB
unused payload each. The canonical scorer now exposes `PointDataset`, a repeatable
file iterable: current profiles, rank context and historical outcome reconstruction
receive independent passes after feature joins. A one-shot generator would silently
exhaust those later consumers, so it is not used as their shared input.

The same eager CLI pattern existed in current dynamic scoring, market backtest /
walk-forward, hold calibration / walk-forward, prospective evidence, and pressure,
tiebreak, small-sample and matchup challengers. These existing consumers now use
that canonical file source. Feature/state joins and label input grouping process
one complete match at a time; arbitrary in-memory list inputs retain their old
semantics. The label reconstruction and settlement functions are unchanged.
Match-local enrichers reuse their original builders with the same global profile
count. The opponent audit retains its separately prepared global prior indexes.
No sampling, evaluation-fold, feature-value, model, threshold or policy change is
included. Additional RSS probes cover these existing workflow steps.

Validation of the follow-up:
- Exact equality against the committed previous implementations on 3000 points /
  30 matches for scorer, pressure, tiebreak, small-sample and matchup features,
  counters, row order and pandas values/dtypes.
- Current-card integration regression compares the actual fitted artifact,
  fingerprint, second-pass as-of profiles and scored output on 40 history matches.
  The historical-validation gate is stubbed positive only in this test to exercise
  the active scoring path; its production behavior is untouched.
- Empty/missing input, nonchronological match groups, split-match rejection,
  duplicate profile precedence, repeated reads and exact label outcomes covered.
  All six raw-input allocation tests stay below 5 MB for the 20 MB fixture.
- AST comparison: 219 existing function bodies in touched Player DNA modules are
  unchanged. Modified existing functions are ingestion/build entry points and
  input grouping; fitting, evaluation, simulation and settlement bodies are intact.

- Final follow-up full Python suite: **1729 passed in 53.89 seconds**.
  `git diff --check` passed. New GitHub CI and production verification are pending.
