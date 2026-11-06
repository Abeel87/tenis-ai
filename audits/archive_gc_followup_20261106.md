# Archive GC follow-up — 2026-11-06

The previous application repairs remain deployed. A new failure in
[GC run 42195698453](https://github.com/Abeel87/tenis-ai/actions/runs/42195698453)
returned PostgreSQL 57014. The database error context identifies the ready-manifest
query inside `training_archive_gc_prepare`, before archive deletion.

## Reproduction and repair

The live table has about 1.50 million entry rows. A read-only EXPLAIN ANALYZE of
the existing selection took 39.05 seconds. Its blocker expansion visited 58,342
references across 1,000 blocking objects. It needed only the first blocker of
each candidate manifest. The isolated 100,000-entry fixture failed before the
fix (100,002 visited entry rows) and passes after it (fewer than 1,000).

The new migration replaces only the existing prepare function. Hashed blocker
membership and primary-key-ordered per-manifest traversal stop after the first
blocker. It adds no index, parallel owner, fallback or timeout increase. All
validation, mutation and audit code outside that selection remains identical.

All 10 real PostgreSQL safety cases pass, including comparisons against both
prior implementations across 24 mixed fixtures. Latest two manifests, active
pins, staged references, seven-day grace, size checks, partial-batch resumption,
rollback, deletion claims and service-only privileges are covered. The final
live read-only query took 358 ms on a warmed cache. This is observational evidence,
not a controlled cold-cache speed comparison. Full local regression: 1932 passed in 71.23s, with two existing empty-sample
Neuron warnings. Remote CI is now verified below; production deployment remains blocked.

## Verified merge and recovery

[PR #580](https://github.com/Abeel87/tenis-ai/pull/580) passed all 11 checks.
Remote full regression: 1932 passed in 83.18s with the same two known warnings.
Merge `7c183c5828ea8a858dfe0b43daa200fee970bbc2` exactly matches tested tree
`75deec7543f25d9f3691e2d1a48585e43c06c4b5` against fresh main `59ee7c1`.

Player DNA fast readiness run 42194876202 succeeded on attempt 2, including
its exact-snapshot guard for 101 matches. Pages retry 42194878718 failed again,
this time with empty status reports. Subsequent Pages run 42200919016 succeeded;
live HTTP 200 manifest matches `032e244290fe91856593a6337873f1b5725d0137`.
This verifies recovery, not a permanent fix for GitHub's deployment timeouts.
Private DNA run 42200921810 and its GC succeeded. Direct SQL confirms active
generation `2775bef5-0c14-4f8d-a3cc-12d5c437d9f1` from that same source,
14 physical objects, zero missing objects and zero size mismatches.

## Remaining provider confirmation

The migration is **not applied to production**. Two `apply_migration` requests
returned confirmation-expired responses. A fresh read of the deployed function
confirms the old query remains. No alternative route bypassed that confirmation,
and the archive GC job was not rerun against the old function.

The next step is to obtain the provider confirmation for the exact merged SQL,
verify the deployed body and unchanged service-only ACLs, then rerun existing
GC job 127818291913 and verify actual completion and protected manifests.
Models, training, identity, thresholds, SHADOW/PROD boundaries and Auth settings
remain unchanged. Missing player history remains an explicit coverage limitation.
