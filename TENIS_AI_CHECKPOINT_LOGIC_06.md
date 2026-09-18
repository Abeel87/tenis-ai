# Tenis AI — LOGIC-06 closeout checkpoint

Status: **CLOSED / VERIFIED / SHADOW-ONLY**

Date: 2026-09-18

## Closed work

- LOGIC-06 — Opponent-Adjusted Serve / Return / Hold / Break completed in PR #397.
- Final PR head: `8e64ecef4b92a749e6b1d33fbf2d286dd40d949d`.
- Merge commit: `c1d1328b38a9b71fc2b4b15f4dc5f34c86703200`.
- Canonical owner remains `backend/player_dna_opponent_adjustment_audit.py`; no parallel opponent-adjustment engine was introduced.
- Implementation remains SHADOW/evaluation-only and reuses the existing Point Tape workflow.
- No Player DNA PROD write, Current Engine change, probability/weight/threshold/training change, Symphony/Neuron/PLAYABLE/iNeed$ change, or runtime activation was introduced.

## Final CI / artifact evidence

Final head `8e64ecef4b92a749e6b1d33fbf2d286dd40d949d`:

- Point Tape Schema Audit `35346777493` (#388) = GREEN, full 73/73 steps.
- CodeQL `35346777508` = GREEN.
- Delivery and security checks `35346777367` = GREEN.
- Tenis AI UI & Project Health `35346777520` = GREEN.
- Artifact `player-dna-point-foundation`: ID `10550797498`.
- Artifact size: `42891198` bytes.
- Artifact digest: `sha256:c037879a043223f9ca7b02c7d5a41c28cee2db9a87dc26e2f6fad21fd197fc5e`.
- Artifact expired: `false` at final verification.

Post-merge verification on merge commit `c1d1328b38a9b71fc2b4b15f4dc5f34c86703200`:

- CodeQL `35353430855` = GREEN.
- Delivery and security checks `35353430840` = GREEN.
- Tenis AI UI & Project Health `35353430838` = GREEN, including full pytest and project guards.
- Update tennis data and deploy Pages `35353430836` (#800) = GREEN, including build steps 1–76, final full regression v9.3.3 and `deploy_pages`.
- Run #800 published `7f05291ecde4d3dc15b469b3b2c0f7c897722642` (`data: refresh tennis analysis`), whose direct parent is the LOGIC-06 merge commit.
- Drift `c1d1328b... -> 7f05291e...` is generated-data-only: only `frontend/data/*.json`; no backend code, tests, workflows or checkpoint contracts changed.

## Final LOGIC-06 evidence

Chronological split and common evaluation sample:

- cutoff: `2026-09-07T11:35:00+00:00`
- train matches: `7017`
- holdout matches: `1755`
- same-timestamp split: `false`
- all enriched points: `1010081`
- train points after support gate: `260671`
- holdout points after support gate: `127808`
- common holdout matches: `1029`

Raw baseline vs opponent-adjusted candidate on the same holdout:

- raw: Brier `0.232444`, match-equal Brier `0.232552`, log-loss `0.653519`
- adjusted: Brier `0.232397`, match-equal Brier `0.232521`, log-loss `0.653421`
- gains: Brier `+0.000047`, match-equal Brier `+0.000031`, log-loss `+0.000098`

Walk-forward:

- completed folds: `3`
- positive adjusted-vs-raw folds: `3/3`
- robust positive: `true`
- mean gains: Brier `+0.000044`, match-equal Brier `+0.000037`, log-loss `+0.000091`

Coverage / support evidence:

- target directions: `17544`
- overall all four expected components available: `11762`
- same-surface all four expected components available: `10618`
- paired matches: `8772`
- enriched rows with LOGIC-06 overall serve/return: `710474`
- enriched rows with overall hold/break: `708337`

## LOGIC-06 semantic and leakage contracts

- Expected serve uses only strict-prior player serve counts + opponent return counts.
- Expected return uses only strict-prior player return counts + opponent serve counts.
- Expected hold uses only strict-prior player hold/service-game counts + opponent break/return-game counts.
- Expected break uses only strict-prior player break/return-game counts + opponent hold/service-game counts.
- Count pooling only; no manually tuned opponent weights or rank multipliers.
- Overall and same-surface components are separate.
- Target point/game outcomes are evaluation labels only and never inputs to their own expectation.
- Raw and adjusted candidates use one common chronological test set.
- Support/confidence metadata is diagnostic only and is not a strength proxy or activation threshold.
- Opponent strength comes from the opponent's own strict pre-match snapshot.
- Target match never enters its own history.
- Same-timestamp matches never count as prior.
- Source row order cannot override scheduled-time order.
- Stable provider player IDs only.
- Future results are never used for earlier state.

Hard policy flags remained closed in final evidence:

- `network_calls=0`
- `production_influence=false`
- `runtime_scoring_enabled=false`
- `training_join_enabled=false`
- `canonical_profile_write_enabled=false`
- `player_dna_overwrite=false`
- `feature_activation=false`
- `symphony2_influence=false`
- `superbet_playable_influence=false`
- `auto_promote=false`
- `candidate_may_replace_reference=false`
- `promotion_gate=false`

Final signal: `OPPONENT_ADJUSTED_ROBUST_POSITIVE_SHADOW_SIGNAL`. This is evidence only; it does not authorize PROD promotion.

## Relevant recent-form evidence for LOGIC-07

The same final #388 artifact contains `player_dna_recent_form_challenger.json`. Its L5 challenger is **not robust enough for activation**:

- status: `RECENT_FORM_L5_NOT_ROBUST_ENOUGH`
- positive holdout: `false`
- robust walk-forward: `false`
- fresh confirmation required: `true`
- candidate/promotion flags: `false`
- split cutoff: `2026-09-07T11:35:00+00:00`
- train matches: `7017`; holdout matches: `1755`
- train L5-supported points: `112406`; holdout L5-supported points: `86384`
- lean reference: Brier `0.232173`, match-equal Brier `0.232419`, log-loss `0.652710`
- +L5: Brier `0.232175`, match-equal Brier `0.232419`, log-loss `0.652714`
- gains: Brier `-0.000002`, match-equal Brier `0.000000`, log-loss `-0.000004`
- positive walk-forward folds: `1/3`

Implication for LOGIC-07: L5 may be represented as descriptive Player State with provenance/support/uncertainty, but must not become a probability feature, weight or PROD activation from this evidence.

## Active next task — LOGIC-07 Player State

Goal: distinguish long-term Player DNA from current player state without modifying the PROD Current Engine.

Implementation direction:

1. Re-check fresh `main`, open PRs and CI before writing.
2. Create one canonical SHADOW owner: `backend/player_dna_player_state_shadow.py`; do not create parallel state engines or a new PROD path.
3. Use the stable-provider-ID timeline and strict-as-of primitives already owned by `backend/player_dna_shadow_profiles.py` for match ordering, contributions, rankings, overall/surface profiles and rolling history.
4. Reuse LOGIC-06 opponent-adjusted primitives from `backend/player_dna_opponent_adjustment_audit.py`; do not reimplement opponent-adjusted mathematics.
5. Treat `backend/player_dna_current_shadow.py`, `backend/player_dna_current_dynamic_shadow.py` and `backend/player_dna_recent_form_challenger.py` as reference/evidence sources, not additional production owners.
6. Do not use legacy `backend/player_trends.py` name-key L5/L10/L20 calculations as the canonical model-state source.
7. Build strict-prior descriptive state for: current-season level; previous-season baseline; season delta; ranking momentum; serve trend; return trend; opponent-adjusted performance trend; current-surface state; inactivity/gap evidence; matches-since-observed-gap; support/confidence/provenance.
8. LOGIC-01 tested freshness scenarios rather than selecting a magic recency cutoff. Do not invent a single new cutoff. For inactivity/matches-since-gap, preserve explicit scenario windows (30/60/90/180 days) until evidence chooses otherwise.
9. Recent-form L5 remains descriptive/non-robust with uncertainty; no probability activation.
10. Inactivity must never infer injury, medical condition or comeback cause.
11. Current Engine comparison is read-only/observational. Never recalculate, overwrite or alter Current Engine probability, weights, thresholds or training.
12. Keep all LOGIC-07 outputs SHADOW-only with hard no-runtime/no-write/no-promotion flags.
13. Add dedicated tests for strict-as-of ordering, same-time/future leakage, season isolation, surface isolation, rank provenance, gap semantics, opponent-adjusted reuse, recent-form non-activation and Current/PlayerDNA/PROD isolation.
14. Reuse the existing Point Tape owner/workflow where technically possible; do not add a parallel workflow unless unavoidable.
15. PR -> all required CI GREEN -> evidence/artifact -> fresh-main check -> merge -> post-merge verification -> checkpoint to LOGIC-08.

## Hard bans carried forward

Do not redo LOGIC-00/01/02/03/04/05/06 without new evidence that a completed result is invalid. Do not change model math, probability, thresholds, weights, training, Current Engine PROD, Player DNA PROD, Surface Elo, Symphony, current Neuron, PLAYABLE, settlement, SHADOW/PROD mode or iNeed$ calculations without separate explicit authorization. No fuzzy matching, manual aliases, provider-ID namespace guessing or real-money betting execution.
