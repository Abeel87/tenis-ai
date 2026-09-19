# TENIS AI — LOGIC-08 phase-4 readiness observability delivery audit

Status: **AUDIT / NO RUNTIME OR UI WIRING**

Original audited base: `c6e4dc7301ffdf1eda66d3b222e61729b95c11db` (PR #407 merged). Revalidated after data drift on `57a5def75b14ea849abe3c9e3cfb7ce761aa305a` (`data: refresh Superbet market context`), `8742c48aaf40efd60b3a9d2a1f665bb9de1323e0` (`data: refresh rebuilt Neuron SHADOW`), `a8c3bea2a9e833a8d75fed107d3c9835d667696f` (`data: refresh tennis analysis`), and fresh `main` `de6387273eb19b10b02f94f572b53567ab3011ec` (`data: refresh Superbet market context`).

## Problem

R12/R13 selected additive SHADOW readiness telemetry beside legacy `meta.model_ready`, but the canonical semantic report is not a current tracked runtime input. Joining an old Point Tape artifact to a newer `results.json` would create false observability.

This phase therefore defines an exact-snapshot join contract before any meta/UI wiring.

## Current delivery topology

| Data/evidence | Current producer/path | Tracked on main | Safe direct input for current R12/R13? |
| --- | --- | --- | --- |
| `frontend/data/results.json` | Update tennis data workflow / `backend/update.py` | yes | canonical current result snapshot |
| `frontend/data/history_coverage_audit_v949.json` | `Update-and-Pages` ? `scripts/verify_audit_consistency.py` ? `history_coverage_audit.write_current_audit()` | yes | only with exact results-digest alignment |
| `frontend/data/player_dna_profile_readiness.json` | Player DNA SHADOW refresh | yes | supporting audit only |
| `player_dna_service_split_source_readiness.json` | Point Tape audit | no | artifact-only today |
| `player_dna_pbp_service_split_readiness.json` | Point Tape audit | no | artifact-only today |
| `player_dna_match_state_readiness.json` | Point Tape audit | no | artifact-only today |
| `player_dna_matchup_readiness_audit.json` | Point Tape audit | no | artifact-only today |
| `player_dna_player_state_shadow.json` | recent-form CLI delegates Player State inside Point Tape | no | artifact-only today |
| `readiness_engine_shadow.json` | Point Tape audit | no | artifact-only today |

## Workflow facts

- `Point Tape Schema Audit` has `workflow_dispatch` and PR triggers, but no `workflow_run` after the live data refresh. Its readiness artifact is therefore evidence, not a guaranteed current runtime snapshot.
- `Player DNA SHADOW refresh` already has `workflow_run` after successful `Update tennis data and deploy Pages`, checks out current `main`, restores the tennis cache, and builds SHADOW Player DNA outputs. It is the natural candidate host for later same-snapshot readiness generation; this audit does not wire it yet.
- `Update tennis data and deploy Pages` regenerates history coverage through `scripts/verify_audit_consistency.py`, but later Superbet/data refresh commits may change `results.json` without regenerating coverage. Equal counts and subset IDs are therefore insufficient as a join proof.
- `Update tennis data and deploy Pages` treats `frontend/data/**` as a heavy data change through `.github/scripts/change_scope.py`. A new standalone tracked sidecar commit could retrigger the data workflow, so publication must not create an unbounded workflow/data-commit loop.
- No new workflow is justified. Reuse an existing owner after dependency proof.

## Exact-snapshot join contract

Canonical owner remains `backend/readiness_engine_shadow.py`.

`results_snapshot_sha256` is SHA-256 of deterministic canonical JSON for the complete current `results` list (`sort_keys=True`, compact separators, UTF-8). The canonical history-coverage owner remains unchanged. Inside Point Tape, coverage is first regenerated from the restored cache, then `backend/snapshot_digest.py` stamps that run-local report with the current results contract/digest before readiness reads it. The readiness report records:

- `source_snapshot.results_snapshot_contract = canonical-json-sha256-v1`,
- `source_snapshot.results_snapshot_sha256`,
- history coverage alignment only when its own results digest exactly matches the current results digest,
- existing Player State alignment flag,
- existing legacy Current Engine mismatch count.

An observability consumer may use semantic readiness only when all of these are true:

1. readiness report status is `READINESS_SEMANTICS_SHADOW_EVIDENCE_READY`,
2. current results digest exactly equals the recorded readiness digest,
3. history coverage carries the same canonical results digest and snapshot alignment is true,
4. Player State snapshot alignment is true,
5. legacy Current Engine reference mismatches equal zero.

If any condition fails, semantic observability is unavailable: render/emit `N/D` with a reason code. Never translate mismatch/missing evidence to zero, `NOT_READY`, or `READY`.

`observability_snapshot_alignment()` now centralizes the consumer-side fail-closed contract. `Point Tape Schema Audit` rebuilds history coverage from restored cache and stamps that fresh run-local file in the same fail-fast step before semantic readiness. The generic `history_coverage_audit.py` contract is not changed. This prevents an older tracked coverage file with coincidentally equal counts/IDs from being treated as exact-snapshot evidence. The `player-dna-point-foundation` artifact also carries the exact `results.json`, that run-local stamped `history_coverage_audit_v949.json`, and `readiness_engine_shadow.json`, enabling independent post-run digest comparison. It does not write meta, change a gate, create probability, or activate a feature.

## Rejected shortcuts

- downloading the latest Point Tape artifact and assuming it matches current `results.json`,
- accepting only equal match counts or overlapping IDs,
- modifying the generic history/identity audit contract merely to carry LOGIC-08 provenance,
- using timestamps as the sole join key,
- frontend inference from legacy `model_ready`,
- creating a parallel readiness workflow solely to patch delivery,
- committing a new tracked sidecar without proving bounded workflow behavior.

## Next implementation gate

1. Validate the existing Player DNA SHADOW refresh as the candidate same-snapshot producer host for all readiness prerequisites after successful Update.
2. Prove module dependency order and zero-network behavior on that host.
3. Prove publication cannot create an unbounded Update ↔ SHADOW commit loop.
4. Only then publish a compact SHADOW observability payload or wire R12/R13 through the canonical backend owner.
5. Current `meta.model_ready` remains unchanged throughout.
6. UI R18/R19 stays blocked until backend delivery is exact-snapshot and provenance-complete.

Runtime/learning gates remain out of scope. R07/R08/R11 stay deferred to LOGIC-09 and R14 to LOGIC-10.

## Candidate producer-host evidence

The existing `Player DNA SHADOW refresh` is the preferred candidate host for a later same-snapshot producer because it already:

- accepts `workflow_run` from successful `Update tennis data and deploy Pages` on `main`,
- checks out current `main`,
- restores the tennis history/PBP cache,
- builds the strict point dataset and leakage-safe profile snapshots required by recent-form/Player State evidence,
- owns an existing SHADOW artifact upload and existing SHADOW report publish commit,
- explicitly dispatches FAST Pages only when that existing report commit changed data.

The phase-4 prerequisite modules contain no network-client imports/API-key usage; history coverage explicitly reads the same cached TML sources used by Update. Candidate order is therefore local-only: cache/history audits → service/PBP/match-state audits → Player DNA profiles → matchup/recent-form → Player State → readiness.

### Workflow-loop evidence

Existing Player DNA SHADOW publish commit `34285c926ce20757dab8d8ab03fda3ab736368e2` was created by successful Player DNA run `35435083725`. Runs attached to that bot commit were FAST Pages `35437360643` and Runtime private delivery staging `35437364257`; no `Update tennis data and deploy Pages` run was created for that commit.

This is evidence that extending the **existing** SHADOW publish payload is materially safer than adding a separate workflow/commit. It is not authorization to wire observability yet: the implementation PR must preserve the existing one-commit publication path and re-verify run topology.
