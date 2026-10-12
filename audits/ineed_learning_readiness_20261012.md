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


## Follow-up after user's Symphony authorization — 2026-10-12

User explicitly authorized the Symphony probability repair. Further read-only reproduction found an UPSTREAM label defect, so normalization alone is not established as the root cause.

Canonical backend/signal_settlement.py::_key preserves token order. A completed match with p1="Jake Delaney", p2="Marat Sharipov", winner="Marat Sharipov" and pick="Sharipov, Marat" returns miss from settle_signal_live(). This is reproduced on unchanged main.
The iNeed settlement runner already has a separate input normalization adapter; the history path does not share that adaptation.

Fresh restored history: 2,500 entries; build_training_rows generated 3,041 match_winner rows:
- pick includes comma: 1,161 rows, ZERO target=1.
- pick has no comma: 1,880 rows, 1,072 target=1.
Read-only inspection of both frozen PLAYABLE history layers found 3,033 exact participant-resolvable match_winner observations and 8 unresolved names. Of the resolved observations, 460 stored miss labels match the recorded final winner after full name token permutation. Examples: Kachmazov, Alibek / Alibek Kachmazov; Zeitune, Maximo / Maximo Zeitune; De la Fuente, Santiago / Santiago De La Fuente. No fuzzy or surname-only matching was used.
These counts describe rows, not necessarily independent matches.
The malformed-name effect contaminates targets upstream of training; simply preserving raw output or tuning normalization would not repair the labels.

Live experiment-3 settled snapshots were independently checked against final winners: 22 checked, ZERO outcome mismatches. Its 9 wins / 13 losses and -40.0559 PLN are unchanged. The history defect must NOT be used as justification to rewrite its ledger or claim those 13 losses were wins.

Current model was reproduced locally with pinned dependencies: status ready, 61,022 train rows / 14,153 validation rows. This trains on unchanged historical labels and is diagnostic, not a deployable repair.

### Concrete expanded repair proposed
- Resolve exact full participant names at the canonical history settlement boundary, with unique p1/p2 matching and ambiguous/unknown identity fail-closed. No fuzzy matching and no changes to tennis winner/retirement/void rules.
- Add regressions for reordered names, multi-token names, same-token ambiguous participants and unrelated names.
- Prepare a deterministic versioned historical correction manifest showing prior label, corrected label and exact final evidence. Preserve original records/provenance and all iNeed placements/ledger. Do not silently recalculate experiment bankroll.
- Rebuild the Symphony training input from corrected labels, then evaluate actual final paired probabilities chronologically. Determine whether normalization itself still needs repair only using corrected data.
- Full regression and mandatory green CI before merge/deployment.

### Current authorization boundary and resume point
AGENTS.md section 6 separately protects settlement and history semantics. User's most recent approval answered the specific Symphony-probability request; it did not explicitly authorize changing archived settled labels. No such change has been performed.
Request the necessary extension for canonical history settlement repair and auditable historical label corrections. No Neuron or Self Evolution promotion, real betting, DB bankroll mutation, or model deployment occurred.
