# Durable training archive

## Purpose

GitHub Actions `data/cache` is an operational cache, not a durable or reproducible training archive. Cache eviction must not be able to erase the raw inputs needed to reproduce historical features or a trained experiment.

This archive is deliberately separate from the private runtime delivery path. It must not change model mathematics, probabilities, thresholds, weights, training behaviour, Player DNA, Surface Elo, Symphony, Neuron, PLAYABLE, settlement, SHADOW/PROD or iNeed$ calculations.

## Phase 1: inventory

The first rollout phase measured the restored Actions cache before durable writes were enabled.

`backend/training_archive_inventory.py` classifies cache files into:

- `historical_csv_raw` — compressed historical CSV source inputs (`*.csv.gz` outside `pbp_v7`),
- `pbp_match_raw` — compressed match-level point-by-point source payloads under `pbp_v7/matches/`,
- `pbp_state` — the minimal `players.json` and `terminal_refresh.json` PBP indexes/state needed to restore the raw PBP cache coherently,
- `rebuildable_cache` — model downloads, temporary responses and other cache material that should not consume durable archive storage by default.

Only the first three classes are archive candidates. Published `frontend/data/*.json` are derived/runtime products and are intentionally not mirrored into the training archive by this inventory.

Every candidate is measured and SHA-256 hashed. The report includes logical bytes, unique content-addressed bytes and potential deduplication savings. A workflow triggered after a successful main data update restores the newest tennis cache and uploads the inventory report as a short-lived Actions artifact.

A missing cache is a hard inventory failure rather than a misleading zero-byte success.

## Durable archive architecture

The active implementation uses the dedicated private bucket `tenis-ai-training-archive-private`, never `tenis-ai-runtime-private`.

Objects are immutable and content-addressed:

```text
objects/<first-two-hex>/<full-sha256>
```

A logical path is metadata, not the physical object key. Identical bytes from multiple logical inputs and snapshots are stored once.

### Immutable manifests

Each archived snapshot records:

- manifest schema version,
- source logical path,
- content SHA-256,
- byte length,
- source/provider identity,
- producer repository/workflow provenance,
- raw/state classification,
- archive object key through the content digest.

A manifest is finalized only after counts, bytes, SHA references and physical Storage presence/size have been rechecked server-side.

## Retention and garbage collection

The archive must use reference-aware retention rather than age-only deletion:

1. preserve every object referenced by a pinned training/research manifest,
2. preserve current raw source inputs required by active rebuilds,
3. deduplicate globally by SHA-256,
4. apply a grace period before deleting newly-unreferenced content,
5. delete an object only when no retained manifest references it,
6. record every archive GC decision and reclaimed byte count.

Rebuildable cache material is not archived unless a later reproducibility requirement explicitly pins it. The storage-budget gate does **not** delete archive objects; reference-aware GC remains a separate, explicitly controlled operation.

## Storage budget gate

Archive publication is fail-closed behind the canonical server-side manifest and object-reservation budget triggers.

The current safety ceilings are:

- `30000000000` bytes (30 GB) maximum archive-reserved footprint,
- `75000000000` bytes (75 GB) maximum project-accounted Storage for archive writes.

These bounded limits target the confirmed Supabase Pro organization with 100 GB of included file Storage. Database disk (8 GB included per project) is a separate quota. GitHub Pro does not change either Supabase quota. The project ceiling leaves at least 25 GB of nominal allowance outside archive admission, and must be reviewed before any plan downgrade or additional project shares the organization allowance.

The project-accounted value includes physical objects from all buckets plus archive object reservations whose physical upload is missing. Manifest admission rejects an already-exceeded budget. The object trigger serializes reservations with the existing advisory lock and checks the resulting actual, globally deduplicated footprint after each insert statement. An oversized reservation rolls back before signed upload URLs are issued; an already-stored SHA is not charged again as a whole new manifest.

The ceiling controls archive writes, not every Storage producer. Runtime storage retains its own lifecycle. Neither the limits nor this migration delete data, change retention/pins/grace, alter access permissions, or change model/training behaviour.

## Authentication

There is no long-lived public upload path. The writer is GitHub Actions authenticated through a narrowly scoped GitHub OIDC trust path with repository, repository ID, owner ID, workflow, ref and audience checks.

The archive remains private. Browser/frontend clients do not receive direct archive credentials or signed URLs as part of normal application operation.

## Cutover rule

Inventory and archive work is independent of the frontend private-read cutover. It must not be used as a reason to disable generated-data direct pushes, remove public runtime data, or enable branch protection before the required real Auth E2E is complete.
