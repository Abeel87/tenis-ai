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
Completed current-head CI and production evidence are recorded below and in the
live checkpoint. Earlier green runs are baseline evidence only; deployment claims
below use the actual new source and producer runs.

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

## Signed-upload production verification

Normal core/Pages run `40849136609` completed successfully. Private core run
`40852401197`, job `123374872402`, activated generation
`82a61d1e-8399-4189-aca1-50bc82305947` from source `39a462e`: 270 files and
251 uploaded objects. Its retention cleanup also succeeded. This is deployment
proof for the signed-upload owner from #565, not an inference from older runs.

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
PR #566 merged as `fb117a59131c8608f295eedbb3a7c01d5ba5eb0c` after all 11 checks
on exact head `81528eea7f6005134b1ac67af631381709af6236` passed. Full DNA run
`40852815341` passed; health `40852815352` passed all 1849 tests in 85.87s.

The fresh-main merge against `647e9576ac73db982c7d3c9b8ca7e719236b9a7c` also
passed all 1849 tests in 65.09s and every UI/project-health workflow stage with
the exact CI baseline. Intervening changes were generated runtime data and
verified Neuron prediction history. Actual merged tree
`691be953439559296297cca4a64a0a6155603b3e` equals that validated tree.

## Concurrent publisher production verification

Ordinary post-merge DNA run `40859564272`, job `123399637781`, completed the
repaired early publication step at 10:56:55–10:57:00 UTC and its FAST deployment
dispatch at 10:57:00–10:57:04 UTC. The published commit is
`b6070832183329eca08a7eef533ec5dad0ae5a42`, with parent
`fb117a59131c8608f295eedbb3a7c01d5ba5eb0c`. Only the readiness and meta files
changed. Independent validation confirmed the exact canonical projection against
the unchanged 210-match results snapshot and preservation of every foreign meta
field. Report generation time is `2026-10-29T10:56:51.331338+00:00`.

Downstream FAST Pages run `40861559349`, job `123405809386`, deployed successfully
at 11:00:21 UTC. Post-merge health, browser, dependency and CodeQL checks passed.
The long production DNA evaluation remains ordinary background work: this record
does not claim its completion or a completed production final-report publish.
The full required PR evaluation and real-Git tests of both publication modes
passed before merge. Publication repairs #565/#566 are complete; model policy,
retention and the existing explicit payload warnings remain unchanged.
