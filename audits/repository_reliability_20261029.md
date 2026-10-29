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

PRs #563 and #564 have green older heads, but their bases predate the current main.
Their small remaining changes are consolidated here on the current baseline:
`filter: blob:none` for full-history FAST and Player DNA checkouts, and an explicit
`git fetch origin --no-tags main:refs/remotes/origin/main` in DNA report publication.
Real local-Git tests reproduced three missing cases before these workflow edits.
The tests exercise ancestry, lazy retrieval of old blobs and concurrent-main
preservation. Existing readiness snapshot comparisons and publication guards stay
in place. Close the two superseded PRs only after this replacement is merged.

This does not alter Player DNA calculations, training, probabilities, settlement,
thresholds, model populations, storage retention or SHADOW/PROD boundaries.

## Validation and rollout

Local full regression: **1838 passed in 66.80s**, with the two existing Neuron
empty-fixture warnings. Final focused transport/upload suite: 25 passed in 4.89s.
Current-head CI and production evidence must be recorded in the live checkpoint
before this work is described as deployed. Earlier green runs are useful baseline
evidence, not proof of this new commit's deployment.
