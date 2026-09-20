# LOGIC-09 — Learning Integrity / Prediction Ledger

Status: **PHASE-0 AUDIT CONTRACT / MERGED / ZERO BEHAVIOR CHANGE**

Audited base: `57d5e9c037ae0cc4570e4c68f84a8006478de876`.

Merge evidence: PR #414 final head `8532212b0a3292112dc33ae6ec052d766b5058d7` merged as `d589b7204098fe285fe30ec66fbd6be96ee3f5a8`; exact-head required CI GREEN.

This document records the current prediction populations before any learning or telemetry migration. It does not authorize changes to model math, probability, thresholds, weights, training, PLAYABLE, settlement, Symphony, Neuron or iNeed$.

## Executive finding

The current history is not one neutral prediction ledger. It contains several separately frozen populations with different selection rules. Direct model comparisons are therefore valid only on an explicit common intersection.

Observed on the audited base:

- history entries: **1425**, settled/void entries: **1367**;
- legacy green settled signals: **5397**;
- AutoLearn settled signals: **12162**;
- Current scores: **12162**, CatBoost scores: **12162**, TabPFN scores: **1532**;
- exact Current + CatBoost + TabPFN intersection: **1532**;
- AutoLearn pre-match capture proof: **12162 / 12162** settled signals came from entries captured before `scheduled_time`;
- `generator_selected=true`: **2350** settled AutoLearn signals;
- exact PLAYABLE history exists as a separate layer; **31159** settled PLAYABLE signals were observed;
- Symphony history contains **2276** frozen compositions, **605** settled and **1649** pending at audit time.

## Current source-of-truth matrix

| Population | Canonical owner | Frozen/as-of evidence | Prediction identity | Selection state | Settlement path | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| Legacy green history | `backend/history_tracker.py` | `captured_at`; archive refuses fixtures inside the pre-match cutoff | match key + signal key | only signals with score `>= GREEN_THRESHOLD` | `settle_history()` | **SELECTED**, not ALL |
| AutoLearn frozen signals | `backend/autolearn_v84.py::_capture_frozen` | `autolearn_captured_at`; requires future fixture | match key + candidate key | model scores + `generator_selected` | result copied/settled in `history.json` | model-available / generator-selected |
| Model telemetry | `backend/model_telemetry_v84c.py` | consumes already frozen AutoLearn rows | frozen match/candidate identity | per-model score availability; selected metrics use threshold 65 | consumes settled hit/miss | derived diagnostics, not a ledger owner |
| TabPFN challenger | `backend/autolearn_v84.py` + `backend/tabpfn_challenger_v84.py` | cached challenger predictions keyed by match + candidate; current run capped | same AutoLearn candidate key | score exists only where challenger prediction exists | via AutoLearn frozen row | sparse model-available subset |
| Exact PLAYABLE | `backend/superbet_playable.py::freeze_playable_history` | `playable_captured_at_v912` | exact signal signature + match key | operator verified / playable | dedicated PLAYABLE history layer | **PLAYABLE** |
| Symphony selection | `backend/symphony2_tracker.py::capture` | `captured_at`, scheduled time, exact operator-verification bit | composition id + selection ids | recommended final composition | exact selection-signature join to PLAYABLE settlement | **SELECTED / SYMPHONY** |
| iNeed$ SHADOW selection | `backend/ineed_money.py` + Edge state | `placement_snapshot.timestamp`, stable fingerprint | match id + exact signal signature fingerprint | qualified/proposed/open SHADOW bet | placement snapshot + canonical match result | **SELECTED / INEED** |

`backend/prediction_integrity_v78a.py` is an output-probability guard, not a prediction-ledger owner. It validates current `results.json`; it does not establish a neutral historical population.

## Proven selection bias / incomparable samples

Current and CatBoost have settled scores for all **12162** audited AutoLearn rows, while TabPFN has only **1532**. Any direct Current/CatBoost/TabPFN ranking that uses each model's own available rows compares different samples.

TabPFN sparsity is structural: `TABPFN_CURRENT_CAP = 300` and current candidates are ranked before challenger inference; cached predictions are reused only for unchanged match/candidate keys. Missing TabPFN scores are intentionally not invented.

Telemetry also has two scopes per model: all available rows (`n`) and score-threshold-selected rows (`selected_n`). Generator metrics are another selected population. These labels must not be presented as equivalent populations.

The AutoLearn frozen signal does not carry PLAYABLE, Symphony-selection or iNeed$-selection fields. Those states exist in separate owners and must be joined by exact identity and valid pre-match chronology if used together.

## Required population semantics

- **ALL** = every supported prediction frozen before any display/quality/operator/Symphony/iNeed$ selection gate. The current legacy green archive cannot represent ALL because it starts after a score threshold.
- **PLAYABLE** = exact operator-supported predictions frozen by the PLAYABLE owner. It is a subset/projection, never a synonym for ALL.
- **SELECTED** = an explicitly named downstream selection population. `GENERATOR_SELECTED`, `SYMPHONY_SELECTED` and `INEED_SELECTED` remain separate labels; they must not collapse into one generic selected metric.

Accuracy, Brier, log-loss and calibration must always identify the population they summarize.

## Minimal future frozen-ledger contract

A future canonical ledger row must be immutable after match start and must contain enough provenance to reproduce population membership without recomputing model decisions later:

- schema/version and stable prediction id;
- canonical `match_key` plus canonical candidate/signal identity;
- `scheduled_time`, `captured_at` and strict proof `captured_at < scheduled_time`;
- producer/model owner and exact model version;
- frozen score/probability plus its semantics/unit; a score must not be silently relabeled probability;
- feature/context snapshot reference or digest and provenance;
- readiness snapshot/reference available at prediction time;
- explicit selection facts: model available, generator selected, exact PLAYABLE, Symphony selected/composition id, iNeed$ selected/placement reference;
- explicit population tags, never inferred later from a threshold that may have changed;
- settlement key/signature, result, settlement source and `settled_at` once known.

No future ledger row may use post-start data to fill a missing pre-match prediction.

## Common-test-set invariant

A direct Current/CatBoost/TabPFN comparison is permitted only on the exact intersection of settled prediction identities where all compared model scores were frozen for the same candidate and the same pre-match snapshot semantics. If a model score is missing, that row may remain in that model's coverage diagnostics but must not enter a comparative winner/ranking metric.

Positive case: same frozen match/candidate identity, valid pre-match timestamp, settled hit/miss, all compared scores present.

Negative cases: different candidate identity, missing challenger score, capture at/after start, unresolved settlement, or different population label. These rows must fail closed from the common comparison set.

## Phase-0 decision

Selection bias and population mismatch are proven. This audit **does not change behavior**. The next implementation phase must first add a prospective SHADOW-only frozen ledger capable of capturing ALL supported predictions before downstream selection, while preserving every existing learning/PROD path until common-set evidence is available. Existing historical layers remain evidence sources; they are not retroactively rewritten into a fictitious ALL population.
