# Tenis AI — LOGIC-05 closeout checkpoint

Status: **CLOSED / VERIFIED / SHADOW-ONLY**

Date: 2026-09-18

## Closed work

- LOGIC-05 — Opponent Strength Engine completed in PR #394.
- Final PR head: `b1afeb1e0a146a258ccd870b69c91959d7644819`.
- Merge commit: `bd01b3c9bc1685a36c8762a2fd3ea64871fdc801`.
- Canonical owner remains `backend/player_dna_opponent_adjustment_audit.py`.
- No parallel opponent-strength runtime path was introduced.
- Mode remains SHADOW/evaluation only; no PROD/runtime activation.

## Final CI / artifact evidence

Final head `b1afeb1e0a146a258ccd870b69c91959d7644819`:

- Point Tape Schema Audit `35332644368` = GREEN, full 73/73 steps.
- CodeQL `35332644381` = GREEN.
- Delivery and security checks `35332644382` = GREEN.
- Tenis AI UI & Project Health `35332644376` = GREEN.
- Artifact `player-dna-point-foundation`: ID `10544291045`.
- Artifact size: `43429487` bytes.
- Artifact digest: `sha256:b14fc5a27f6bee00b388190170c87151c6af97f80fd1b116647637ba1b0468e3`.

Post-merge verification:

- Update tennis data and deploy Pages run `35338430244` = GREEN, including full pytest, quota guard, settlement, SHADOW modules, Surface Elo, Symphony 2.0, final PLAYABLE publication guard, final regression v9.3.3, data publish and `deploy_pages`.
- Subsequent bot drift through `ec0e213fa353967fce0c081c99edc35e114ccb05` is data-only (`frontend/data/*.json`) and does not alter LOGIC-05 code/tests/workflow/checklist contracts.

## Final LOGIC-05 evidence

Chronological split:

- cutoff: `2026-09-07T11:10:00+00:00`
- train matches: `7011`
- holdout matches: `1757`
- same-timestamp split: `false`
- all enriched points: `1009547`
- train points after support gate: `259798`
- holdout points after support gate: `128145`
- holdout matches after support gate: `1031`

Common holdout metrics:

- profile + rank: Brier `0.240961`, match-equal Brier `0.241367`, log-loss `0.674867`
- profile + rank + opponent strength: Brier `0.240946`, match-equal Brier `0.241352`, log-loss `0.674838`
- lean-stateful: Brier `0.232505`, match-equal Brier `0.232615`, log-loss `0.653647`
- lean-stateful + opponent strength: Brier `0.232486`, match-equal Brier `0.232592`, log-loss `0.653609`
- gains vs lean-stateful: Brier `+0.000019`, match-equal Brier `+0.000023`, log-loss `+0.000038`

Walk-forward:

- completed folds: `3`
- positive folds vs lean-stateful: `3/3`
- robust positive vs lean-stateful: `true`
- mean gains vs lean-stateful: Brier `+0.000017`, match-equal Brier `+0.000020`, log-loss `+0.000033`
- same-timestamp groups not split: `true`
- test windows disjoint: `true`

Leakage / provenance contracts confirmed:

- opponent strength comes from opponent's own strict pre-match snapshot;
- target match never enters its own history;
- same-timestamp matches never count as prior;
- source row order cannot override scheduled-time order;
- stable provider player IDs only;
- future match results are not used;
- residual bin boundaries are TRAIN-only;
- ranking is benchmark-only; no manual rank multiplier;
- event level is unavailable and is not inferred from tour/name;
- surface and tour missingness are not guessed.

Hard policy flags in final artifact:

- `network_calls=0`
- `production_influence=false`
- `runtime_scoring_enabled=false`
- `training_join_enabled=false`
- `canonical_profile_write_enabled=false`
- `symphony2_influence=false`
- `superbet_playable_influence=false`
- `auto_promote=false`
- `candidate_may_replace_reference=false`
- `promotion_gate=false`

## Active next task — LOGIC-06

`LOGIC-06 — Opponent-Adjusted Serve / Return / Hold / Break`

Goal: raw rates such as 72% serve must not be treated as equivalent when produced against materially different opponent strength.

Canonical implementation direction:

1. Re-check fresh `main`, open PRs and CI before writing.
2. Extend `backend/player_dna_opponent_adjustment_audit.py` in place; do not create a parallel engine.
3. Add SHADOW expected serve vs opponent return strength.
4. Add serve residual.
5. Add SHADOW expected return vs opponent serve strength.
6. Add return residual.
7. Add hold residual and break residual.
8. Preserve explicit surface split.
9. Add explicit sample/support/confidence metadata; support must never become a strength proxy.
10. Expectations must use strict-prior player/opponent profiles only; target observed metrics may be used only as evaluation labels.
11. Compare raw vs adjusted on one common chronological holdout plus walk-forward.
12. Extend `tests/test_player_dna_opponent_adjustment_audit.py` with same-time, future-leakage, target-label isolation, surface, pooled-count expectation and support/confidence tests.
13. Reuse the existing Point Tape workflow/owner; no new workflow unless technically unavoidable.
14. No runtime wiring, no Player DNA PROD overwrite, no probability/weight/threshold/training/Symphony/Neuron/PLAYABLE/iNeed$ changes.
15. PR -> artifact -> all required CI GREEN -> fresh-main check -> merge -> post-merge verification -> checkpoint to LOGIC-07.

## Hard bans carried forward

Do not redo LOGIC-00/01/02/03/04/05 without new evidence that a completed result is invalid. Do not change model math, probability, thresholds, weights, training, Current, Player DNA PROD, Surface Elo, Symphony, current Neuron, PLAYABLE, settlement, SHADOW/PROD mode or iNeed$ calculations without separate explicit authorization. No fuzzy matching, manual aliases, provider-ID namespace guessing or real-money betting execution.
