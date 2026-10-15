# Technical application repair — 2026-10-15

User authorization: fix technical failures, then review the application and fix confirmed defects. Preserve model math, market scope, PLAYABLE, scoring/payout semantics and SHADOW isolation.

Base: `a154d1e4e21457879ba14a3b18a435fa7d1a77c6`. Capacity/compression deployments are complete and are not repeated. Unrelated open PRs #523/#537 and dependency PRs are not merged.

## Reproduced failures and canonical repairs

1. **Direct discovery blocked by an unrelated sample.** Market refresh `38702056406`, job `116312352752`, reports `DIRECT_LISTING_UNAVAILABLE / INSUFFICIENT_MARKET_EVIDENCE` and keeps the Direct file dated 2026-10-01. `browser_selected_direct_feed` used the diagnostic probe's first-event market requirements as a global gate. Production discovery now requests listing-only output from the same probe. Every selected candidate still passes the existing exact participant/time/public-event resolver; unknown identity remains `NO_SAFE_OVERLAP`. The diagnostic `probe-browser` retains its sample audit by default. A regression reproduces the old block and verifies both successful exact matching and rejected foreign identity.
2. **Result-fetch quota did not count timeouts.** `live_history_settle.main` incremented attempts only after `requests.get` returned. Three simulated timeouts exceeded a budget of two while reporting zero calls. Every attempt now counts before I/O. One bounded retry handles transient timeout/connection/429/5xx reads within the same existing total budget; permanent 404 is not retried or converted to an outcome. Scorers and terminal-result interpretation are unchanged. Safe per-match reason codes and previous cached failure diagnostics replace the unexplained counter.
3. **iNeed history input absent in fresh Actions checkout.** The iNeed workflow did not restore the canonical Git chunks before its existing history settlement consumer. It now uses the same exact-byte restore command as the other consumers, before settlement/sync. No labels or bankroll records are manually rewritten.
4. **iNeed zero/missing presentation.** `Number(null)`/`Number(false)` could report zero completed evaluations for a missing counter. Missing or invalid counts now stay N/D. When published backend intake reports zero match-winner candidates, the UI explains that it is waiting for a final PLAYABLE match-winner signal. It never invents a missing-data reason. Runner logs now include the existing health payload and quote-source timestamps/status.
5. **Old balance after 500 ledger rows.** The UI selected the oldest 500 ascending rows and derived current balance from row 500. It now requests the latest 500 and reverses only for chronological presentation. The bounded chart is labelled and does not prepend the initial bankroll across an omitted historical interval. A 600-row reproduction proves the latest balance is shown. No database or economic calculation changes.

## Observed state, not bugs to override

- iNeed runtime health at `2026-10-15T09:30:01Z`: 221 result rows, 34 final signals, zero allowed match-winner signals, zero evaluations. This agrees with `ineed_scope.py`, which allows only `match_winner` for V1. The current source publication contains other market types; no scope/threshold expansion is performed.
- Bet Builder exact-quote sidecar reported `SOURCE_UNAVAILABLE / DIRECT_REFRESH_FAILED`. Builder reservation and settlement remain disabled by the existing operator-evidence gate. Repairing the quote transport does not authorize real-money execution or a new builder lifecycle.
- Core run `38698344875` reported 17 requests, 5 settled, 10 not ready and 2 fetch errors, but did not publish their HTTP/exception details. The two original causes cannot be claimed until the preserved cache or a new instrumented run is inspected.
- Latest DNA, Neuron, Self Evolution and private runtime delivery runs were successful. Success is technical execution evidence, not model profitability or production-promotion evidence.

## Validation and rollout

- Baseline full suite: 1663 passing tests after canonical chunk restore.
- New reproductions fail on the old code; focused repairs pass.
- Static/runtime UI smoke passes for real published fixtures, routes, auth/role isolation, lazy delivery, exact offers, expiry, H2H, navigation, refresh and logout.
- Full final suite, PR CI, mobile Chromium CI and production verification are recorded in the execution checklist. Local browser installation could not download its binary; browser coverage must come from the actual CI run, not an invented local result.
- Required rollout: current-base PR, all CI green, fresh-main recheck, merge, then inspect actual Direct refresh, history result-fetch diagnostics, iNeed sync and deployed UI assets. No deployment success is claimed in this pre-merge audit.
