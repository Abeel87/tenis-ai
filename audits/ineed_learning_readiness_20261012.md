# iNeed$, Self Evolution, Neuron — read-only audit 2026-10-12

Verified main: d796756e15528ba523a629bdf9b7314b61204cba.
Status: diagnosis complete; NO production or configuration changes.
Branch: audit/ineed-learning-readiness-20261012.

## iNeed$ experiment 3
Live Supabase read confirms ACTIVE, SHADOW, automatic_real_betting=false.
All 24 placements are match_winner: 9 WIN, 13 LOSS, 2 PENDING.
Settled stake 110.62 PLN; net profit -40.0559 PLN; remaining open stake 6.98 PLN.
Starting bankroll 200 PLN. Screenshot equity 159.94 PLN and drawdown 22.1% are consistent with recorded losses.
Across the 22 settled frozen placement snapshots:
- actual hit rate: 40.9091%
- mean raw model probability: 47.1318%
- mean final operator probability consumed by iNeed$: 84.7564%
- raw Brier: 0.2311866473; final Brier: 0.4273739564
- final-minus-raw inflation: 30.46 to 46.50 percentage points
- ZERO rows satisfy raw_p * observed_odds * 0.88 - 1 > 0.

This is a descriptive selected cohort, not an independent validation set or proof of future counterfactual profitability. Historical snapshots must not be rewritten.

Concrete frozen example: Alexander Donski vs Georgii Kravchenko, odds 2.22, stake 3.33, raw/calibrated 41.62%, final 72.08%, LOSS 5-7 2-6. Bobichon pending example: raw/calibrated 44.89%, final 84.35%, odds 2.42.

Canonical source: backend/symphony2_engine.py::_cohere_exclusive_probabilities divides each independently scored outcome by the pair's summed probabilities. backend/ineed_money.py correctly consumes operator_model_probability under its existing contract. backend/symphony2_learning.py calibration validation evaluates probabilities before this pair normalization. Therefore calibration evidence does not validate the final economic input.

Executed deterministic reproduction using the canonical function: winner pair [40%,10%] becomes [80%,20%]. Existing tests assert sum=100, not predictive calibration of the transformed probabilities.
The mathematical transformation is confirmed; deeper reasons for poorly coherent pair scores (feature parity, identity, selection-biased training) still require audit. Do not claim a specific deeper cause is established.

confidence=1 is learning_support/FULL_SUPPORT_ROWS capped at one, not a 100% chance or demonstrated calibration quality.
Risk settings already include CAUTION at 10%, DEFENSIVE at 20%, HALTED at 30% drawdown; increasing stakes is not a probability repair.

## Concrete proposed repair scope — needs explicit Symphony probability authorization
1. Preserve experiment 3 and every immutable settlement/placement.
2. Reproduce full paired pre-normalization/final inference on frozen historical exact offers; audit feature and player-side parity.
3. Repair the canonical Symphony probability owner, with chronological calibration/validation of the ACTUAL final output. Do not bypass it by rewriting probability in iNeed$.
4. Compare current and proposed probabilities on identical unseen match groups; include market-specific Brier, log-loss, calibration and economic evaluation only where frozen odds permit.
5. Require green regression/CI and explicit production promotion before altered probabilities affect existing consumers.
6. Keep real betting disabled. No Neuron/Self Evolution promotion is part of this change.
Simply deleting normalization, tuning thresholds to these 22 results, or replacing it with another unvalidated formula is NOT an approved repair.

## Self Evolution
Latest retrieved main runs: 37924098106 (Oct 9), 38046146528 (Oct 10), 38133968301 (Oct 11), all success.
Last report: 2026-10-11 11:01:07 UTC; 1635 eligible rows; 213 training, 63 validation, 62 holdout independent matches.
Holdout candidate Brier 0.200253205 vs Current 0.201213783: modest descriptive improvement.
match_winner research remains INSUFFICIENT_EVIDENCE (8 train / 8 validation / 5 holdout matches).
Exact frozen operator odds are not joined; economic_roi_evaluated=false, ineed_influence=false, auto_promote=false.
A successful cycle is not evidence of improved betting profit. Repeated holdout is explicitly descriptive rather than prospective.

## Neuron
Latest metrics generation: 2026-10-08 10:54:20 UTC.
25,467 usable source matches; 50,934 orientation rows. Test has 4,950 rows, NOT 4,950 independent matches.
Test accuracy 65.616% vs Elo 62.061%; Brier 0.215069 vs 0.225965; log-loss 0.618425 vs 0.642254.
Own quality_gate.passed=true; promotion_eligible=false; reason manual architecture and quality review required.
All production/PLAYABLE/Symphony/iNeed influence flags false.
Latest retrieved workflow 38191782589 Oct 12 01:24 UTC success. Hourly workflow scores existing model; retraining is separately scheduled Monday/Thursday or manual.
Ready as a SHADOW research model; NOT proven production-ready or economically profitable.

## Checkpoint
No model, thresholds, weights, training, settlement, bankroll, config or SHADOW/PROD gate changed.
No PR opened and no production verification claimed for a repair.
NEXT EXACT ACTION: obtain the separate Symphony probability authorization required by AGENTS.md section 6, then investigate/replay the paired inference boundary and implement only an evidence-backed canonical repair with the normal green-CI process.
