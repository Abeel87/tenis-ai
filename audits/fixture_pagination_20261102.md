# Fixture pagination and source freshness — 2026-11-02

Baseline: `4634eb203388aba8bc7407e86ff01e6e346c79e3`.

## Incident evidence

The user confirmed that the Live Tennis subscription had expired and was renewed
to 10,000 requests/day. The last pre-renewal report declared 100/day. The existing
8% fixture allocation therefore allowed only eight page requests for the day.

Run [41310350896](https://github.com/Abeel87/tenis-ai/actions/runs/41310350896),
job `124859528305`, started with seven fixture calls spent and ended with eight.
At 13:19 UTC on November 1 it returned 198 singles from the first page, with only
60 still eligible after stale filtering. Earlier run `41294766610` had published
453 visible fixtures. The resulting 60 rows all had start times between 13:00 and
14:15 UTC on November 1; no future fixture remained by the evening.

Run [41358825315](https://github.com/Abeel87/tenis-ai/actions/runs/41358825315),
job `125004833421`, skipped retrieval (`fixture_quota_safe_skip`) but rewrote
`meta.updated_at` to 22:50 UTC. Successful downstream publication could thus look
fresh despite retaining the truncated catalogue. History-backfill HTTP 403 was
also observed, but is not evidence that the skipped fixture request returned 403.

## Canonical repair

`backend/update.py::fetch_fixtures` must reach the declared total or a terminal
short page with no contradictory total before returning a publishable list.
Exhausted budgets and contradictory short/empty pages return a degraded skip.
The existing caller retains results/history unchanged, preserves source time,
records the attempt separately and exposes its reason. Genuine complete empty
catalogues remain valid. No catalogue union, guessed fixture or stale-price reuse
is introduced.

The quota policy needs no numerical override after renewal. Its existing live
usage read changes the fixture daily cap from 8 to 800 and retains spent calls.
The 12-call run cap, request pacing, reserves and other consumer budgets remain.

## Validation and rollout

Seventeen isolated cases cover partial and complete pagination, exact page
boundaries, missing totals, contradictory pages, genuine empty results, preserved
source timestamps/data and subscription renewal with retained usage. Eleven
failed before the repair. Full-suite, CI and production status are recorded in
the live execution checkpoint; no deployment is claimed by this source audit.
