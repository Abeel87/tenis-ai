# LOGIC-12 ? Bet Builder terminal evidence capture

Status: **SHADOW READ-ONLY EVIDENCE CAPTURE ? NO SETTLEMENT AUTHORITY**

Branch base: `6e4f0a2e671f527e742dd8cc1d51abf25d89001c` (PR #458 merged). Before final exact-head validation the branch was synchronized without conflict through bot main `c5aa9039d26240c83e49ea73a4f630dfec803a2c`; the latest drift changed only generated `frontend/data/*` paths and had zero overlap with PR #459 files.

## Purpose

PR #458 froze `BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE`: current Superbet market `238733` evidence proves exact pre-match Bet Builder price and identity, but not a terminal one-ticket result, recalculated price or payout. This step does not implement settlement. It preserves exact pre-match identity and performs a bounded read-only observation of the same operator event after the scheduled start.

## Frozen source

The source is the already-published exact quote artifact; no quote is recreated or repriced:

- source commit: `935a2d1b2119c061fcda2ecdb3333ef395327125`
- source blob: `3f7b58212540f7c5a4b28f42457b3c747a9fb6f7`
- source generated at: `2026-09-21T18:56:50.924941+00:00`
- manifest: `audits/logic12_builder_terminal_evidence_manifest.json`
- deterministic selection rule: lexicographically smallest exact `operator_selection_id` per captured event.

The three frozen samples are:

1. event `15059409`, selection `0155873a-f67d-5288-a8a7-14e6b0f0e652`, Eva Lys vs Gabriela Elena Ruse, scheduled `2026-09-22T03:00:00Z`;
2. event `15059413`, selection `006b60ca-3498-50c4-97f8-5f1a1f327749`, Jelena Ostapenko vs Anastasia Zakharova, scheduled `2026-09-22T07:00:00Z`;
3. event `15063427`, selection `041c4d76-7e31-5acb-a1b3-3a060ae7e4e2`, Maria Sakkari vs Linda Fruhvirtova, scheduled `2026-09-22T12:00:00Z`.

Each manifest row also freezes the exact component UUID list, original combined odd and 24-hour probe window starting at the scheduled match time.

## Canonical evidence owner

`backend/superbet_builder_terminal_evidence.py` is the sole owner of this observation step.

It may:

- read the frozen manifest,
- call the existing public exact-event fetcher by numeric `event_id`,
- reverify exact event/pair/time identity with the existing safe fixture matcher,
- inspect only `odds`, `oddsResults`, `matchResults` and raw event offer-state metadata,
- retain raw dict objects only when the exact frozen combination UUID or exact component UUID occurs,
- write `frontend/data/superbet_builder_terminal_evidence.json` as a SHADOW evidence sidecar.

It may not:

- score a leg,
- map an operator value to WIN/LOSS/VOID/CANCELLED,
- reconstruct a Bet Builder result from component results,
- calculate or infer payout/recalculated odds,
- call V1 settlement,
- call builder reservation,
- access Supabase/Edge/iNeed persistence,
- change model/Symphony/PLAYABLE/iNeed calculations,
- enable real betting.

## Request and replay bounds

The manifest contains exactly three candidates. Before each candidate's `probe_from`, the collector performs zero request for that candidate. After `probe_until`, it performs zero request. Therefore one run can make at most three public exact-event requests.

If an exact frozen combination UUID appears in operator result containers, the raw object is preserved as `EXACT_OPERATOR_IDENTITY_HIT`. On subsequent runs that exact hit is carried forward without refetching that candidate, so a transient exact evidence object cannot be overwritten by later source disappearance.

Network/source failure is `SOURCE_UNAVAILABLE`; identity mismatch is `EVENT_IDENTITY_MISMATCH`; finished event without an exact combination result object is `EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE`. None of these states is converted into a settlement outcome.

## Hourly workflow boundary

The existing `Superbet hourly market refresh` invokes the collector only when its normal refresh is actually running and only outside pull requests. PR validation uses fixtures/tests and performs no terminal-evidence live request. The normal `frontend/data` commit step can preserve each observed SHADOW evidence snapshot in Git history.

## Initial live proof

Before the first probe window, a local live invocation at `2026-09-21T19:35:16.998556+00:00` produced:

- candidates: `3`,
- external requests: `0`,
- statuses: `NOT_PROBE_WINDOW`, `NOT_PROBE_WINDOW`, `NOT_PROBE_WINDOW`,
- `settlement_enabled=false`,
- `result_inferred=false`,
- `automatic_real_betting=false`.

## Current test proof

- terminal-evidence unit/contract tests: **11/11 GREEN**;
- exact Superbet/Symphony workflow pack including the collector: **207/207 GREEN**;
- full iNeed + quote/evidence pack: **196/196 GREEN**;
- full repository pytest: **1529/1529 GREEN**;
- Python syntax: GREEN;
- `git diff --check`: clean.

Exact-head GitHub CI remains required before merge.

## Hard gate

This collector cannot unblock settlement by itself. Even an `EXACT_OPERATOR_IDENTITY_HIT` is raw evidence only; its semantics must be separately audited against exact operator behavior/rules before a lifecycle contract can be designed.

`builder_reservation.enabled` remains absent/false. Builder settlement remains `NOT_IMPLEMENTED`. `automatic_real_betting=false` remains mandatory.
