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
Neuron warnings. Remote CI and deployment remain pending.

## Other observed failures

- FAST Pages run 42194878718 stalled at `syncing_files`; native attempt 2 was
  requested. Payload reduction alone does not establish a fix for this service timeout.
- Player DNA fast readiness run 42194876202 committed readiness successfully,
  then GitHub returned HTTP 500 for workflow dispatch. Native attempt 2 was requested.
- Recovery outcomes and actual GC deployment must be recorded before closeout.

Production migration is not yet applied. Models, training, identity, thresholds,
SHADOW/PROD boundaries and Auth settings remain unchanged.
