# App reliability and research evidence — 2026-10-16

Owner approved all six proposed improvements after the Solar rollout. Base:
`553d5c294cf94f5aa6d3a4c6ac94f285f495106c`. No model/training/probability,
PLAYABLE decision, settlement, iNeed economic or real-betting changes.

## Reproduction and ownership

The browser reproduced a failed index refresh removing the only visible match
(actual 0, expected 1). `app.js::loadData` is the canonical owner. The repair
validates the next index before replacing existing state, bounds requests and
retries, preserves the last view with an explicit freshness warning and discards
late responses from a previous account. A successful empty index still clears
matches. Online/foreground events recheck old data; source dates are never
replaced with browser-check times.

`presentation-data.js::availability` retains the exact existing boolean decision
and adds reasons for missing/exact/stale/unverified offers, source mismatch and
final composition rejection. Failed-refresh prices are labeled as the last read,
not as a current verified offer. No new probability or second PLAYABLE gate.

Admin views now select one match and reuse its existing content-addressed detail
bundle. They do not fetch the 20 MB full result file. All reports remain reachable.
The index adds only existing Direct and AutoLearn source timestamps.

## Private Self Evolution evidence

Research and memory stay owned by `backend/self_evolution_shadow.py`, unchanged.
The existing private publisher gains a research provenance layer, using the same
OIDC identity, atomic activation and retention. The new projection validates a
successful schedule/manual main run from the exact repository/workflow, report
and memory identity/digest/time, bounded fields and explicit false authority flags.
Only scalar metrics and retained decisions are published, exclusively as tier C.
The transport forces this report through the existing authenticated admin reader,
even in public data mode; there is no public fallback or repository report commit.

The source report from actual run `38879366541` was downloaded read-only and
projected locally: memory cycle 8, three research tracks, 2084 eligible samples,
114 historical holdout fixtures, zero completed trials in retained history.
The ALL prospective trial contains 112 fixtures across 7 days and is still
collecting until `2026-10-23T11:30:44.647119+00:00`. These are research evidence,
not production promotion, economic profit or a future-performance guarantee.
The projected document is 3349 bytes. Raw artifacts and private weights remain
outside the frontend repository and public Pages delivery.

## Preferences and status

`ui_preferences` stores owner-scoped keys with RLS, active-profile checks and no
anonymous grants. Per-key writes preserve unrelated changes from other devices.
Pending local writes win over an older server value until acknowledged. Remote
favourite removals persist; account epochs isolate late asynchronous responses.
Existing device favourites migrate only if the server has no corresponding key.

The shared status displays original dates and bounded connection recovery.
Optional connection notices default off. They work while the app is running;
background push delivery is not claimed. Browser permission is requested only
from a user's explicit settings-button action.

## Verification and rollout

Baseline browser regression failed; repaired Chromium user/moderator/admin flows
pass, including failed refresh preservation, valid empty feeds, report selection,
private research metrics and 320/412 px report layout. Preference tests cover
pending merges, remote removals, per-key writes and a delayed-account response.
Seventeen projection tests and the existing private publisher/UI/readiness tests
pass (48 focused Python tests). A direct account change followed by a failed
index read clears the previous account immediately, confirmed in Chromium.
The existing lossless delivery test passes all 273 PLAYABLE
comparisons. Final full-suite, schema/RLS, CI and production verification are
recorded in the execution checkpoint as they complete.

Deployment order: additive migration, compatible publisher Edge, green PR merge,
Pages/core private delivery and automatic research projection from the last trusted
run. Publisher-code pushes may publish only the single bounded tier-C research
report; prepare and activate both reject every production layer for push events.
Scheduled research completions keep using the existing workflow-run OIDC contract.
No raw report, draft coupon, user credential or training dataset is made public.
