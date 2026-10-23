# Runtime delivery and Symphony evidence repair — 2026-10-23

Authorized by the owner after the health review: fix the reported problems and
verify the result. Original snapshot: `202f757b6fb7659fcc56c19d755586c003f14ca7`.
Branch: `fix/runtime-health-20261023`. No forecast mathematics, training policy,
PLAYABLE rules, iNeed economics/scope, builder enablement or real betting change.

## Reproduced defects and canonical repairs

1. **Consumer delivery after watchdog recovery.** Successful market runs
   [39892633789](https://github.com/Abeel87/tenis-ai/actions/runs/39892633789)
   and [39909268429](https://github.com/Abeel87/tenis-ai/actions/runs/39909268429)
   were dispatched from a DNA-triggered watchdog. FAST Pages ran, but market
   `workflow_run` subscribers (iNeed, private delivery and DNA) did not appear.
   The second run was a controlled recovery using watchdog job `120215435548`.
   This matches GitHub's documented
   [three-level workflow_run limit](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run).
   The market owner now dispatches those existing consumers explicitly after
   successful publication; the old subscriptions are removed. DNA's existing
   fast-readiness path is exposed as a boolean dispatch input, default false.
   DNA also explicitly dispatches its private publication after non-stale
   successful work. PR runs cannot publish or dispatch. No second scheduler,
   external credentials or polling runner is introduced.
2. **Symphony unresolved labels and biased diagnostics.** `symphony2_tracker`
   only looked up legs selected in two other model layers and stopped updating
   all legs after the first loss. It now fills unresolved frozen legs from an
   unambiguous exact history fixture and delegates final-score semantics to
   `signal_settlement.settle_signal_live`. Exact archived operator labels remain
   usable; conflicting labels are not guessed. Identity, participant order,
   schedule, pre-match capture, terminal timestamp and source/version must agree.
   Original probabilities, diagnostics, terminal outcomes and timestamps stay
   frozen. Point checkpoints are never reconstructed from final scores.
3. **False prospective capture.** Capture at/after the scheduled start or without
   a timezone-aware start is rejected. Four existing non-pre-match captures are
   retained but cannot gain new settlement/calibration evidence.
4. **Calibration population.** Operational losses remain losses immediately.
   Joint calibration now requires every leg to be binary-resolved and genuine
   pre-match capture; void and unresolved legs and invalid probabilities are
   excluded explicitly. Coverage/exclusion counts accompany the diagnostic.
   There is no calibrated-probability rollout or promotion claim.
5. **Provider HTTP 410 loop.** `live_history_settle` rechecked deleted matches
   every two hours indefinitely. Persisted HTTP 410 now defers rechecking for
   seven days, with match/reason/retry time in meta. Later provider recovery is
   still possible. Predictions remain pending; no fabricated result or void.
   Retries still use the existing quota and persisted cache.
6. **Historical provenance.** New `history_tracker.settle_history` results record
   their actual source/version/time, as the live owner already does. Existing
   unsupported provenance is not fabricated or retroactively inferred.
7. **Security gate found vulnerable existing dependencies.** PR #553 dependency
   job `120274126890` reported 36 advisories in two pre-existing pins: certifi
   2026.7.22 (PYSEC-2026-4320) and Pillow 12.3.0. Update only those pins to the
   auditor's fixed releases, certifi 2026.10.19 and Pillow 13.0.0. Official release
   evidence: [certifi](https://github.com/certifi/python-certifi/releases/tag/2026.10.19)
   and [Pillow](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html).
   Keep the audit fail-closed; no suppressions or unrelated dependency PR merge.
   The updated lockfile passes `pip_audit` with no known vulnerabilities. The
   pinned environment loads the CA bundle and imports Requests/CatBoost; a
   Matplotlib PNG round-trip through Pillow also passes.
   Full regression with the fixed versions: **1755 passed in 66.72s**.

## Immutable local replay at the original SHA

Restored the exact published history chunks (2500 fixtures) and replayed the
canonical tracker in memory against 5659 frozen compositions. No source JSON
was written by the replay. Assertions verified unchanged input, probabilities,
dependency diagnostics and every pre-existing terminal result/timestamp.

| Evidence | Before | After |
|---|---:|---:|
| Pending compositions | 4076 | 2923 |
| Binary-resolved compositions | 1527 | 2579 |
| Operational composition accuracy | 52.98% | 59.33% |
| Binary-resolved legs | 4813 | 6507 |
| Compositions with unresolved legs | 4486 | 3214 |

1153 newly terminal compositions include 101 void compositions. There are 1855
new leg outcomes, including voids. Fully binary, pre-match calibration contains
2249 compositions: observed 66.518%, mean frozen joint probability 67.235%,
Brier 0.212842. These are coverage-limited retrospective diagnostics, **not** a
model improvement, prospective validation result, ROI or profitable strategy.

Unresolved cases include absent archived fixtures, changed schedules, missing
provenance and nonterminal matches. They are visible with reasons and remain
unresolved; exact identity/time requirements are not relaxed to improve coverage.

## Verification and limits

- Baseline focused pack: 59 passed. Added reproduction failed on missing leg
  settlement, terminal-loss backfill, chronology, conflict handling and 410 repeat
  requests before the implementation. The provenance and dispatch contracts also
  failed before their respective fixes.
- Focused implementation pack: 92 passed; readiness/orchestration pack: 51 passed.
- Static UI and real-data runtime smoke passed (148 fixtures / 119 Symphony
  matches). Four edited workflow YAML documents parse successfully.
- An initial full-suite attempt had three old trigger-string expectations and
  an isolation error caused by running the delivery builder concurrently. The
  assertions were migrated to the new single dispatch route. Sequential full
  regression: **1755 passed in 61.08s**. No production-data isolation rule is weakened.
- Fresh main advanced only generated data to
  `e1fff88670c58d1881286a33110441124e074201`; incorporated unchanged. Rebased
  full regression: **1755 passed in 60.46s**, isolation intact.
- PR #550 already merged on 2026-10-19 at `7abe4f618474caa1897243ddba60d5f63f4ec3c0`.
  The previous pending checkpoint is stale and superseded.
- Current source coverage remains 48/148 technically model-ready fixtures,
  with 85 fixtures missing one player's safe history. No audited source/identity
  evidence supports filling those gaps by guessing. Existing thresholds remain.
- All schedule workflows are active, but observed starts were hours apart.
  GitHub [documents schedule delays/drops](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
  The delivery fix does not promise exact cron timing; source times remain the
  freshness authority. GitHub status reported Actions operational at this review.

Final CI, merge and post-merge producer/private-delivery evidence are recorded
in the execution checkpoint when actually observed.
