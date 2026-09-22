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

## Manifest expiry

GC never hard-deletes a retained manifest. A `complete` manifest may become `expired` only when every object that would otherwise become unreferenced has completed grace and still exists in Storage at the exact recorded size. The manifest row remains as durable provenance; its entry rows are removed only after that gate passes.

## Object deletion

Only an object with zero live archive-entry references, a current grace-ready candidate row, and exact physical Storage size may be claimed for deletion. The apply plan is persisted before Storage mutation.

Before Storage removal, the database records `remove_started_at`. If a process dies after physical deletion, a later run may finalize that recorded removal. A physically missing object without a prior remove-start marker is treated as an unsafe integrity state and stops the GC rather than being silently normalized.

After successful Storage removal the finalizer revalidates zero references, current grace eligibility, and physical absence before deleting the candidate/object metadata. Every apply and every planned object remains in durable private audit tables with deleted/skipped byte counts.

## Deployment drift

The GC Edge Function returns a source-derived SHA-256 `contract_revision`. The GitHub caller fails closed unless the deployed revision exactly matches the canonical function on `main`. Because this repository has no Supabase management access token, source changes to the Edge Function must be deployed explicitly before the GC workflow can pass.
