# Training archive GC timeout investigation — 2026-10-25

## Scope and evidence

Infrastructure only. Preserve latest two complete manifests, active pins, every
non-complete reference, 168-hour continuous eligibility, exact Storage size,
persisted claim/finalize recovery and all audit rows. No model mathematics,
training, settlement, SHADOW/PROD, retention duration, storage budget or Edge
authorization changes.

Source baseline: `f4f224868b5e45f7723331bd97788376f5281204`.
Supabase project: `kplcfqmcsukiqfbgvxcm`, PostgreSQL 17.6.1.155.

| Run | Apply result | Preview evidence |
| --- | --- | --- |
| [39962502594](https://github.com/Abeel87/tenis-ai/actions/runs/39962502594), 23 Oct | HTTP 500 / SQLSTATE 57014 after about 32s including transport | 56 complete, 54 expirable, 2991 grace-ready |
| [40139133284](https://github.com/Abeel87/tenis-ai/actions/runs/40139133284), 24 Oct | Same error after about 32s | 65 complete, 63 expirable, 3265 grace-ready |
| [40196696824](https://github.com/Abeel87/tenis-ai/actions/runs/40196696824), 25 Oct | Same error | 69 complete, 67 expirable, 3348 grace-ready / 946517044 B |

The live PostgreSQL error at `2026-10-25T13:16:04.932Z` names
`training_archive_gc_prepare`, line 54, at its `ready_manifests` SELECT. This is
not a Storage.remove failure. PostgreSQL rolled back the failed prepare before
the Edge Function could start a deletion batch.

Both live function configurations already contain `statement_timeout=30s`.
Both ACLs are `{postgres=X/postgres,service_role=X/postgres}`. The authenticator
default is 8s, but the observed cancellation is at the scoped 30s deadline.
Successful prepare calls on 25 Oct took 24592.661ms and 27351.671ms. Increasing
the deadline again would leave the growing scan cost unresolved.

## Root cause

At inspection there were 1099874 entries, 19330 archive objects, 73 complete
manifests and 112 non-complete manifests (16 expired, 96 abandoned). The terminal
manifests had no entries. Nevertheless, the optimizer estimated that many entry
rows matched them and chose a parallel full scan. EXPLAIN ANALYZE of the observer
candidate SELECT took 14499.604ms; the empty non-complete branch accounted for
12873.604ms, scanning about 550000 entries per worker.

Prepare additionally built an entry-level anti-join across the full history,
then matched those rows back to expirable manifests. Fixing only the observer's
empty branch was insufficient: that prepare SELECT still measured 30484.468ms.

## Canonical repair

Migration `20261025224109_training_archive_gc_query_plan.sql` replaces only
`training_archive_retention_observe` and `training_archive_gc_prepare`.

- Indexed lateral lookups retain the same selected manifest IDs and all their
  entries; `OFFSET 0` prevents join flattening without discarding any rows.
- Materialize blocking object SHAs once, then find their referencing manifests
  through the existing `training_archive_entries_sha_idx`.
- The entry-to-object FK is present in the live schema; no orphan entry can
  disappear from the object-first complement.
- Preserve observer candidate/grace updates, prepare mutations, pending-batch
  resume, 100-object default batch, 30s budget, fixed search paths and ACLs.
- Claim, Storage removal, finalize, finish, stale reaper, workflow schedule and
  shared publisher/GC concurrency are unchanged. No index or new runtime path.
- The migration itself changes function definitions only; it deletes no data.

Final read-only live plans measured 171.617ms for the candidate SELECT and
7498.596ms for the manifest readiness SELECT. Earlier measurements were 1071.6ms
and 6128.414ms respectively; timings vary with cache/load. These are individual
SELECT timings, not a claim about complete end-to-end workflow duration.

## Safety validation

- Original and optimized candidate sets and all aggregate counts were identical
  in one live query snapshot: 3817 candidates.
- Original and optimized manifest decisions were identical in one live query
  snapshot: zero ready manifests. No retention gate was relaxed to manufacture
  a nonzero deletion result.
- Before rollout: zero active pins, zero pending batches; the latest two
  complete manifests had 15512 entries each and zero absent/wrong-size objects.
  Archive reservation: 19330 objects / 1688430724 B.
- Ten isolated executable SQL/PLpgSQL tests pass with pinned PGlite 0.5.11
  (PostgreSQL 18.6). Live query analysis above uses production PostgreSQL 17.
  Tests cover latest-two/pins/staged refs, shared references, exact 168h boundary,
  clock restart/extension, missing/size-mismatched Storage, recovery after removal,
  idempotent finalization, bounded batches, rollback after expiry, 24 deterministic
  old/new equivalence fixtures, and a 100000-entry skewed query-plan regression.
- PGlite Storage rows are local test fixtures. Tests cannot call the real Storage
  service or assert real concurrent multi-session behavior. The existing shared
  maintenance mutex/concurrency and claim/finalize design are unchanged.
- Full Python regression: 1806 passed in 61.03s in an isolated temporary checkout;
  this includes three new tests proving unchanged surrounding function behavior.
  Remote CI/production rollout are recorded in the execution checkpoint;
  deployment must not be inferred from a migration file.

## Rollout and rollback

Require green CI and a fresh-main source comparison. Apply this exact migration,
compare live function definitions/configuration/ACLs and pre/post data counts,
then execute the normal OIDC GC workflow and reconcile the apply audit plus
protected-manifest integrity. Check advisors against the pre-migration baseline.

If the query repair needs reverting, restore the preceding two function bodies
with their existing 30s budgets and ACLs. This is a code rollback only: never
recreate expired entry references or undo audited object removals blindly.


## Production verification — 2026-10-27

Source PR [#560](https://github.com/Abeel87/tenis-ai/pull/560) merged as
`55cff432c9d05df7c40e4c77989d24c9046fd4dc`. All eight CI workflows passed on
`4e86afc50aa098c7e721d9341147fe8eb94415bd`, including the ten PostgreSQL tests.
The final health job `121317103822` reported 1806 Python tests passed in 60.06s.
Fresh main immediately before merge still matched the integrated
`8967cf37cff33c7c6868a33b6b27924014afa4a8`.

The earlier deployment approval requests expired; the migration was absent on
26 October and at the start of this continuation. Successful deployment was
confirmed on 27 October at 00:04 UTC under live migration version
`20261027000420`, name `training_archive_gc_query_plan`. The repository file
remains `20261025224109_training_archive_gc_query_plan.sql`; its SHA-256 is
`03298b84383dc6d3fb6a6662cd97c6e962c239de4ed1cbfd2569100f067e3f20`.

Both live PL/pgSQL bodies matched the reviewed file exactly. Owner `postgres`,
SECURITY DEFINER, fixed search paths, 30s budgets and ACLs were unchanged:
`anon` and `authenticated` cannot execute either function; `service_role`
can. Pre/post migration snapshots matched on all counts and all seven ordered
metadata fingerprints (manifests, objects, candidates, pins, retention audits,
apply audits and apply objects). The migration changed no archive rows or files.

### Normal workflow, real PostgreSQL 17

[Run 40196696824, attempt 2](https://github.com/Abeel87/tenis-ai/actions/runs/40196696824/attempts/2)
and job `121925205544` completed successfully through the existing OIDC path.

| Step | UTC interval | Result |
| --- | --- | --- |
| Preview seven-day retention gate | 00:05:33–00:05:35 | success |
| Apply grace-ready archive retention | 00:05:35–00:05:42 | success |
| Database apply audit | apply_id 111 | complete; 0 expired, planned, deleted or skipped |

Detailed log timestamps put the apply command at about 6.4s including transport,
versus the earlier roughly 32s cancellation. This is an end-to-end workflow
measurement, distinct from the individual read-only plans above.

The job checked out current main
`45c061a3556fbca305e7d6233db48e15f44798b3`. GitHub reruns retain the original
run SHA: `ca0e03e49db501fa5107576773db1b7331af8e3f`, which is also the
authenticated audit source SHA. These are intentionally recorded separately.
The Edge contract revision remained
`sha256:92b6049dc3586120bbb2d4e215ef94ebcb0362539e16b7aba24c7bb18e4f1ac8`.

### Why a successful run removed zero bytes

Preview reported 77 complete manifests, 2 retained and 75 expirable; 3829
eligible objects, of which 3597 were grace-ready (1317383873 B). However, 232
objects still had unexpired grace. An indexed reference check showed that these
young objects block all 75 expirable manifests. Every eligible object was
physically present with the expected size.

The next individual grace boundary observed was 2026-10-27 07:44:54.483028 UTC.
It does not guarantee that any entire manifest will then become ready. No grace,
reference, pin or latest-two gate was weakened to force deletion. This production
run validates successful preparation and safe no-op handling; nonempty removal,
recovery and rollback paths are exercised by the isolated SQL tests.

### Post-run integrity

| Check | Result |
| --- | --- |
| Archive entries | 1161922, unchanged |
| Registered / physical archive objects | 19344 / 19344, unchanged |
| Registered archive bytes | 1692826501, unchanged |
| Protected unique objects | 15515; zero missing or wrong-size |
| Active pins / pending apply batches | 0 / 0 |
| Latest complete manifests | ca57bbb4-a944-4361-98b0-abab755b18c0; 02813937-0832-4fc8-97ec-6d6fb3c5bc15 |

Manifest/object fingerprints remained unchanged after the workflow. Candidate
observation metadata and audit rows advanced normally. Security advisor findings
were identical before and after deployment; existing unrelated findings were not
silently treated as resolved. Performance advisors listed 11 unused-index INFO
findings and one auth-connection INFO finding; no indexes or connection settings
were changed.

The repair is deployed and production-verified. Continue through the existing
scheduled GC. Model mathematics, training, settlement and SHADOW/PROD rules remain
outside this infrastructure-only change.
