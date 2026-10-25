# Neuron learning integrity — 2026-10-25

Scope: owner-authorized repair following the learning audit. Neuron remains
SHADOW_RESEARCH. No change to Model mathematics, hyperparameters, date split,
other models, PLAYABLE, iNeed or promotion rules. Base main:
`d099d9ca41aca89a83410b181e9901b49f9e4a5d`.

## Observed failures

- Run `40168596395` on 25 October scored with existing weights; training was
  skipped. Successful scoring is not evidence of another learning step.
- Published weights/metrics still came from 22 October, 08:56 UTC: 26,062
  usable matches, 41,670 TRAIN rows, 5,140 VAL rows and 5,314 TEST rows.
  Mirrored rows represent 2,657 independent test matches. Test accuracy was
  0.64395935 vs Elo 0.61234475; Brier 0.21659698 vs 0.22849038; log loss
  0.62173110 vs 0.64791689. ECE was worse than Elo (0.02599476 vs 0.01546696).
- Seven published versions on 5, 6, 8, 12, 15, 19 and 22 October had changed
  weights. All 7,095 parameters differed between 19 and 22 October. This is
  deterministic full retraining from the original seed, not online weight updates.
- Run `39919786105`, job `120303997723`, trained on 23 October at 07:53:33 UTC
  and passed quality: accuracy 0.6441808747 vs 0.6108228317; Brier 0.2166512355
  vs 0.2285280807. Publication failed three rebases on neuron_current.json.
  This candidate did not become the published model; no artifact preserved it.
- Quality rejection was enforced only in PR validation. Scheduled/main training
  could overwrite the last model even with a failed gate.
- Current scoring used the final loaded history without an as-of cutoff.
  Regression reproduces a later result affecting an earlier snapshot. Dates in
  a snapshot alone do not prove that a specific real prediction leaked.
- Missing player history produced 50/50 instead of NO_SCORE. Started fixtures
  were scored. No immutable Neuron forecast ledger supported prospective results.

## Canonical repair

`backend/neuron.py` now applies the existing completed-match hygiene and an
exclusive UTC-day cutoff. Source dates are recorded as tourney_date; no intraday
ordering is invented. Model, split, metrics, performance and sigmoid ASTs were
compared with base and remain unchanged. Input hygiene changes training data,
so metrics before/after repair are not a same-cohort improvement estimate.

Every candidate is archived with its exact feature arrays/split masks, dataset
hash, effective model hash, source hash and split boundaries. Only passing
candidates replace active weights and metrics. The workflow enforces the gate
on every training event and retains evidence after failure for 60 days.

The canonical publication step now builds a normal fast-forward commit on fresh
main using a temporary Git index. It replaces the removed JSON-rebase loop,
preserves other owners' data, merges immutable Neuron evidence and blocks a
concurrent source change/newer model/newer scoring snapshot.

Scoring records pre-match Neuron and Elo probabilities together with exact
fixture identity, timestamp, model hash, feature values and source hash in
monthly repository partitions. Repeated scoring cannot overwrite a frozen
prediction. Evaluation consumes canonical exact terminal evidence through the
existing shared settlement functions. Ambiguous identity, unproven times or
missing provenance remain N/D. No historical forecasts are backfilled.
The capture clock is sampled after computation and ledger loading; fixtures
starting during processing are rejected. A delayed-clock regression first
reproduced a falsely pre-match row, then passed after this boundary repair.

Overall reporting counts the earliest forecast per fixture once, with separate
per-model cohorts. Training history, scoring time and prospective results are
separate in the existing admin view. Successful main-core completion also
wakes scoring/evaluation; the Monday/Thursday training cron is unchanged.

## Isolated real-data preflight (not a production result)

At 20:16:48 UTC, all 11 sources were freshly downloaded. Candidate
`neuron-0f44db1dec6200299ba252b052afffaf9e948385eed387d6ed4e332f4fdcd9c9`
passed all quality checks. The dataset SHA was
`3d0f2aabc9c279b10fca64646105375a4799e319af21b0ec986ab3455736eafd`.

| Evidence | Value |
|---|---:|
| Raw matches | 26,195 |
| Removed by canonical completion hygiene | 1,043 |
| Excluded same-day/future records | 26 |
| Usable distinct matches | 25,124 |
| TRAIN matches, through 2026-06-25 | 20,009 |
| VAL matches, 2026-06-26–2026-08-23 | 2,458 |
| TEST matches, 2026-08-24–2026-10-24 | 2,657 |
| Epochs / best epoch | 17 / 5 |
| Test accuracy Neuron / Elo | 0.65035755 / 0.61272111 |
| Test Brier Neuron / Elo | 0.21669280 / 0.22823344 |
| Test log loss Neuron / Elo | 0.62237078 / 0.64737168 |
| Test ECE Neuron / Elo | 0.01370010 / 0.00879323 |

The conservative common unseen cohort against the legacy 22 October model has
only 17 matches: both accuracy 0.52941176, candidate Brier 0.26488136 vs previous
0.25883344. This does **not** demonstrate superiority over the previous version.
Legacy artifacts lack the old validation boundary, so this comparison uses the
old artifact date conservatively. New models record the real boundary.

