# TENIS AI - Guard Ownership Audit

**Program:** LOGIC-10 - Guard Ownership / Dead Logic Audit

**Audit base:** `76c4f505d55a5b7c07856a90dab0093c65e5aae8` (phase-3 branch created from merged phase-2 PR #423; phase-1 BO5 discovery originally audited on `5fbe321987bd271240bacd16c382efbd38e02145`).

**Status:** COMPLETE - PR #422 / #423 / #424 merged. Phase-3 PR #424 merged as `2b81e589e3d9f78db31d7f41b2959f091fc4bc1c` after exact-head all-green CI, `BAD_OR_PENDING=0`, base==main and MERGEABLE checks. Post-merge Delivery/Security and UI Health are GREEN; final Player DNA SHADOW completed SUCCESS 34/34 and published `e17e4c4ac37f15d79d5c2c4398ed00d513614c20`. Subsequent Update/Neuron/Superbet generated-data commits advanced main to `a329444df36968a48aa92ce2e3d26ae1dea011e6`; Runtime Private and Fast frontend deploy on that settled head are GREEN.

## 1. Scope and rules

This audit inventories active workflow steps whose names contain `guard` or `validat`, assigns each invocation to a canonical file-backed entrypoint or to its workflow inline block, and deep-audits the first confirmed collision in the BO5 path.

An **invocation** is not automatically a second owner. The same canonical verifier can run in more than one CI surface. That is duplicate execution, not duplicate ownership, unless the implementations enforce conflicting invariants.

Hard boundary: this audit does not change Current Engine probability math, thresholds, weights, training, Player DNA PROD, Surface Elo, Symphony probability, PLAYABLE policy, production settlement, SHADOW->PROD, or iNeed$ calculations.

## 2. Inventory summary

- Active guard/validation invocations after the phase-3 semantic naming cleanup: **92**.
- Workflows containing them: **28**.
- `update-and-pages.yml`: **24** invocations.
- `point-tape-audit.yml`: **26** invocations.
- `ui-smoke.yml`: **10** invocations.
- File-backed verifier repeated in multiple workflows = repeated enforcement of one owner, not a second owner by itself.
- Inline workflow guards are owned by the exact workflow step until/unless a canonical source module is extracted. No wrapper is introduced by this audit.

## 3. Confirmed BO5 collision

### Canonical producer

`backend/model.py` is the Current Engine owner of match-format-aware full-match output. It reads `best_of`, calls `_match_distribution_conditional(..., best_of=best_of)`, uses BO5-specific total-game lines, and emits `match_win`, `match_over_under`, `expected_match_games`, `total_sets`, and `exact_match_score` for legal BO5 model-ready fixtures.

### Stale conflicting guard

`backend/prediction_integrity_v78a.py::apply_pre_output_guards()` previously erased all five canonical BO5 full-match outputs and added `bo5_guard_v78a=True`. The same module later rejected non-N/D BO5 full-match fields. That historical fail-safe directly contradicted the current canonical producer.

### Ownership-preserving repair

- `apply_pre_output_guards()` now only normalizes `best_of`; it no longer rewrites legal Current Engine markets.
- BO5 integrity validation now checks the **format score-space** instead of demanding N/D: exact match scores must be in `{3:0, 3:1, 3:2, 2:3, 1:3, 0:3}` and total-set outcomes in `{3 sety, 4 sety, 5 sety}` when those maps are present.
- `backend/market_lab_v741.py` remains its own owner: BO5 stays `LAB_SET1_ONLY`.
- `backend/serve_props.py` remains its own owner: BO5 remains `ready=false` with reason `bo5_full_match_not_supported`.
- No new guard was added to compensate for another guard.

### Regression evidence

- RED reproduction before repair: **2 BO5 tests failed** because legal full-match BO5 output was erased and invalid BO3 score-space was not rejected by the intended invariant.
- Current Engine + integrity targeted pack: **11/11 passed** after the minimal repair.
- BO5/downstream pack covering integrity, Current Engine, Market Lab, Superbet line coverage, Superbet market projection and TML runtime equivalence: **47/47 passed**.
- PR #422 exact-head CI: all checks GREEN; merged as `aada53ad34d6613fbe628ad0a66a11348526658b`. Post-merge Update #65: Prediction integrity step #20 GREEN, final full regression #75 GREEN, refreshed JSON publication #77 GREEN, Pages artifact/deploy GREEN; bot publication moved main to `80098542d59f9ee402e33c997eb29200d286054c`.

## 4. High-risk execution contract

| Guard / owner | Input | Output / failure channel | Reason semantics | Order / boundary | Finding |
| --- | --- | --- | --- | --- | --- |
| `backend/prediction_integrity_v78a.py` | `frontend/data/results.json` after Market Lab, Serve Props, PBP joint rebuild and Player Intelligence PRE | writes `integrity_report_v78a.json`, integrity fields in `meta.json`; exits non-zero on hard errors | explicit human-readable invariant errors; BO5 score-space now structural | `update-and-pages.yml` Prediction integrity gate | **BO5 collision repaired in PR #422; post-merge Update #65 gate GREEN** |
| `backend/market_lab_v741.py` | Current Engine result + operator line context | enriches `market_lab_v741`; BO5 returns `LAB_SET1_ONLY` | status/note, no synthetic full-match BO5 lab | runs before prediction integrity | separate owner; keep fail-closed |
| `backend/serve_props.py` | result + historical serve-prop evidence | enriches `serve_props_v72`; BO5 `ready=false` | `bo5_full_match_not_supported` | runs before prediction integrity | separate owner; keep fail-closed |
| `backend/api_quota.py` | central quota state + API operation | begin/check state; workflow fails on guard violation | quota guard command result | before `backend/update.py` | no BO5 overlap |
| `tests/test_prediction_ledger_selection_shadow.py` | Prediction Ledger selection SHADOW contract | pytest pass/fail only | test assertion | late Update guard | SHADOW isolation; no runtime owner rewrite |
| `tests/test_prediction_ledger_settlement_shadow.py` | Prediction Ledger settlement SHADOW contract | pytest pass/fail only | test assertion | late Update guard | SHADOW isolation; no runtime owner rewrite |
| Symphony/Superbet exact-offer test packs | exact operator context + Symphony/PLAYABLE artifacts | pytest pass/fail only | test assertion | late Update guards | enforcement only; model probability remains upstream-owned |

## 5. Duplicate invocation is not duplicate ownership

Repeated execution in different CI surfaces is allowed when the same owner is intentionally revalidated at a **different mutation boundary**. Repeated aliases with no intervening relevant mutation are not separate owners and are dead CI duplication.

### Phase-2 confirmed legacy presentation-owner collision

Five historical commands ? `scripts/verify_v84d1.py`, `scripts/verify_v84d2.py`, `scripts/verify_v84e11.py`, `scripts/verify_v853_runtime_ui.py`, and `scripts/verify_v87_decision_center.py` ? are compatibility aliases that do nothing except import and execute `scripts/verify_ui.py::main()`. `verify_ui.py` itself runs `tests/ui_static_smoke.mjs` and never writes published data.

On the phase-2 base all five aliases were active workflow commands. In `update-and-pages.yml`, multiple aliases ran consecutively after the first presentation check with no frontend/data mutation between them. The step named `Global Match Time Guard v8.4E1.1` did **not** execute the actual match-time owner; the actual specific owner is `tests/match_time_smoke.mjs`, already executed by `ui-smoke.yml`.

Local ownership cleanup:

- `update-and-pages.yml` has one pre-projection `Canonical UI presentation guard` calling `scripts/verify_ui.py` directly.
- Decision Center guard steps keep their specific `tests/decision_center_smoke.mjs` (plus audit-consistency smoke in Update) and no longer re-run the generic UI alias.
- historical Dynamic Weights UI/View aliases are removed from active Update execution because both were the same generic UI smoke, not Dynamic Weights-specific owners.
- `ui-smoke.yml` intentionally keeps canonical UI validation at distinct payload mutation boundaries: post-prune and post-compaction; its initial UI smoke also runs the real `tests/match_time_smoke.mjs`.
- compatibility wrapper files remain available for external/legacy command compatibility but are no longer active guard owners in these workflows.

RED proof on unmodified phase-2 base: all five legacy aliases were active (`RED_BASE_COUNT=5`). A dedicated ownership contract now fails if any alias is reintroduced as an active workflow owner.

## 6. Phase-3 semantic closeout

- Full named-step classification covers all active `guard|validat` workflow steps. The two direct `backend/player_dna_market_walk_forward.py` executions were producers that write SHADOW evidence (`player_dna_dynamic_market_walk_forward.json` / phase-7 evidence), not validators. Their workflow names are changed to `Build dynamic lean market walk-forward evidence...`; execution, training math and outputs are unchanged.
- All **52** active inline-Python guard/validation blocks are read-only with respect to repository/published artifacts: no `write_text`, `write_bytes`, unlink/rename/copy/move or `git push` mutation channel was found.
- `Symphony final PLAYABLE publication Guard` and Superbet `Runtime sanity guard` read generated artifacts and assert producer contracts only; they do not rewrite PLAYABLE/operator data.
- Historical `verify_v84*` / `v85*` guard scripts are read-only verifier entrypoints. Repeated execution of the same verifier in multiple CI surfaces is enforcement at multiple boundaries, not a second owner.
- `Central API Quota Guard` is the intentional stateful exception: `backend/api_quota.py begin` owns `data/cache/api_quota_v83b.json`, `frontend/data/api_quota_v83b.json` and quota metadata consumed through the same canonical quota module by update/history/PBP. It does not own model probability or betting output.
- `Checkout orchestration guard` is workflow orchestration, not a producer of application/model artifacts.

Regression evidence: phase-3 focused semantic/inventory/docs/walk-forward pack **24/24 GREEN**; full local repository suite **1349/1349 GREEN** with 755 warnings and zero failures/errors. PR #424 exact-head CodeQL, Delivery/Security, LOGIC-01..04, UI Health, Player DNA SHADOW and Point Tape all completed SUCCESS; Point Tape had 79 GREEN steps and Player DNA 31/31 GREEN on the PR head. PR #424 merged as `2b81e589e3d9f78db31d7f41b2959f091fc4bc1c`. Post-merge Delivery/Security and UI Health are GREEN; final Player DNA SHADOW completed SUCCESS 34/34 and published `e17e4c4a...`. Subsequent Update/Neuron/Superbet commits advanced only generated `frontend/data/**` to `a329444d...`; Runtime Private and Fast frontend deploy on that head are SUCCESS. No further semantic collision is proven.

## 7. Complete active invocation inventory

Every row below is keyed as `workflow :: step`; YAML line and guard-order are evidence from the audit base, not a stable API.

| # | Workflow :: step | YAML line | Guard order in workflow | Canonical owner / entrypoint |
| ---: | --- | ---: | ---: | --- |
| 1 | `context-engine-shadow.yml :: Validate SHADOW context contract and evidence` | 51 | 1 | `.github/workflows/context-engine-shadow.yml (inline step)` |
| 2 | `existing-history-source-inventory.yml :: Validate zero-network audit contract` | 60 | 1 | `.github/workflows/existing-history-source-inventory.yml (inline step)` |
| 3 | `history-freshness-counterfactual.yml :: Validate audit contract and evidence` | 52 | 1 | `.github/workflows/history-freshness-counterfactual.yml (inline step)` |
| 4 | `neuron-shadow.yml :: Hard isolation guard` | 54 | 1 | `backend/neuron.py` |
| 5 | `pbp-global-history-calibration.yml :: Validate audit contract` | 65 | 1 | `.github/workflows/pbp-global-history-calibration.yml (inline step)` |
| 6 | `pbp-history-schema-audit.yml :: Validate audit contract` | 67 | 1 | `.github/workflows/pbp-history-schema-audit.yml (inline step)` |
| 7 | `pbp-player-summary-audit.yml :: Validate zero-network fail-closed contract` | 62 | 1 | `.github/workflows/pbp-player-summary-audit.yml (inline step)` |
| 8 | `pbp-short-history-supply-audit.yml :: Validate audit contract` | 56 | 1 | `.github/workflows/pbp-short-history-supply-audit.yml (inline step)` |
| 9 | `pbp-tml-dedup-audit.yml :: Validate audit contract` | 60 | 1 | `.github/workflows/pbp-tml-dedup-audit.yml (inline step)` |
| 10 | `player-dna-service-split-depth-audit.yml :: Guard diagnostic isolation` | 47 | 1 | `.github/workflows/player-dna-service-split-depth-audit.yml (inline step)` |
| 11 | `player-dna-shadow-refresh.yml :: Player DNA canonical guards` | 138 | 1 | `backend/atomic_point_transition.py`<br>`backend/canonical_point_event.py`<br>`backend/player_dna_point_dataset.py`<br>`backend/player_dna_match_context.py`<br>`backend/player_dna_shadow_profiles.py`<br>`backend/player_dna_profile_readiness.py`<br>`backend/history_coverage_audit.py`<br>`backend/snapshot_digest.py`<br>`backend/player_dna_service_split_source_readiness.py`<br>`backend/player_dna_pbp_service_split_readiness.py`<br>`backend/player_dna_match_state_readiness.py`<br>`backend/player_dna_matchup_readiness_audit.py`<br>`backend/player_dna_recent_form_challenger.py`<br>`backend/player_dna_player_state_shadow.py`<br>`backend/readiness_engine_shadow.py`<br>`backend/player_dna_point_scorer.py`<br>`backend/player_dna_point_probability_engine.py`<br>`backend/player_dna_current_shadow.py`<br>`backend/player_dna_current_dynamic_shadow.py`<br>`backend/player_dna_tennis_simulator.py`<br>`backend/player_dna_tennis_state_engine.py`<br>`backend/player_dna_market_backtest.py`<br>`backend/player_dna_market_walk_forward.py`<br>`backend/player_dna_hold_calibration.py`<br>`backend/player_dna_hold_walk_forward.py`<br>`backend/player_dna_prospective_validation.py`<br>`tests/test_atomic_point_transition.py`<br>`tests/test_canonical_point_event.py`<br>`tests/test_player_dna_point_dataset.py`<br>`tests/test_player_dna_match_context.py`<br>`tests/test_player_dna_shadow_profiles.py`<br>`tests/test_player_dna_profile_readiness.py`<br>`tests/test_player_dna_point_scorer.py`<br>`tests/test_player_dna_point_probability_engine.py`<br>`tests/test_player_dna_current_shadow.py`<br>`tests/test_player_dna_current_dynamic_shadow.py`<br>`tests/test_player_dna_tennis_simulator.py`<br>`tests/test_player_dna_tennis_state_engine.py`<br>`tests/test_player_dna_market_backtest.py`<br>`tests/test_player_dna_market_walk_forward.py`<br>`tests/test_player_dna_hold_calibration.py`<br>`tests/test_player_dna_hold_walk_forward.py`<br>`tests/test_player_dna_prospective_validation.py`<br>`tests/test_history_coverage_audit_v949.py`<br>`tests/test_player_dna_service_split_source_readiness.py`<br>`tests/test_player_dna_pbp_service_split_readiness.py`<br>`tests/test_player_dna_match_state_readiness.py`<br>`tests/test_player_dna_matchup_readiness_audit.py`<br>`tests/test_player_dna_recent_form_challenger.py`<br>`tests/test_readiness_engine_shadow.py`<br>`tests/test_readiness_observability_delivery_contract.py`<br>`tests/test_player_identity.py` |
| 12 | `player-dna-shadow-refresh.yml :: Guard LOGIC-08 exact-snapshot readiness delivery` | 203 | 2 | `.github/workflows/player-dna-shadow-refresh.yml (inline step)` |
| 13 | `player-dna-shadow-refresh.yml :: Hard isolation + learning guard` | 309 | 3 | `backend/player_dna_tennis_simulator.py`<br>`backend/player_dna_market_walk_forward.py` |
| 14 | `point-tape-audit.yml :: Point tape + atomic validator + Player DNA identity/context tests` | 127 | 1 | `tests/test_point_tape_schema.py`<br>`tests/test_point_transition_audit.py`<br>`tests/test_atomic_point_transition.py`<br>`tests/test_canonical_point_event.py`<br>`tests/test_player_dna_point_dataset.py`<br>`tests/test_player_dna_match_metadata_audit.py`<br>`tests/test_player_dna_match_context.py`<br>`tests/test_player_dna_context_time_audit.py`<br>`tests/test_player_dna_ordering_authority_audit.py`<br>`tests/test_player_dna_profile_readiness.py`<br>`tests/test_player_dna_service_split_source_readiness.py`<br>`tests/test_player_dna_pbp_service_split_readiness.py`<br>`tests/test_player_dna_match_state_readiness.py`<br>`tests/test_player_dna_match_state_profiles.py`<br>`tests/test_player_dna_match_state_challenger.py`<br>`tests/test_player_dna_shadow_profiles.py`<br>`tests/test_player_dna_phase13_performance.py`<br>`tests/test_player_dna_phase14_lifecycle.py`<br>`tests/test_player_dna_matchup_readiness_audit.py`<br>`tests/test_player_dna_matchup_challenger.py`<br>`tests/test_player_dna_matchup_engine.py`<br>`tests/test_player_dna_point_probability_engine.py`<br>`tests/test_player_dna_opponent_context_audit.py`<br>`tests/test_player_dna_opponent_adjustment_audit.py`<br>`tests/test_player_dna_pressure_challenger.py`<br>`tests/test_player_dna_tiebreak_challenger.py`<br>`tests/test_player_dna_recent_form_challenger.py`<br>`tests/test_readiness_engine_shadow.py`<br>`tests/test_player_dna_point_scorer.py`<br>`tests/test_player_dna_current_shadow.py`<br>`tests/test_player_dna_current_dynamic_shadow.py`<br>`tests/test_player_dna_tennis_simulator.py`<br>`tests/test_player_dna_tennis_state_engine.py`<br>`tests/test_player_dna_market_backtest.py`<br>`tests/test_player_dna_market_walk_forward.py`<br>`tests/test_player_dna_hold_calibration.py`<br>`tests/test_player_dna_hold_walk_forward.py`<br>`tests/test_player_dna_prospective_validation.py`<br>`tests/test_player_identity.py` |
| 15 | `point-tape-audit.yml :: Guard service-split source audit isolation` | 157 | 2 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 16 | `point-tape-audit.yml :: Guard PBP-native service-split audit isolation` | 262 | 3 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 17 | `point-tape-audit.yml :: Guard comeback + BO5 stamina readiness isolation` | 344 | 4 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 18 | `point-tape-audit.yml :: Guard comeback + BO5 match-state profile isolation` | 433 | 5 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 19 | `point-tape-audit.yml :: Guard comeback + BO5 challenger isolation` | 542 | 6 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 20 | `point-tape-audit.yml :: Guard canonical Player DNA service-split profiles` | 643 | 7 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 21 | `point-tape-audit.yml :: Guard Phase-3 matchup readiness isolation` | 708 | 8 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 22 | `point-tape-audit.yml :: Guard Player DNA opponent audit isolation` | 824 | 9 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 23 | `point-tape-audit.yml :: Guard opponent-strength challenger isolation` | 872 | 10 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 24 | `point-tape-audit.yml :: Guard pressure challenger isolation` | 933 | 11 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 25 | `point-tape-audit.yml :: Guard tiebreak-profile challenger isolation` | 1074 | 12 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 26 | `point-tape-audit.yml :: Guard recent-form L5 challenger isolation` | 1165 | 13 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 27 | `point-tape-audit.yml :: Guard LOGIC-08 semantic readiness isolation` | 1267 | 14 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 28 | `point-tape-audit.yml :: Guard small-sample shrinkage challenger isolation` | 1342 | 15 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 29 | `point-tape-audit.yml :: Guard Phase-3 matchup challenger isolation` | 1477 | 16 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 30 | `point-tape-audit.yml :: Guard Phase-3 canonical matchup closure` | 1574 | 17 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 31 | `point-tape-audit.yml :: Guard Phase-4 canonical point probability closure` | 1711 | 18 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 32 | `point-tape-audit.yml :: Guard Phase-5 legal tennis state engine closure` | 1856 | 19 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 33 | `point-tape-audit.yml :: Guard Phase-6 exact DP plus Monte Carlo closure` | 1928 | 20 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 34 | `point-tape-audit.yml :: Guard Phase-7 calibration + walk-forward closure` | 2005 | 21 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 35 | `point-tape-audit.yml :: Guard Phase-9 Player DNA shared-state closure` | 2145 | 22 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 36 | `point-tape-audit.yml :: Guard Phase-10 Bet Builder dependency closure` | 2238 | 23 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 37 | `point-tape-audit.yml :: Guard Phase-12 master regression closure` | 2512 | 24 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 38 | `point-tape-audit.yml :: Guard Phase-13 observational performance closure` | 2583 | 25 | `.github/workflows/point-tape-audit.yml (inline step)` |
| 39 | `point-tape-audit.yml :: Guard Phase-14 safe lifecycle closure` | 2723 | 26 | `backend/player_dna_phase14_lifecycle.py` |
| 40 | `population-priors-audit.yml :: Validate audit contract and evidence` | 51 | 1 | `.github/workflows/population-priors-audit.yml (inline step)` |
| 41 | `ranking-provenance-audit.yml :: Validate audit contract and evidence` | 53 | 1 | `.github/workflows/ranking-provenance-audit.yml (inline step)` |
| 42 | `shadow-promotion-audit.yml :: Unit guard` | 25 | 1 | `tests/test_shadow_promotion_gate_v942.py` |
| 43 | `shadow-promotion-audit.yml :: Isolation guard` | 29 | 2 | `.github/workflows/shadow-promotion-audit.yml (inline step)` |
| 44 | `superbet-market-refresh.yml :: Validate orchestration guard on PR` | 94 | 1 | `tests/test_superbet_refresh_guard.py` |
| 45 | `superbet-market-refresh.yml :: Syntax guard` | 113 | 2 | `backend/superbet_market_context.py`<br>`backend/superbet_direct.py`<br>`backend/superbet_market_core.py`<br>`backend/superbet_market_mapping.py`<br>`backend/superbet_market_audit.py`<br>`backend/superbet_fixture_matching.py`<br>`backend/superbet_line_coverage.py`<br>`backend/superbet_playable.py`<br>`backend/market_lab_v741.py`<br>`backend/player_intelligence_v85.py`<br>`backend/player_model_shadow_v89.py`<br>`backend/ensemble_player_learning_v891.py`<br>`backend/surface_elo_integration_v893.py`<br>`backend/shadow_signal_center_v894.py`<br>`backend/symphony2_learning.py`<br>`backend/symphony2_state.py`<br>`backend/symphony2_engine.py`<br>`backend/symphony2_tracker.py`<br>`scripts/verify_superbet_market_semantics.py` |
| 46 | `superbet-market-refresh.yml :: Zero-request coverage, fixture matching and Symphony 2 guards` | 135 | 3 | `tests/test_canonical_superbet_runtime.py`<br>`tests/test_superbet_direct.py`<br>`tests/test_superbet_direct_context_fallback.py`<br>`tests/test_superbet_fixture_discovery_separation.py`<br>`tests/test_superbet_fixture_matching_v927.py`<br>`tests/test_superbet_line_coverage_v922.py`<br>`tests/test_superbet_line_coverage_v924.py`<br>`tests/test_superbet_market_v923.py`<br>`tests/test_superbet_market_v924.py`<br>`tests/test_symphony2_learning.py`<br>`tests/test_symphony2_state.py`<br>`tests/test_symphony2_tracker.py`<br>`tests/test_symphony2_exact_operator_line_gate.py`<br>`tests/test_symphony2_ui.py`<br>`tests/test_canonical_playable_frontend.py`<br>`tests/test_playable_ui_v917.py`<br>`tests/test_playable_freshness_pipeline_v928.py` |
| 47 | `superbet-market-refresh.yml :: Runtime sanity guard` | 167 | 4 | `.github/workflows/superbet-market-refresh.yml (inline step)` |
| 48 | `superbet-market-watchdog.yml :: Validate watchdog safety contract` | 39 | 1 | `.github/workflows/superbet-market-watchdog.yml (inline step)` |
| 49 | `superbet-market-watchdog.yml :: Checkout orchestration guard` | 67 | 2 | `.github/workflows/superbet-market-watchdog.yml (inline step)` |
| 50 | `tennis-data-stale-run-guard.yml :: Validate stale-guard safety contract` | 25 | 1 | `.github/workflows/tennis-data-stale-run-guard.yml (inline step)` |
| 51 | `tml-2024-blocker-audit.yml :: Validate audit-only contract` | 67 | 1 | `.github/workflows/tml-2024-blocker-audit.yml (inline step)` |
| 52 | `tml-2024-candidate-lock.yml :: Validate audit-only contract` | 87 | 1 | `.github/workflows/tml-2024-candidate-lock.yml (inline step)` |
| 53 | `tml-2024-history-preview.yml :: Validate preview-only contract` | 66 | 1 | `.github/workflows/tml-2024-history-preview.yml (inline step)` |
| 54 | `tml-2024-integration-readiness-audit.yml :: Validate fail-closed contract` | 66 | 1 | `.github/workflows/tml-2024-integration-readiness-audit.yml (inline step)` |
| 55 | `tml-2024-integration-safety-gate.yml :: Validate audit-only contract` | 66 | 1 | `.github/workflows/tml-2024-integration-safety-gate.yml (inline step)` |
| 56 | `tml-2024-runtime-equivalence-audit.yml :: Validate audit-only contract` | 78 | 1 | `.github/workflows/tml-2024-runtime-equivalence-audit.yml (inline step)` |
| 57 | `tml-freshness-preview.yml :: Validate preview contract` | 59 | 1 | `.github/workflows/tml-freshness-preview.yml (inline step)` |
| 58 | `tml-internal-id-alias-audit.yml :: Validate fail-closed contract` | 65 | 1 | `.github/workflows/tml-internal-id-alias-audit.yml (inline step)` |
| 59 | `ui-smoke.yml :: Player Model Shadow Guard v8.9` | 79 | 1 | `scripts/verify_v89_player_model_shadow.py` |
| 60 | `ui-smoke.yml :: Ensemble + Player Learning Guard v8.9.1` | 83 | 2 | `scripts/verify_v891_ensemble_player_learning.py` |
| 61 | `ui-smoke.yml :: Surface Elo Guard v8.9.3` | 87 | 3 | `scripts/verify_v893_surface_elo_integration.py` |
| 62 | `ui-smoke.yml :: SHADOW experiment trend guard` | 91 | 4 | `scripts/verify_v895_shadow_experiment_trends.py` |
| 63 | `ui-smoke.yml :: Shadow Signal Center Guard v8.9.4` | 95 | 5 | `scripts/verify_v894_shadow_signal_center.py` |
| 64 | `ui-smoke.yml :: Full App Coherence Guard v8.9.2` | 99 | 6 | `scripts/verify_v892_full_app_coherence.py` |
| 65 | `ui-smoke.yml :: Post-prune UI presentation guard` | 107 | 7 | `scripts/verify_ui.py` |
| 66 | `ui-smoke.yml :: Match Decision Center Guard v8.7` | 111 | 8 | `tests/decision_center_smoke.mjs` |
| 67 | `ui-smoke.yml :: Post-compaction UI presentation guard` | 127 | 9 | `scripts/verify_ui.py` |
| 68 | `ui-smoke.yml :: Model Trend Monitor Guard v8.4E2` | 131 | 10 | `scripts/verify_v84e2.py` |
| 69 | `update-and-pages.yml :: Central API Quota Guard` | 63 | 1 | `backend/api_quota.py` |
| 70 | `update-and-pages.yml :: Shadow Signal Center Guard v8.9.4` | 191 | 2 | `scripts/verify_v894_shadow_signal_center.py` |
| 71 | `update-and-pages.yml :: Surface Elo Guard v8.9.3` | 193 | 3 | `scripts/verify_v893_surface_elo_integration.py` |
| 72 | `update-and-pages.yml :: Ensemble + Player Learning Guard v8.9.1` | 195 | 4 | `scripts/verify_v891_ensemble_player_learning.py` |
| 73 | `update-and-pages.yml :: Player Model Shadow Guard v8.9` | 197 | 5 | `scripts/verify_v89_player_model_shadow.py` |
| 74 | `update-and-pages.yml :: Player Intelligence Guard v8.5` | 199 | 6 | `scripts/verify_v85.py` |
| 75 | `update-and-pages.yml :: AutoLearn Integration Guard v8.4A` | 201 | 7 | `scripts/verify_v84a.py` |
| 76 | `update-and-pages.yml :: AutoLearn Hotfix Guard v8.4A.1` | 203 | 8 | `scripts/verify_v84a1.py` |
| 77 | `update-and-pages.yml :: Quality Lock Guard v8.5.2` | 205 | 9 | `scripts/verify_v852_quality_lock.py` |
| 78 | `update-and-pages.yml :: Canonical UI presentation guard` | 207 | 10 | `scripts/verify_ui.py` |
| 79 | `update-and-pages.yml :: Match Decision Center Guard v8.7` | 209 | 11 | `tests/decision_center_smoke.mjs`<br>`tests/audit_consistency_smoke.mjs` |
| 80 | `update-and-pages.yml :: Accuracy Shadow Guard v8.6` | 213 | 12 | `scripts/verify_v86_accuracy_shadow.py` |
| 81 | `update-and-pages.yml :: AutoLearn Calibration Guard v8.4A.2` | 215 | 13 | `scripts/verify_v84a2.py` |
| 82 | `update-and-pages.yml :: Logic & Stability Guard v8.4B` | 217 | 14 | `scripts/verify_v84b.py` |
| 83 | `update-and-pages.yml :: Model Telemetry Guard v8.4C` | 219 | 15 | `scripts/verify_v84c.py` |
| 84 | `update-and-pages.yml :: Dynamic Weights Guard v8.4D` | 221 | 16 | `scripts/verify_v84d.py` |
| 85 | `update-and-pages.yml :: Signal Mapping Bridge Guard v8.4D.4` | 223 | 17 | `scripts/verify_v84d4.py` |
| 86 | `update-and-pages.yml :: Game-State Tracking Guard v8.4E1` | 225 | 18 | `scripts/verify_v84e1.py` |
| 87 | `update-and-pages.yml :: Model Trend Monitor Guard v8.4E2` | 227 | 19 | `scripts/verify_v84e2.py` |
| 88 | `update-and-pages.yml :: Superbet exact-offer projection Guard` | 233 | 20 | `tests/test_superbet_market_v91.py`<br>`tests/test_superbet_market_v913.py`<br>`tests/test_superbet_market_v923.py`<br>`tests/test_superbet_market_v924.py`<br>`tests/test_superbet_playable_v912.py`<br>`tests/test_superbet_line_coverage_v922.py`<br>`tests/test_superbet_line_coverage_v924.py` |
| 89 | `update-and-pages.yml :: Prediction ledger downstream SHADOW join Guard` | 241 | 21 | `tests/test_prediction_ledger_selection_shadow.py` |
| 90 | `update-and-pages.yml :: Prediction ledger settlement SHADOW Guard` | 245 | 22 | `tests/test_prediction_ledger_settlement_shadow.py` |
| 91 | `update-and-pages.yml :: Symphony 2.0 Guard` | 247 | 23 | `tests/test_symphony2_learning.py`<br>`tests/test_symphony2_state.py`<br>`tests/test_symphony2_tracker.py`<br>`tests/test_symphony2_exact_operator_line_gate.py`<br>`tests/test_canonical_playable_frontend.py`<br>`tests/test_playable_ui_v917.py` |
| 92 | `update-and-pages.yml :: Symphony final PLAYABLE publication Guard` | 249 | 24 | `.github/workflows/update-and-pages.yml (inline step)` |
## 8. Audit interpretation

The inventory is complete for **named workflow guard/validation invocations** on the current audit base and contains exactly the active invocation set enforced by `tests/test_guard_ownership_audit_contract.py`. It does not claim that every ordinary test/assertion anywhere in the repository is a guard. Phase-3 contract tests freeze this exact inventory and the read-only semantics above. LOGIC-10 is closed by PR #424 plus post-merge closeout evidence; future changes belong to their canonical owner/program phase, not a reopened guard audit unless a new proven collision appears.
