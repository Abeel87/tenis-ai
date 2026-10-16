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

Targeted parser/discovery/identity/iNeed regression: 75 passed before the final
bounded-retry and duplicate-input tests. Final focused Direct/discovery/PWA
regression: 47 passed. Static UI, runtime UI (real data and both readiness
fixtures), match-time and decision-center smoke passed. Full suite, exact-head
CI, merge and publication checks are required and recorded in the execution
checkpoint. Initial full-run issues (diagnostic row indexing and cache revision
assertion) were repaired before the final focused pass.

No model math, probability, training, thresholds, settlement, iNeed economics,
market scope, builder lifecycle, paid-provider quotas or real betting changes.
