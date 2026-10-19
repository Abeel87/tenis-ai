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


## Shared-feature DataFrame allocation follow-up

Head `f23bf50ac8d2cb8d060b32225173476d84916976` passed eight workflows including
UI health [39221003925](https://github.com/Abeel87/tenis-ai/actions/runs/39221003925).
Its full suite, browser/runtime checks and model isolation checks passed. The two
full-history workflows were still running when this additional issue was reproduced.

The locked pandas 3.0.5 constructor flattens every `ChainMap` to a new dictionary
before building a frame. This discards the memory benefit of shared opponent /
pressure feature maps at the evaluation boundary. A 10,000-row / 100-shared-feature
fixture measured 41,462,798 bytes peak with the old constructor, versus 8,827,971
bytes with column-wise construction. The regression failed at 41,449,608 bytes
before the fix. These figures describe only this controlled fixture.

The canonical `_frame` helper now constructs shared-mapping input column by
column, retaining pandas' inferred column order, missing-value semantics, types
and row index. Existing plain-dictionary/mixed inputs retain their previous path.
This only changes temporary allocation, with no change to fitting/evaluation.
Regressions compare exact DataFrames, fitted coefficients, schemas and predicted
probabilities for both pressure and opponent features. Empty mappings and explicit
missing-value overrides are covered. Latest full local suite: **1733 passed in 63.16 seconds**; `git diff --check` passed.
Fresh CI for this frame-allocation fix and production verification are pending.

## Fresh-main integration — 2026-10-19 09:31 UTC

Head `11f20db81069c0ba2be6729a8fb4b2059ed74cf1` passed eight workflows.
UI health [39222655833](https://github.com/Abeel87/tenis-ai/actions/runs/39222655833)
passed all **1733 tests in 47.60 seconds**, browser/runtime and isolation checks.
At this observation, [DNA 39222656168](https://github.com/Abeel87/tenis-ai/actions/runs/39222656168)
had also passed current-card scoring, market backtest, dynamic walk-forward and
dynamic current-card scoring; hold calibration was running.
[Point Tape 39222656167](https://github.com/Abeel87/tenis-ai/actions/runs/39222656167)
had passed opponent, pressure, tiebreak, recent-form, small-sample and matchup
evaluations, plus the point scorer. Full completion was still pending.

Main advanced from the original base to
[`8573c4fcc858b9cb9c9d5dc042cd768e9128ce4b`](https://github.com/Abeel87/tenis-ai/commit/8573c4fcc858b9cb9c9d5dc042cd768e9128ce4b)
at 09:16:37 UTC. The Neuron bot changed only `neuron_current.json`,
`neuron_metrics.json` and `neuron_model.json` in `frontend/data`; no repair source
or workflow changed. The branch incorporates those generated files unchanged
and will run fresh CI on the combined tree. This is an existing automated
SHADOW refresh, not a manual modification of Neuron training or authority.
Earlier-head results remain useful diagnostics but do not replace final-head CI.
Normal PR concurrency may cancel the superseded DNA run when the integration
is published; that cancellation is not a regression or an explicit cancellation
of a production refresh. No production recovery is claimed at this checkpoint.

The main refresh [39229175434](https://github.com/Abeel87/tenis-ai/actions/runs/39229175434/job/117982707244)
still failed at 09:28:37 UTC with `O/U threshold mismatch for player_total_games
200503: over=10.5, under=12.5`; its builder source was still `DIRECT_INPUT_UNSAFE`.
Those are the same two canonical input-contract defects repaired by this PR,
not evidence that its unpublished code failed in production.

The combined local tree passed **1733 tests in 59.70 seconds**. Only the three
unchanged Neuron bot outputs and this audit/checkpoint differ from head `11f20db`;
the repair source code and its tests are identical. Full fresh GitHub CI remains
the merge gate.

## Completed PR CI and second data-only base advance — 2026-10-19 11:21 UTC

All ten GitHub workflows succeeded for PR head
`af81bb25ba719030556058545bb7b8fca3a5038d`. This head incorporates main
`8573c4fcc858b9cb9c9d5dc042cd768e9128ce4b`; it does not include the later bot
commit described below.

- [UI health 39231113543](https://github.com/Abeel87/tenis-ai/actions/runs/39231113543):
  1733 tests passed in 69.91 seconds; UI, runtime, project health and isolation passed.
- [DNA 39231113492](https://github.com/Abeel87/tenis-ai/actions/runs/39231113492),
  job 117989525731: full SUCCESS at 11:01 UTC. Artifact
  `player-dna-shadow-refresh`, ID 12180973951, generated 11:01:36 UTC,
  83,628,534 bytes, expires 2026-11-02; digest
  `92c9863edc93ac1c01a113eb59155501a51c3b67ae434fa970e0f3d4c0c6a1b9`.
- [Point Tape 39231113404](https://github.com/Abeel87/tenis-ai/actions/runs/39231113404),
  job 117989020628: all 79 steps succeeded, complete at 11:21 UTC. Artifact
  `player-dna-point-foundation`, ID 12182696734, generated 11:21:03 UTC,
  84,455,872 bytes, expires 2026-11-02; digest
  `17b0f2152ec285626b975ac697b52b690042748ae2e2075d1d3e62f01ae4b2a1`.
- LOGIC-01 39231113406, LOGIC-02 39231113563, LOGIC-03 39231113419,
  LOGIC-04 39231113471, Superbet PR validation 39231113399,
  delivery/security 39231113413 and CodeQL 39231113551 also succeeded.
  Superbet PR validation is not a production refresh.

Point Tape peak RSS readings (the log unit is kbytes) were 5,439,380 for opponent
evaluation, 7,810,512 for pressure, 9,301,052 for small-sample evaluation,
4,457,276 for current-card scoring and 7,905,584 for dynamic walk-forward.
Every instrumented process exited zero. These are real completed CI runs, not
proof of a production memory ceiling or a causal OOM diagnosis for the original
runner shutdowns. The earlier 11f20db Point Tape run 39222656167 also completed
successfully at 10:36 UTC; it remains separate earlier-head evidence.

The DNA log reports 15,296 historical matches, 1,888,361 point events and
1,751,834 strict trainable/player points. Its current-card result generated at
09:59:25 UTC scored 196 of 370 snapshot matches; 174 were collecting history.
The dynamic result at 10:36:22 UTC scored 179, with 17 blocked for missing
provider rank. Training cutoff was 06:15 UTC. The final 11:01:31 log reports
`ACTIVE_SHADOW` computation, mixed/no match-level backtest signal,
`HOLD_CALIBRATION_NOT_YET_PROVEN`, hold walk-forward not yet robust and
prospective collection active. No production influence, runtime switch or
promotion is enabled. These generated CI results do not prove current application
freshness or PLAYABLE availability.

Main then advanced to
[`cded3bd34ca00652a23b796cb7b3c7a5b38af75f`](https://github.com/Abeel87/tenis-ai/commit/cded3bd34ca00652a23b796cb7b3c7a5b38af75f)
at 11:00:20 UTC. The complete
[base comparison](https://github.com/Abeel87/tenis-ai/compare/8573c4fcc858b9cb9c9d5dc042cd768e9128ce4b...cded3bd34ca00652a23b796cb7b3c7a5b38af75f)
contains only `frontend/data/neuron_current.json`, blob
`b8f1ad330a3f233c19bca859550774aaae0862ca`. Its generated timestamp/source
freshness and three SHADOW score pairs changed; no repair source, workflow,
Neuron training artifact or authority flag changed. The blob is retained exactly,
without manual edits, in the local integration.

The combined runtime tree `1dc76f1f8063a4f82bbed2a7b5c699065752fcf7` passed
1733 tests in 58.25 seconds. Static UI and runtime UI passed on real data and
both readiness fixtures after the workflow's `build_delivery.mjs` prerequisite.
An initial runtime invocation omitted that prerequisite and failed the first
Symphony route assertion; the documented build-then-test sequence passed without
changing UI or tests. Whitespace checks passed. The review/checkpoint branch
`verify/refresh-contracts-main-20261019` preserves this integration and these
records. Its source tree differs from the combined runtime tree only in audit
and checkpoint documentation.

AGENTS.md section 7 explicitly requires required CI again after a base advance.
The hourly Neuron schedule and long full-history CI can cause repeated data-only
base advances during validation. The local checks above are not represented as
new GitHub CI. No merge, workflow stop or exemption has been performed. The
remaining decision is whether the owner explicitly authorizes one merge using
the green repair-head CI plus these complete local integration checks for the
isolated generated Neuron change; otherwise re-publish the integrated branch
and repeat required GitHub CI. This record does not amend the project rule.

Production remains unverified: main Superbet
[39241953523](https://github.com/Abeel87/tenis-ai/actions/runs/39241953523/job/118024659533)
failed at 11:10:00 UTC with `O/U threshold mismatch for match_total 1002:
over=26.5, under=25.5`; the builder log at 11:09:21 still reports
`DIRECT_INPUT_UNSAFE`. These are the same two defects in the unpatched main.
The PR remains open; no production recovery, live PLAYABLE count or provider
HTTP 410 resolution is asserted.

## Owner-authorized merge — 2026-10-19 11:51 UTC

The owner explicitly approved the requested one-time exception for the isolated
Neuron generated-data advance. A fresh read confirmed main `cded3bd`, unchanged
PR head `af81bb2`, mergeability and all ten successful workflows. PR #550 merged
at 11:51:23 UTC as
[`7abe4f618474caa1897243ddba60d5f63f4ec3c0`](https://github.com/Abeel87/tenis-ai/commit/7abe4f618474caa1897243ddba60d5f63f4ec3c0).
The resulting tree is exactly the tested `1dc76f1f8063a4f82bbed2a7b5c699065752fcf7`.
This explicit decision does not amend AGENTS.md, CI policy or workflow schedules.

The normal [data/Pages producer 39247666214](https://github.com/Abeel87/tenis-ai/actions/runs/39247666214),
[DNA 39247666101](https://github.com/Abeel87/tenis-ai/actions/runs/39247666101)
and [UI health 39247666110](https://github.com/Abeel87/tenis-ai/actions/runs/39247666110)
started automatically on the merge SHA. At 11:52 UTC these were still running;
merge is confirmed, but production refresh/publication is not yet confirmed.
