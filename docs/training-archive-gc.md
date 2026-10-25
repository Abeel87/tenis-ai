# Training archive retention GC apply

This phase is the destructive executor for the already-existing seven-day training-archive retention policy. It does not change model math, probability, training, Player DNA, Surface Elo, Symphony, Neuron, PLAYABLE, settlement, SHADOW/PROD, or iNeed$ calculations.

## Policy

- keep at least the 2 newest `complete` manifests,
- keep every actively pinned `complete` manifest,
- keep every object referenced by a non-`complete` manifest,
- require 168 hours of continuous eligibility before destructive apply,
- re-run the retention observer immediately before apply,
- serialize GC and archive publication through the repository-wide `training-archive-maintenance` concurrency group.

The scheduled GC workflow runs four times per day and is also manually dispatchable. Every run executes preview before apply.

## Failed publication lifecycle

A publisher failure explicitly changes its own authenticated `staged` manifest to `abandoned` in one database transaction and removes only that incomplete manifest's entry rows. A bounded GC reaper applies the same transition to `staged` manifests older than 24 hours, covering interrupted runners that could not call the publisher cleanup action.

Abandonment never removes archive objects or Storage rows. It only releases incomplete references, after which the normal observer starts a new 168-hour continuous-eligibility window. Latest-two retention, active pins, exact Storage-size verification and the audited GC apply remain mandatory.

## Manifest expiry

GC never hard-deletes a retained manifest. A `complete` manifest may become `expired` only when every object that would otherwise become unreferenced has completed grace and still exists in Storage at the exact recorded size. The manifest row remains as durable provenance; its entry rows are removed only after that gate passes.

## Object deletion

Only an object with zero live archive-entry references, a current grace-ready candidate row, and exact physical Storage size may be claimed for deletion. The apply plan is persisted before Storage mutation.

Before Storage removal, the database records `remove_started_at`. If a process dies after physical deletion, a later run may finalize that recorded removal. A physically missing object without a prior remove-start marker is treated as an unsafe integrity state and stops the GC rather than being silently normalized.

After successful Storage removal the finalizer revalidates zero references, current grace eligibility, and physical absence before deleting the candidate/object metadata. Every apply and every planned object remains in durable private audit tables with deleted/skipped byte counts.

## Deployment drift

The GC Edge Function returns a source-derived SHA-256 `contract_revision`. The GitHub caller fails closed unless the deployed revision exactly matches the canonical function on `main`. Because this repository has no Supabase management access token, source changes to the Edge Function must be deployed explicitly before the GC workflow can pass.

## Query-plan repair (2026-10-25)

The observer and prepare RPC retain their 30-second function budgets. Their
reference queries use parameterized entry-index lookups for both retained and
non-complete manifests. `OFFSET 0` is a planner boundary, not a row limit: every
reference is still checked, including references on unusual terminal states.
Prepare first identifies unprotected objects lacking a valid grace-ready,
exact-size Storage match, then finds the manifests referencing those blockers
through the existing SHA index. The validated entry-to-object foreign key makes
this equivalent to the former entry-first anti-join.

A large `grace_ready_objects` count does not mean all those objects can already
be removed. A complete manifest containing even one unprotected immature,
missing or wrong-size object cannot expire. Any remaining entry reference then
prevents physical removal. A successful zero-deletion run is valid in that case.

Run `node --test tests/training_archive_gc_postgres.mjs` after `npm ci` for
isolated PostgreSQL/PLpgSQL retention, rollback, resume and query-plan tests.
These use a local Storage metadata fixture, not the Storage service. Live
PostgreSQL 17 read-only query plans and rollout evidence are recorded in
`audits/training_archive_gc_timeout_20261025.md`.
