# Superbet Direct discovery repair — 2026-10-16

## Reproduced failure

Baseline main: `18a78e75eebf583ec5fbaaf99eb322eef9df76de`.
The published 07:28 UTC Direct snapshot contained 144 app fixtures, 27 listing
URLs, three candidates and three resolved matches. These are Direct price
coverage counts, not all canonical operator contexts or PLAYABLE counts.

The browser's public tennis page currently loads `/v3/pl-PL/events` with
`sports=2&index=active-prematch`. Its event identity is `event_id`, while the
name, sport and schedule are inside `fixture.event_name`, `fixture.sport_id`
and `fixture.utc_date`. The old iNeed-only network parser expected a top-level
name and returned no candidates for this shape. Main Direct did not consume
listing network responses at all and jumped to the bottom of a virtualized DOM.

Six focused regression tests failed on baseline: current v3 discovery, source
identity validation, remembering IDs, never reusing stale prices, complete
per-fixture diagnostics and listing-outage seed recovery.

## Canonical repair

- `superbet_direct.py` owns shared incremental DOM + already-loaded public
  prematch tennis XHR discovery. iNeed imports the same owner; the duplicate
  implementation is removed. No authenticated endpoints or wagering actions.
- Explicit non-tennis records are excluded; concrete URL/event-ID disagreements
  cannot provide an incorrect identity. Listing data only discovers candidates;
  each candidate still passes existing exact event JSON + player/time/ambiguity
  verification and side orientation.
- The existing sidecar retains bounded, price-free identity bindings for current
  app fixtures. Every reuse requires a fresh event read and the same verification.
  Failed reads keep identity hints and diagnostics, never refreshed old prices.
- Each input fixture receives a reason code. Network/catalogue gaps, time/identity
  rejection, ambiguity, unsupported active markets and explicit budget deferral
  are distinguished. The arbitrary default 64-match slice is removed; at most
  512 unique event reads per refresh, at most two transport attempts per event.
  403/404/410/429, malformed payloads and long Retry-After are not retried.
- Per-event `observed_at` is recorded. The shared feed timestamp is refresh start,
  conservatively no later than any included fresh read. No old quote is copied.
- The existing delivery diagnostics and admin Superbet panel display source counts
  and per-match explanations. Models and PLAYABLE remain separate authorities.

## Read-only live evidence before deployment

A public browser capture yielded 167 prematch event identities. Against the same
144 app fixtures it produced 75 candidate matches. 76 distinct event JSON reads
completed without transport failures. Existing exact resolver accepted 73
matches and rejected two by `TIME_MISMATCH` (app IDs 204120 and 204651).
69 matches had no safe candidate in the observed catalogue; this is not proof
that Superbet has no offer. These are separate-time baseline/probe snapshots,
not a guaranteed production coverage ratio or a claim of 73 PLAYABLE matches.

## Validation and deployment

Focused final Direct/discovery/PWA suite: 47 passed. Earlier broader fixture/iNeed
suite: 75 passed. Static UI, runtime UI (real data and both readiness fixtures),
match-time and decision-center smoke passed. Full final-source local regression:
1682 passed in 136.90s. Remote full regression: 1682 passed in 42.57s.

PR #547 head `252bdb252fb458e137f8dd2abee5c880a255ea00` passed all 12 workflows
(15 successful checks, two intentional production-only skips), including mobile
browser job `116926938893`. It merged as
`ec908de4764b344db87297a35ca5131e5882db2b` against fresh unchanged main
`fcca685f8e236544c15f9354c08ae8a6ab0d92c5`.

Production Update/Pages run `38887707148` completed SUCCESS, including final
generated-data regression (1682 passed in 33.96s) and Pages deployment job
`116937787096`. It published data commit
`91aa93cde9009d149efa22159731f9380b95c877`.

The actual production snapshot, generated at `2026-10-16T10:37:56.264334+00:00`,
contains 84 app fixtures, 189 discovered event URLs (143 DOM and 144 XHR, with
overlap), 65 candidates, 62 exact verified matches and 66 unique event reads.
There were no fetch failures and no degraded discovery. One remembered identity
was revalidated. All fixtures have a reason: 62 OK, 19
`NOT_IN_DISCOVERED_CATALOGUE`, three `TIME_MISMATCH`. This is a different fixture
population from the predeployment probe; do not derive a before/after ratio or
claim that 62 fixtures are PLAYABLE.

Read-only public verification at 10:55 UTC confirms app.js and sw.js equal the
tested source bytes, the Direct feed equals its committed source and delivery
manifest digest, and diagnostics exactly project the source fields. All included
prices have fresh observation times; the 62 retained identity hints contain no
prices. The public source SHA descends from the reviewed merge. SHA-256 evidence:

- app.js: `a3ad731451169f6d99c4d3bd4a3504a761bcf4265f81b815689b2ae7d9cdfff9`
- sw.js: `99f514130c7f5ecccab172a04dbd718342aa595815e64f96dc77bbc658705247`
- Direct: `15fc00457d737ade732cfdac97afa06575ebc99022697b56ae8db782fb69a493`
- diagnostics: `d90d175e37b2382d97749be829f349dac5b8da566dfbe77642330dbaf288bc06`

Automatic private core publication `38890316033` and its normal GC completed
SUCCESS. Publish job `116937936098` confirmed `RUNTIME_PRIVATE_PUBLISH_OK` at
10:57:40 UTC: 135 files, 125 uploaded objects, generation
`802caca8-85e2-4e24-9034-4ae549d188f6`, same source SHA. This is publisher evidence;
no separate database mutation or authenticated physical-device test was performed.
Normal market refresh `38890316143` continues independently; a second refresh is
not required to establish this verified core/public rollout. Existing hourly
cadence and the 40-minute watchdog remain unchanged; feed observation time remains
the authority for freshness.

No model math, probability, training, thresholds, settlement, iNeed economics,
market scope, builder lifecycle, paid-provider quotas or real betting changes.
