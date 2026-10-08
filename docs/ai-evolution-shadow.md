# Tenis AI Self Evolution: autonomous SHADOW phase 1

The independent daily GitHub Actions workflow automatically searches for
convex mixtures of Current, CatBoost and TabPFN frozen probabilities.
It NEVER alters any production probability, model, settlement, Symphony,
PLAYABLE, Player DNA, iNeed or actual bookmaker execution path.

Inputs: exact-byte-restored immutable prediction ledger and canonical
settlement history. Canonical exact-match settlement ownership is reused.
Only unique prematch SHADOW predictions with all three probabilities and
exact binary settlements enter. N/D, void, ambiguous, unfinished and
future-settled rows are excluded, not guessed.

Data is split by complete UTC fixture days: train (60%), validation (20%),
holdout (20%). Training labels must have settled before validation begins,
and validation labels before holdout begins. Mutated probability mixtures
are searched on train, chosen on validation; the holdout is observed only.
Brier scores weight each independent fixture equally. Insufficient
evidence is explicitly reported as INSUFFICIENT_EVIDENCE.

Schedule: 03:17 UTC daily; manual workflow dispatch is also supported.
Run report is a 30-day GitHub Actions artifact, not a published UI file.
There is NO automatic production promotion and NO actual betting.

Without frozen exact bookmaker odds there are no meaningful EV/ROI claims.
Even holdout Brier improvement does not prove profitability. A later phase
requires exact historical price snapshots and prospective operator-specific
evaluation before risk-related strategy comparison.
