# Repository reliability audit — 2026-10-29

Baseline: main `8778a92ed29fa5f6a9a7d8aff8c2d8f7e2a2f536`.

## Confirmed failure and repair

Private runtime delivery run [40636213894](https://github.com/Abeel87/tenis-ai/actions/runs/40636213894),
job `122643672984`, failed on HTTP 520 uploading `frontend/data/market_lab_history.json`.
Later ordinary deliveries succeeded. The canonical signed PUT owner now retries
transient HTTP 500/502/503/504/520/521/522/523/524, with three total attempts and
1s/3s delays. It captures the payload once, retains `x-upsert: false`, preserves
the existing HTTP 409 handling and generation CAS, and never activates after an
exhausted upload. Permanent errors still fail immediately. Error output omits
response bodies that could reflect a signed token.

The new regression module had 17 failures before repair. It covers all retryable
statuses, permanent errors, identical bytes after source mutation, the retry
bound, no activation after failure and retry-to-existing-object activation.
Together with the existing runtime tests, the focused upload suite passed 30 cases.

## Remaining transport work reconciled

PRs #563 and #564 had green older heads, but their bases predated the audit baseline.
Their small remaining changes are consolidated here on the current baseline:
`filter: blob:none` for full-history FAST and Player DNA checkouts, and an explicit
`git fetch origin --no-tags main:refs/remotes/origin/main` in DNA report publication.
Real local-Git tests reproduced three missing cases before these workflow edits.
The tests exercise ancestry, lazy retrieval of old blobs and concurrent-main
preservation. Existing readiness snapshot comparisons and publication guards stay
in place. The replacement merged as #565; both superseded PRs are now closed.

This does not alter Player DNA calculations, training, probabilities, settlement,
thresholds, model populations, storage retention or SHADOW/PROD boundaries.

## Validation and rollout

Local full regression: **1838 passed in 66.80s**, with the two existing Neuron
empty-fixture warnings. Final focused transport/upload suite: 25 passed in 4.89s.
After normal producer updates, local integration with main `44a557196a5167535d2a6f5fa0315560cc3eea27`
again passed **1838 tests in 67.24s**. The fresh PR integration also incorporates
the following readiness/meta-only update `9b0c740bd5f02a6a71b1dba3130b2438ee45f619`.
All completed code/security/browser/project-health checks on the initial PR head
passed. Its long DNA evaluation had reached walk-forward processing when the
branch was refreshed; this is not recorded as a completed full evaluation.
Current-head CI and production evidence must be recorded in the live checkpoint
before this work is described as deployed. Earlier green runs are useful baseline
evidence, not proof of this new commit's deployment.

## Completed source validation and merge

PR [#565](https://github.com/Abeel87/tenis-ai/pull/565) merged as
`b0c3752285423e915bc64a4c3a0c22fa0d5a357a`. All 11 checks on exact source head
`544ad8360c74825824bbe8b10b9b92ba04805406` passed, including the full Player DNA
run [40838950601](https://github.com/Abeel87/tenis-ai/actions/runs/40838950601).
Health run [40838950384](https://github.com/Abeel87/tenis-ai/actions/runs/40838950384)
passed all 1838 tests in 56.57s.

Main advanced during this evaluation to `1c21abfd1faf63eb5143c5c4bf6a123091d1b16b`
through 31 generated `frontend/data` files only. Comparing both recursive trees
confirmed no source/workflow changes. The prospective merge was rebuilt locally
against that exact base and passed all 1838 tests in 64.59s, the UI checks and
project-health workflow stages. Runtime health used the existing exact CI-base
contract: 0 failures, 2 existing size warnings, and no payload growth from the
repair. Without CI metadata a standalone invocation enforces the strict 50 MiB
limit against the complete restored history; that is not the PR comparison.
No limit or health policy was relaxed. The actual merged Git tree exactly equals
the validated tree `3cee273e1e8eb49016344e1b0659e6b73f502011`.

## Production rollout in progress

Normal post-merge core/Pages run `40849136609` is in progress. Its successful
completion and downstream private activation must be recorded here before this
new code is described as production-verified.

## Concurrent publication follow-up

Production validation exposed a separate race in full DNA run
[40849136860](https://github.com/Abeel87/tenis-ai/actions/runs/40849136860), job
`123363935382`. A fast readiness producer had already changed `meta.json` and
`readiness_engine_shadow.json` on the same results snapshot. The full producer's
three identical rebase attempts all conflicted. FAST Pages run `40849774219` and
private DNA run `40849777414` had succeeded; private generation
`a3945afa-249b-45a6-87ee-7fc4d742c1ee` was activated from `a39c702`.

Both publication stages reproduced the conflict using real local Git remotes.
Their inline loops are now replaced by one canonical Git publication owner. It
captures exact report bytes, builds only the owned-file changes in a temporary
index based on fresh main, and uses the existing readiness projection on current
meta. Normal fast-forward push handles concurrency through rejection and bounded
retry. New results still cause stale publication to be skipped. No data/model
contract, scheduler or concurrency group is changed, and run-local audit work is
preserved. Twelve Git regressions cover conflict recovery, foreign metadata,
immutable payloads, stale results, retry exhaustion, no-op, unrelated refs and
invalid reports. Focused suite: 37 passed; full regression: 1849 passed in 75.31s.
This follow-up still requires its own green CI and production verification.
