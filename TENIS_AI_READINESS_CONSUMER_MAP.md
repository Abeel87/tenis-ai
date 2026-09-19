# Tenis AI — legacy `model_ready` consumer map

Status: **LOGIC-08 consumer-audit contract / no runtime migration**

Base audited: `fd44c0546b3167554046a018b9fce1d02b35cbed` (PR #402 merged).

This inventory freezes every source file under `backend/` and `frontend/` that contains the exact standalone token `model_ready` on the audited base. It is an audit/migration map, not a new readiness implementation.

## Contract boundaries

- Canonical legacy producer remains Current Engine (`backend/model.py` / `backend/model_core.py`).
- Canonical semantic SHADOW owner remains `backend/readiness_engine_shadow.py`.
- No consumer is migrated by this map.
- PBP `market_evidence_v940.market_ready`, Symphony `learning_model_ready`, and Superbet operator-market availability are separate contracts and are not aliases of semantic readiness.
- An unapproved sufficiency policy must remain `UNKNOWN`; coverage alone is not readiness.

## Exact-token inventory

| File | Role | Migration note |
| --- | --- | --- |
| `backend/model.py` | legacy producer | Do not redefine in consumer audit. |
| `backend/model_core.py` | legacy producer | Do not redefine in consumer audit. |
| `backend/history_tracker.py` | runtime gate | Skips matches when legacy readiness is false. Requires separate evidence gate. |
| `backend/market_lab_v741.py` | runtime gate | Also requires service model / exact first-set inputs. |
| `backend/pbp_cache_recovery.py` | runtime gate | Legacy readiness + service model currently select recovery targets. |
| `backend/pbp_enrich.py` | runtime gate | Legacy readiness + service model currently select enrichment targets. |
| `backend/autolearn_v84.py` | learning/selection gate | Observation capture filters on legacy readiness. |
| `backend/specialist_learning_v79b.py` | learning/selection gate | Learning sample selection filters on legacy readiness. |
| `backend/shadow_lab_v78e6.py` | SHADOW selection gate | Uses legacy readiness for signal selection/rejection semantics. |
| `backend/update.py` | telemetry/meta copy | Counts legacy-ready visible fixtures; not a new readiness owner. |
| `backend/prediction_integrity_v78a.py` | diagnostic consumer | Uses legacy readiness for a BO3/best-of warning path. |
| `frontend/app.js` | UI presentation/filtering | Card copy, moderator problem/badges, diagnostics and admin counts currently use legacy readiness. |
| `backend/context_engine_shadow.py` | SHADOW observational copy | Captures readiness-at-snapshot only. |
| `backend/player_dna_player_state_shadow.py` | SHADOW observational copy | Copies selected Current Engine fields; no readiness ownership. |
| `backend/readiness_engine_shadow.py` | canonical semantic SHADOW owner | Reads legacy boolean for comparison only; write/gating disabled. |
| `backend/history_coverage_audit.py` | audit consumer | Coverage diagnostics only. |
| `backend/history_freshness_counterfactual.py` | audit/counterfactual consumer | Compares readiness under freshness scenarios; no PROD migration. |
| `backend/population_priors_audit.py` | audit/counterfactual consumer | Uses readiness to scope/compare evidence. |
| `backend/ranking_provenance_audit.py` | audit consumer | Uses readiness for provenance slices. |
| `backend/tml_2024_integration_readiness_audit.py` | audit/counterfactual consumer | Compares stored/baseline/preview readiness. |
| `backend/tml_2024_runtime_equivalence_audit.py` | audit/counterfactual consumer | Compares baseline/augmented readiness. |

Audited exact-token source count: **21 files**.

## Migration order

1. **Audit only now:** freeze this inventory and semantic separation with tests. No consumer behavior changes.
2. **Observability later:** expose semantic readiness in diagnostics/UI beside legacy `model_ready`, preserving `N/D`/`UNKNOWN` and keeping old behavior intact.
3. **Telemetry later:** migrate aggregate/meta reporting only after consumers can distinguish legacy technical readiness from semantic dimensions.
4. **Runtime/learning gates last:** `history_tracker`, Market Lab, PBP paths, AutoLearn/specialist learning and SHADOW selection require consumer-specific evidence and contract tests before any gate replacement.
5. **Legacy removal only after all consumers migrate:** do not delete/redefine `model_ready` while any audited consumer still depends on it.

## Separate similarly named contracts

- `backend/pbp_market_evidence.py` / `market_evidence_v940.market_ready`: PBP market-evidence sufficiency for explicit markets.
- `backend/symphony2_engine.py` / `learning_model_ready`: Symphony learning-model state, not universal match readiness.
- `backend/superbet_direct.py` / operator market evidence: current operator offer availability, not model-data readiness.
- `backend/apply_joint_to_results.py`: aggregates PBP market readiness; it must not be reinterpreted as legacy or semantic overall readiness.

## Phase-3 requirement matrix

Consumer-specific migration requirements are defined in `TENIS_AI_READINESS_REQUIREMENT_MATRIX.md`, audited on main `eec6483ed942ebab9193ef4bd4681ac352f3490c`.

The matrix covers **22 exact legacy tokens on 19 source lines** across runtime/collection, learning/SHADOW, telemetry/guard and frontend consumers. No runtime/learning gate is approved for replacement. Missing sufficiency policy remains `UNKNOWN / NO MIGRATION`.

The first selected observability-only path is additive aggregate/meta telemetry in `backend/update.py` (R12/R13), followed by diagnostic/admin UI counters only after exact snapshot alignment is proven. Legacy `meta.model_ready` and all current runtime behavior remain unchanged in this audit phase.