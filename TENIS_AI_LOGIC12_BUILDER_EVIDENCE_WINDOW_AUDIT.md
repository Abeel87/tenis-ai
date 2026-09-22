# LOGIC-12 - Bet Builder terminal-evidence observation-window audit

Status: **EVIDENCE COLLECTION ONLY / SETTLEMENT BLOCKED / NO RUNTIME LOGIC CHANGE**

Audit base: `a5a19979632f6b1a9f552d8f51a4c7998b857dd5`.

## 1. Why the original 24h horizon is insufficient

The first frozen terminal sample for event `15059409` was captured at
`2026-09-22T05:31:50Z`. The exact event identity was reverified and the event
was already terminal, but the approved public event surface exposed no exact
combination result object, payout, or ticket-level result tied to the frozen
combination UUID.

That is a valid point-in-time N/D sample, but it is not proof that the operator
will never publish additional result evidence later.

The current Superbet online betting regulation, version listed on the official
rules index as updated 03.06.2026, states in the `Official result` section that
the company publishes event results after obtaining information from official
sources, within up to three calendar days from event completion. The same
regulation defines official communications as information binding on both the
company and the customer.

Authoritative rules index:
`https://superbet.pl/wiki/regulamin`.

Therefore a collector that stops after 24 hours could incorrectly classify a
late operator-owned result as permanently absent.

## 2. Bounded evidence-only correction

The frozen event/selection/component identities are unchanged. Only each
`probe_until` is extended from 24 hours to 96 hours after its existing
`probe_from`.

The 96h value is a conservative bounded evidence buffer: the existing first 24h
plus an additional 72h observation allowance. It is **not** encoded as a
settlement deadline and does not claim to translate the legal phrase “three
calendar days” into an operator settlement SLA.

Frozen identities remain:

- event `15059409`, selection `0155873a-f67d-5288-a8a7-14e6b0f0e652`,
- event `15059413`, selection `006b60ca-3498-50c4-97f8-5f1a1f327749`,
- event `15063427`, selection `041c4d76-7e31-5acb-a1b3-3a060ae7e4e2`.

No new candidate, fuzzy matching, dynamic discovery, settlement mapping or
additional per-run request capacity is introduced.

## 3. Request and safety bounds

The collector remains capped at `MAX_CANDIDATES=3`, so a single hourly run can
perform at most three public event requests. Before `probe_from` and after the
new `probe_until`, the candidate performs zero requests. An already captured
`EXACT_OPERATOR_IDENTITY_HIT` is preserved without refetching.

All existing hard stops remain:

- `settlement_enabled=false`,
- `result_inference_allowed=false`,
- `result_inferred=false`,
- no payout calculation,
- no Supabase/Edge mutation,
- no iNeed runtime influence,
- no PLAYABLE/Symphony/model influence,
- `automatic_real_betting=false`.

## 4. Settlement conclusion

This change does not weaken the existing
`BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE` decision. It makes the negative
evidence collection more reliable by avoiding a premature 24h cutoff.

A completed 96h observation with no exact result still remains evidence about
the approved public surface only. It must not by itself be converted into a
synthetic WIN/LOSS/VOID/CANCELLED outcome.

## 5. Next exact action

Continue hourly read-only observation of the same three frozen identities.
Preserve any exact combination UUID result object raw and uninterpreted. After
the bounded windows finish, compare all captured samples before deciding whether
another authenticated/read-only operator surface is necessary. Builder
reservation and builder settlement remain disabled until a separate lifecycle
contract is proven.
