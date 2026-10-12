# Exact participant settlement repair — 2026-10-12

User authorization covers canonical settlement, auditable archived-label correction and Symphony retraining. No real betting, experiment reset, or historical iNeed ledger update.

## Root cause and minimal repair
`signal_settlement._key` preserved name order. The scorer treated `Sharipov, Marat` as different from the archived winner `Marat Sharipov`. In the original training rows, 1,161 comma-name match-winner selections had zero hits; 460 winner observations in the PLAYABLE history layers were incorrectly misses.

The canonical scorer now resolves a complete name against two distinct fixture participants by exact normalized token multiset. It never accepts a partial name or ambiguous match. All named settlement markets share the resolver; iNeed's existing compatibility adapter delegates to it. Its actual 22 settled experiment-3 outcomes were already correct and are not rewritten.

The existing archive reconciliation path repairs only previously resolved/unverifiable named selections whose full-name order differs from a uniquely resolved participant and whose corrected result is binary. Every change retains original selection, probability, capture time, final score and prior result/source in `settlement_corrections`. Void policies and unrelated/PBP evidence are preserved. Unknown old labels are not guessed; Symphony excludes unresolved participant identity from training.

This also recovers previously unverifiable handicap/player-total observations. Counts in the JSON are signal observations across layers, not independent matches. The original history remains in Git; each corrected row keeps provenance. No full historical artifact is committed manually: the existing core workflow reconciles, trains, verifies and publishes it atomically through its existing Git-safe chunk transport.

## Validation
- Nine new regression cases failed on original code; corrected identity, ambiguity, retirement and migration cases now pass.
- Full local regression: 1,661 passed (40.26 seconds); final telemetry/version additions also go through PR CI.
- `replay_name_settlement_repair.py` trains two identical algorithm/hyperparameter models using original vs corrected labels, exclusively from captures AND terminal labels before 2026-10-09 00:00 UTC. Calibration is also confined to this prefix.
- Evaluates 110 later independent fixture pairs (220 selections), no earlier fixture overlap. One incomplete/conflicting pair is excluded. Final probabilities are produced by the actual canonical pair-normalization function including runtime rounding.
- Final Brier improves from **0.29580448 to 0.26114730** and log loss from **0.87556561 to 0.72025156**. Corrected normalization also improves on corrected raw Brier **0.26365883**; it is therefore retained rather than replaced with an arbitrary formula.
- A constant 50/50 forecast has Brier 0.25 on these complementary pairs. The repaired model still does NOT demonstrate superiority to that baseline on this test. This is a verified correctness repair and retrospective improvement, not a profitable-model or production-promotion claim.

Reproduce with `python audits/replay_name_settlement_repair.py --history frontend/data/history.json --as-of 2026-10-09T00:00:00Z`. Exact original source SHA-256 and results are in `name_settlement_repair_evaluation_20261012.json`. The counterfactual uses the repaired identity eligibility in both models to isolate label corrections. Source prices are not used and no ROI is inferred.

## Deployment verification target
Green exact-head PR checks, fresh-main comparison, then merge. Normal core workflow must publish correction provenance and Symphony `learning_version=symphony2-learning-6`, with nonzero corrected-label training counts. Verify downstream iNeed runtime stays SHADOW and historical ledger is intact. No Neuron/Self Evolution activation accompanies this repair.
