# Training archive retention preview

This phase adds reference-aware retention metadata and a **preview only** GC calculation. It does not delete manifests, database rows or Supabase Storage objects.

## Retention rules

The preview is deliberately conservative:

1. always retain at least the two newest `complete` archive manifests,
2. retain every `complete` manifest with at least one active pin,
3. retain every object referenced by a non-`complete` manifest,
4. only classify objects outside those retained references as *eventually reclaimable*,
5. perform no mutation or deletion from the preview function.

The minimum rolling window of two complete manifests preserves an immediate rollback/reproducibility fallback even when no explicit research release has been pinned.

## Pins

`training_archive_manifest_pins` maps a stable `pin_key` to an archive manifest. Pins are private system metadata: RLS is enabled, browser roles have no table grants, and only `service_role` may manage them.

An active pin has `released_at IS NULL`. Releasing a pin does not delete anything; it only allows a later preview to classify the manifest as expirable if it also falls outside the rolling window.

Suggested future pin keys are stable release identities such as a training experiment, benchmark, audit, or reproducibility release. A pin must never be created merely to make a check pass.

## Preview RPC

`training_archive_retention_preview(p_keep_latest)` is service-role-only and returns aggregate counts for:

- complete manifests,
- active pins and distinct pinned manifests,
- retained complete manifests,
- expirable complete manifests,
- objects and bytes that would eventually become reclaimable after expirable manifests are retired.

`p_keep_latest` is constrained to `2..100`.

## No deletion yet

The preview intentionally has no grace-period clock and no delete operation. A future GC phase must separately define and test:

- how a rolling manifest becomes formally expired,
- when the grace period starts,
- how pinned manifests block expiry,
- how object reference counts are recomputed after expiry,
- physical Storage deletion ordering and retry safety,
- audit records for every manifest/object removed and every byte reclaimed.

Until that phase is explicitly deployed, every current archive manifest and object remains untouched.
