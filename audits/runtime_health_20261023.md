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
8. **Fresh market hid stale core data.** At main
   `e1fff88670c58d1881286a33110441124e074201`, successful market publication at
   06:10 UTC still carried core `meta.updated_at` of
   `2026-10-23T01:36:27.145408+00:00`. The existing watchdog only selected market
   refresh, so it could not recover a missed hourly core build. The same canonical
   guard now reads source time and selects the existing full workflow at 120
   minutes, representing two missed hourly cycles. Missing, invalid, naive and
   future source timestamps also request a real rebuild. Existing active-run
   exclusion and five-minute post-core grace take precedence. Fresh core retains
   the lightweight 40-minute market path. No timestamp is rewritten to claim
   freshness, no new timer or API quota is added, and PR validation is network-free.
   Reproduction before repair: **10 failed, 36 passed**; focused guard suite after
   repair: **46 passed**. This follow-up uses branch `fix/core-freshness-20261023`
   while the complete Player DNA validation of PR #553 runs unchanged.
   Full regression on an isolated exact tracked snapshot plus the proposed diff:
   **1768 passed in 58.34s**, including published-data immutability. Initial local
   attempts exposed setup problems (unrestored archived JSON, transient workspace
   files and missing Git metadata in the isolated archive); none was suppressed
   in the final complete run.

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

A separate read-only audit on refreshed main `e1fff88670c58d1881286a33110441124e074201`
compared 1153 already-terminal legs with exact canonical result evidence and
found zero conflicts. This is a bounded evidence comparison, not validation of
legs whose exact archived source is unavailable.

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

## Primary merge verification

PR #553 final head `cea7c0a97a3bf40b6075905270e0f4c64e63437c` passed all 13
workflows. Full Player DNA run `39911763155` / job `120276627702` completed all
historical, current-card, walk-forward, calibration and isolation stages. UI
health ran 1755 tests (65.49s); Chromium E2E and both dependency audits passed.

While CI ran, main published market `e84f77b8f53ffadee7bef77c9a0d26d13acb3f0f`
and readiness `f4ebee9a9c56c61e874145d1740073dcda933041`. No code or training
source changed. The 148 fixture IDs/order and all DNA scoring target inputs
remained identical; result changes were confined to operator/PLAYABLE projection
fields. Fresh combined-tree regression passed 1755 tests (59.39s), plus runtime
smoke and 444 exact PLAYABLE projection comparisons. The later readiness change
only updated source digest/report time; its combined tree passed 1755 tests
(60.14s). Additional local Chromium launch was unavailable because the browser
download was truncated; the independent GitHub Chromium E2E check was green.

Merged as `88363e42f54553be70afb74cc3ce7a2b87abe9aa` at 07:44 UTC. GitHub's
actual merged tree `543b70c3b62b54a95849d4ffad5747c7e2db05d8` exactly equals
the locally validated fresh-main integration, preserving both bot publications.
The normal core rollout is `39919786176`; post-merge delivery is still pending.
The core-freshness follow-up is rebased onto this actual merge.

A pre-deploy comparison baseline freezes 5661 Symphony entries, including 1583
terminal compositions and 5087 terminal legs. Post-deploy verification must
compare original forecast fields and every existing terminal result/provenance,
not merely count newly resolved predictions.

## Core-freshness merge and deployed guard

PR #554 final head `8c405dfad23651f7b4d196c63d175f4fa24d72a9` passed all nine
workflows, including browser E2E, security audits and 1768 tests in CI (77.40s).
Fresh-main verification included the intervening Neuron publication and complete
core publication `01fb14df9ab08ccdce4f1e097f305e24c0841182`: exact history/ledger
restore, delivery rebuild and 1768 tests passed (60.53s). Merged at 08:00 UTC as
`d54bf3107bd39f14d2da84ec3a42cf038e488962`; actual tree
`08e547d1392d4f5f8148173bde4e39abb50ed71e` exactly matches the validated merge.

The deployed watchdog run `39921668377`, job `120308109183`, succeeded at
08:02 UTC with `dispatch=false`, `reason=refresh_already_active`, target
`superbet-market-refresh.yml` and `core_stale_minutes=120`. Existing core/market
work occupied the shared concurrency lane, so this is a verified duplicate-work
suppression, not a claim that a stale-core rebuild was dispatched in production.
The stale-core selection and 120-minute boundary have positive/negative tests.
Normal core rollout `39919786176` started after the earlier pre-merge scheduled
core completed; producer and consumer publication checks are still pending.

## Post-merge browser-test ordering defect

Delivery/security run `39921668382`, job `120308109030`, passed exact source
projection (336 PLAYABLE comparisons) but failed at line 46 of
`tests/delivery_browser_e2e.mjs`: the first card existed inside a closed
tournament, and the test waited for visibility before opening it. The selected
fixture moved outside the initially expanded tournament in the new core data.
`frontend/app.js:matchList` deliberately preserves each tournament's expansion
state through filtering; no product behavior defect is demonstrated here.

The canonical browser test now starts the scenario from an explicitly collapsed
group, clicks its summary, and confirms the card is visible **before** testing
failed/successful refresh retention. The existing visibility, filtering, scroll,
auth and outage assertions remain. No waits are suppressed or lengthened, and no
UI/model behavior is changed. Local Chromium downloads remained truncated, so
the completed production CI log is the reproduction evidence; the corrected
test must pass real Chromium CI before merge.
