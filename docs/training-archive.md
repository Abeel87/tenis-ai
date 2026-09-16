# Durable training archive

## Purpose

GitHub Actions `data/cache` is an operational cache, not a durable or reproducible training archive. Cache eviction must not be able to erase the raw inputs needed to reproduce historical features or a trained experiment.

This archive is deliberately separate from the private runtime delivery path. It must not change model mathematics, probabilities, thresholds, weights, training behaviour, Player DNA, Surface Elo, Symphony, Neuron, PLAYABLE, settlement, SHADOW/PROD or iNeed$ calculations.

## Phase 1: inventory only

The first rollout phase only measures the restored Actions cache. It does **not** create a Supabase bucket and it does **not** upload archive objects.

`backend/training_archive_inventory.py` classifies cache files into:

- `historical_csv_raw` — compressed historical CSV source inputs (`*.csv.gz` outside `pbp_v7`),
- `pbp_match_raw` — compressed match-level point-by-point source payloads under `pbp_v7/matches/`,
- `pbp_state` — the minimal `players.json` and `terminal_refresh.json` PBP indexes/state needed to restore the raw PBP cache coherently,
- `rebuildable_cache` — model downloads, temporary responses and other cache material that should not consume durable archive storage by default.

Only the first three classes are archive candidates. Published `frontend/data/*.json` are derived/runtime products and are intentionally not mirrored into the training archive by this inventory.

Every candidate is measured and SHA-256 hashed. The report includes logical bytes, unique content-addressed bytes and potential deduplication savings. A workflow triggered after a successful main data update restores the newest tennis cache and uploads the inventory report as a short-lived Actions artifact.

A missing cache is a hard inventory failure rather than a misleading zero-byte success.

## Target archive architecture

When the measured raw footprint fits the storage budget, the durable implementation should use a dedicated private bucket, for example `tenis-ai-training-archive`, never `tenis-ai-runtime-private`.

Objects are immutable and content-addressed:

```text
objects/sha256/<first-two-hex>/<full-sha256>
```

A logical path is metadata, not the physical object key. Identical bytes from multiple logical inputs are stored once.

### Immutable manifests

Each archived snapshot/training release should have an immutable manifest with at least:

- manifest schema version,
- source logical path,
- content SHA-256,
- byte length and content type,
- source/provider identity and source locator when available,
- source fetch timestamp when available,
- producer repository commit,
- workflow/run provenance,
- raw/derived classification,
- parent/input digests for derived artifacts when a derived artifact is explicitly pinned,
- archive object key.

Training/research releases pin the exact raw digests they consumed. Pinned digests are not eligible for garbage collection.

## Retention and garbage collection

The archive must use reference-aware retention rather than age-only deletion:

1. preserve every object referenced by a pinned training/research manifest,
2. preserve current raw source inputs required by active rebuilds,
3. deduplicate globally by SHA-256,
4. apply a grace period before deleting newly-unreferenced content,
5. delete an object only when no retained manifest references it,
6. record every archive GC decision and reclaimed byte count.

Rebuildable cache material is not archived unless a later reproducibility requirement explicitly pins it.

## Storage budget gate

The Supabase project is capacity-constrained, so archive writes remain disabled until a real inventory run provides the candidate and unique-byte footprint.

Before enabling uploads, define and test a budget gate that accounts for:

- current total Supabase Storage usage,
- a protected reserve for runtime growth and rollback generations,
- the measured unique archive bytes after SHA-256 deduplication,
- expected archive growth between GC cycles.

The uploader must fail closed before exceeding its configured archive budget. It must not borrow the runtime bucket's retention policy or assume unused Free-plan capacity is permanently available.

## Authentication for future uploads

Do not add a long-lived public upload path. The preferred writer is a GitHub Actions identity authenticated through a narrowly scoped GitHub OIDC trust path, analogous to the private runtime delivery controls, with repository/workflow/ref/audience checks and server-side byte/budget validation.

The archive remains private. Browser/frontend clients do not receive direct archive credentials or signed URLs as part of normal application operation.

## Cutover rule

Inventory and archive work is independent of the frontend private-read cutover. It must not be used as a reason to disable generated-data direct pushes, remove public runtime data, or enable branch protection before the required real Auth E2E is complete.
