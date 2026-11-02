# Neuron / Self Evolution readiness repair — 2026-11-02

Scope: authorized SHADOW data-coverage and evaluation repair. No model math,
training, weights, thresholds, settlement rules, betting or PROD promotion.
Base: `9a75e590114ce6458b4c83d10be33275ea7c802d`.
Machine-readable evidence: `shadow_learning_readiness_20261102.json`.

## Reproduction and observed impact

The current Neuron snapshot was generated at 03:00:29 UTC on 2026-11-02.
Its 425 fixtures had 132 scores, 289 missing-history refusals and 4 already-started
refusals. Replaying the old and repaired `current_features` functions on the same
10 cached source frames, canonical hygiene, exclusive 2026-11-02 cutoff and
snapshot clock gives 136 scores, 285 missing-history refusals and the same 4
already-started refusals. All three feature arrays for all 132 existing scored
fixtures are exactly equal (including NaNs). This is a local same-input replay,
not a post-deployment coverage claim.

Five player occurrences have one unique history key with the exact same complete
normalized name tokens in a different order. Four fixtures recover both players:
213790, 213879, 213874, 213332. The fifth still lacks its opponent's history.
Initials, partial names, spelling guesses and ambiguous keys remain rejected.
The new opt-in mode belongs to the existing canonical resolver; default behavior
for all other consumers is unchanged. JSON records exact names/keys, source
hashes, fixture SHA and retained match counts. Most missing players are genuinely
absent from the currently declared sources; this patch cannot supply that history.

The Neuron workflow did not restore the core TML history cache. It now restores
that same cache before training/scoring; the core workflow retains save ownership.
Existing source timestamps, due-refresh logic, empty-source diagnostics and model
quality gates stay intact. Actual cache-hit behavior still requires CI/live proof.

## Evaluation correction

The 111,019-row source ledger has zero frozen AutoLearn ensemble scores. Existing
three-model inputs cannot prove the actual dynamic ensemble output from the past.
AutoLearn now observes its existing computed ensemble result before display
rounding and selection, freezes it at the ledger's normal 12-decimal precision,
and timestamps capture after computation. Old immutable rows are never enriched.

The shared reader validates score/producer ownership, finite probability and
strict pre-match chronology. Neuron additionally requires exact fixture ID,
start time and winner selection, reports per-model common cohorts and exposes
pending reasons. Self Evolution reports candidate vs actual AutoLearn on the
same holdout/prospective rows, balanced per independent fixture. Its candidate
optimization, registration window and internal SHADOW champion policy are unchanged.
The comparison concerns AutoLearn PRE_SELECTION, not final betting decisions.

The existing Neuron ledger has 106 settled binary fixtures across versions and
32 for the active version. Its current-version Brier is 0.211445 versus Elo
0.204309; there is no demonstrated superiority from that sample. All 32 remain
N/D against AutoLearn because the actual frozen baseline is missing. Pending
schedule conflicts/missing/unterminated results remain pending, not invented
losses. No profitability or production-readiness claim follows from these repairs.

## Verification and delivery

New regression cases reproduced failures before implementation. Tests cover
exact identity/ambiguity, feature parity, cache ownership, actual dynamic-output
capture, unchanged decorated predictions, append-only legacy rows, strict
pre-match provenance, exact common fixtures, per-version cohorts, missing
baselines, prospective registration windows and bounded private UI projection.
The readiness consumer matrix is updated only for moved frontend line numbers.

Current test/PR/merge/deployment results and next steps are recorded in the
latest `TENIS_AI_EXECUTION_CHECKLIST.md` LIVE CHECKPOINT. Existing TML freshness
and locked-2024-source audits have external-source blockers in PR #568; these
contracts must not be weakened or relocked merely to make this change mergeable.
