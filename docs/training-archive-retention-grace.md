# Training archive retention grace audit

This phase adds a grace-period clock and durable observation history for archive retention. It is intentionally **non-destructive**: no manifest, database object, or Supabase Storage object is expired or deleted.

## Default policy

The observer uses these conservative defaults:

- retain at least the 2 newest `complete` manifests,
- retain every actively pinned `complete` manifest,
- retain every object referenced by a non-`complete` manifest,
- require 168 hours (7 days) of continuous eligibility before an object becomes `grace_ready`,
- never shorten an already-running grace window when the configured grace period is increased,
- restart the full grace window if an object stops being eligible and becomes eligible again later.

`p_keep_latest` is constrained to `2..100`. `p_grace_hours` is constrained to `24..720` (1..30 days).

## Candidate tracking

`training_archive_gc_candidates` is private system metadata. For each content-addressed SHA it records:

- expected byte size,
- first and most recent time it was observed as eligible,
- `grace_until`,
- whether it is currently eligible,
- when eligibility was lost,
- observation count.

The table is RLS-enabled. Browser roles have no grants. `service_role` receives read access only; state changes are performed through the restricted SECURITY DEFINER observer.

If a previously eligible SHA becomes referenced by the rolling retention window, a pin, or an in-flight manifest, the observer marks it non-eligible. No archive data is touched.

## Immutable observation audit

Every call to `training_archive_retention_observe(p_keep_latest, p_grace_hours)` appends one aggregate row to `training_archive_retention_audit` containing:

- complete/pinned/retained/expirable manifest counts,
- current candidate object/byte counts,
- grace-ready object/byte counts,
- the number of candidates deactivated during that observation,
- the policy inputs and observation timestamp.

The audit table is RLS-enabled and read-only to `service_role`; writes occur only inside the observer function.

## Safety boundary

This phase deliberately does **not** add:

- a manifest-expiry mutation,
- `DELETE` against archive tables,
- Supabase Storage removal,
- an automatic GC workflow,
- a scheduled task that applies deletions.

A later GC apply phase must revalidate pins, rolling retention, in-flight manifests, physical Storage presence/size, and the candidate's grace window immediately before any destructive action. It must also be idempotent and record each deletion and reclaimed byte count.

Until that separate phase is designed, reviewed, merged, and deployed, `grace_ready` means only "eligible for a future destructive review" — not "safe to delete automatically".