Isolated scoring captured 55 forecasts, rejected 49 started fixtures and 14
fixtures without player history. Zero prospective results had settled; live
accuracy and Brier correctly remained missing. These test forecasts were not
copied into the repository ledger or represented as deployed evidence.

New recent matches currently enter the historical TEST/state features, not
automatically weight fitting. The preserved chronological split determines when
data enter TRAIN; a scoring refresh changes neither weights nor training time.
Separate TRAIN/VAL/TEST hashes make this distinction explicit on later runs:
growing only TEST cannot become "new training inputs". The UI separately labels
the last weight-fitting, calibration and test dates instead of calling the last
date of the whole dataset the end of data used to fit weights.

## Validation and rollout

Four regression reproductions failed before repair: future state, unknown
players, started fixtures and replacement by a rejected candidate. Targeted
tests cover those failures, evidence immutability, exact settlement, missing
metrics, concurrent Git writes and source/model conflicts. The live checkpoint
records full-suite, CI, merge and runtime verification as each completes.

Local full regression on pinned requirements: **1802 passed in 57.65s**, with
published-data isolation intact. Static and runtime UI smoke passed. Existing
source-line registry and PWA-cache assertions were updated for the changed UI;
their readiness/data-freshness contracts remain intact.

No claim of profitable betting, statistical superiority or SHADOW-to-PROD
readiness follows from these results.

## Observed main rollout

PR #557 merged after all nine workflows passed, at source merge
`2536ba6d8d63fc4fa81059d22e4fa93338cdbd0e`. Final PR head was
`c62ef88c123c7cb26e1f1e4f72342b264d963fc0`; fresh main still equalled the
validated base at merge. Remote full regression: 1802 passed in 51.64s.

Main run `40231944423`, neuron job `121285345032`, completed actual training,
quality gating, scoring, evaluation and publication. Training finished at
2026-10-25 20:43:10 UTC; forecast capture at 20:43:31 UTC. Publication succeeded
on attempt one as `30510e7276e8885e463960c57fc586507be4f5c3`.

The independently recomputed published model identity is
`neuron-1a18adcb227b8ec8775f5078472fa9eb74c6ce088b629cdf83e1822ead12f91c`.
Compared with the actually published 22 October model, all 7,095 parameters
changed, with maximum absolute difference 0.28548117.
It matches weights, metrics and forecasts, and the stored source hash matches
merged backend/neuron.py. Main test metrics reproduce the preflight values in
the table above. Binary hashes can differ across numerical environments even
with equivalent metrics; a hash change alone is not a quality-improvement claim.
Here preflight/main used the same dataset hash and differed by at most
6.38e-16 in 5,811 of 7,095 parameters, with identical reported test metrics.

The real monthly ledger contains 53 unique immutable pre-match predictions,
with model-training time <= capture time < scheduled start. At publication,
51 already-started fixtures and 14 without player history were NO_SCORE. All
53 predictions were pending, zero settled; prospective metrics remained N/D.

Artifact `12613153312` (`neuron-evidence-40231944423-1`, 4,751,212 bytes) preserves
the actual candidate, metrics, dataset and forecasts. No preflight forecasts
were used as main evidence.

Pages job `121285882980` completed successfully at 20:47 UTC. Live public sw.js,
app.js and neuron-data-bridge.js returned HTTP 200 with byte hashes exactly
matching merged source. Runtime-source artifact `12613711829` and Pages artifact
`12613467147` preserve the delivered source/payload.

Private delivery run `40232399304`, publish job `121286718159`, checked out
`30510e7276e8885e463960c57fc586507be4f5c3` and reported
`RUNTIME_PRIVATE_PUBLISH_OK`: three files and three uploaded objects in the
Neuron layer at 20:48:18 UTC, generation
`54d71172-dc66-44a5-be81-445883f48f06`.


## Post-publication fixture correction

The parallel core rebuild `40231944352` stopped in its test step (job
`121286378460`): the synthetic scoring test froze time at 10:00 on 25 October,
then loaded the actual newly trained model timestamped 20:43. The strict guard
correctly raised INVALID_FROZEN_MODEL_TIME. This is a moving test-fixture date
failure; the actual published forecasts passed the independent chronology check.

PR #558 pins a prior training timestamp only on the temporary fixture copy.
Runtime chronology checks and published weights/metadata remain unchanged.
The failure was reproduced locally on actual main weights, followed by a full
**1802 passed in 58.93s** after the test-only correction. Core recovery uses a
rerun of the failed jobs from `40231944352` after merge; consult its latest
attempt and PR #558 for the observed execution result.


The fresh report also moved its `test` group to field 21, after the presenter's
existing 20-field page boundary. Browser job `121288120218` failed its old
first-page assumption. The browser test now exercises the existing "Pokaż
kolejne" control before opening historical metrics, preserving the nested
metric assertions and bounded runtime rendering. The GitHub browser gate
validates this against the actual expanded report.
