# LOGIC-12 - Bet Builder lifecycle operator-evidence audit

Status: **AUDIT ONLY / SETTLEMENT BLOCKED / NO RUNTIME OR DB CHANGES**

Audit base: `935a2d1b2119c061fcda2ecdb3333ef395327125`.

## 1. Bounded objective

This audit asks one question only: do we currently have enough operator-authoritative evidence to define a deterministic one-ticket SHADOW lifecycle for a reserved tennis Bet Builder without inventing Superbet settlement semantics?

The answer on 2026-09-21 is **NO**.

This audit does not add or alter a database table, migration, RPC, Edge action, workflow runtime path, settlement runner, model, probability, risk calculation, PLAYABLE rule, email path, or real-money execution path. `builder_reservation.enabled` must remain absent/false.

## 2. Persistence rollout is already production-proven

PR #457 (`LOGIC-12: add guarded builder persistence sync contract`) passed exact-head full GREEN CI and merged as `3fa6fc5602a1c1cfebbe86a68d6425a8e5c20e2d`.

Production `ineed-sync` was then deployed as ACTIVE v12 with the existing GitHub OIDC trust boundary and the new `reserve_builder_tickets` action. The active experiment still has no `builder_reservation` block.

Normal SHADOW workflow run `35641902429` completed GREEN and proved:

- `builder_persistence.status=DISABLED`,
- `reason_code=BUILDER_RESERVATION_DISABLED`,
- zero attempted/reserved/idempotent builder writes,
- builder settlement disabled,
- `automatic_real_betting=false`,
- V1 sync healthy and email queue not regressed.

Post-run live SQL proof remained: zero builder tickets, zero open builder/V1 risk exposure, zero open shadow bets, 36 email events `SENT`, runtime health `OK`.

## 3. Current exact builder evidence is pricing evidence, not settlement evidence

`backend/superbet_direct.py::parse_event_combination_quotes()` accepts only active Superbet pre-priced combination market `238733` rows. It freezes exact operator selection UUID, component selection UUIDs, source event, price, timestamp and quote provenance.

`backend/superbet_builder_quotes.py` republishes those rows as the exact read-only builder quote artifact. It has no terminal result/payout owner.

A live raw current event inspection showed market-238733 rows with offer fields such as `uuid`, `marketId`, `outcomeId`, `price`, `status`, `offerStateId`, `oddComponents`, labels and tags. The individual combination row contains no terminal win/loss/void/cancel result field.

The event object exposes `matchResults` / `oddsResults` keys, but read-only checks of already-finished events captured earlier by Direct returned `offerStateStatus=finished` while `odds=[]`, `oddsResults=[]` and `matchResults=null`. Sample event IDs checked: `15059403`, `15059404`, `15063421`, `15074747`, `15075651`.

Therefore the current public event endpoint cannot be used as a proven post-match exact-combination result owner.

## 4. No settled exact builder sample exists yet

The exact builder quote artifact only began persisting this evidence on 2026-09-21. The current captured quote-bearing matches are scheduled for 2026-09-22, including event IDs `15059409`, `15059413` and `15063427`.

There is therefore no repository-captured before/after sample yet that proves how Superbet represents a terminal result for the same exact combination UUID and component UUID set.

Absence of evidence must remain `N/D`; it must not be converted into a synthetic ticket result.

## 5. Current official Superbet rules are not sufficient for an automatic implementation

Authoritative pages inspected on 2026-09-21:

- regulations index: `https://superbet.pl/wiki/regulamin`,
- Bet Builder official communication shown as NR 22/2023 dated 25.02.2026: `https://superbet.pl/wiki/oficjalny-komunikat-nr-05-2023-z-dnia-01-09-2023r`,
- tennis official communication NR 01/2023 dated 31.07.2026: `https://superbet.pl/wiki/oficjalny-komunikat-nr-01-2020`.

The Bet Builder communication NR 22/2023 is headed as applying to football and basketball, while its point 1 uses the broader wording that outside football an annulled constituent makes the entire Bet Builder settle at odds 1.0, subject to stated exceptions. That scope wording is not sufficient authority to extend the clause to tennis automatically.

The later tennis-specific communication states an explicit tennis rule: if one or more SuperBets/Bet Builder selections are void, the whole ticket is not cancelled; instead the total odds are recalculated using the selections that remain valid, with its stated exception for final-classification offers. The same tennis communication also defines interruption/retirement behavior for individual tennis selections.

The repository must not choose a precedence rule between these published texts by inference. Even if the later tennis-specific rule is intended to supersede the generic text for tennis, an automatic lifecycle still needs exact evidence for which constituent selections Superbet actually marks valid/void and for the resulting ticket odds/payout.

## 6. Forbidden substitutes

The following are explicitly rejected as builder settlement authorities:

- V1 `backend/ineed_settlement_runner.py`,
- V1 `ineed_system_settle_bet(...)`,
- `backend/signal_settlement.py` applied independently to builder legs,
- `backend/symphony2_tracker.py` leg aggregation,
- reconstructing a payout by multiplying surviving pre-match leg prices,
- treating disappearance of a quote after the match as WIN, LOSS, VOID or CANCELLED,
- treating match completion alone as proof of the exact combination outcome.

These sources can be useful diagnostics, but none is operator-authoritative one-ticket settlement evidence for the frozen Bet Builder composition.

## 7. Database lifecycle must remain dormant

The live/repository builder owner still permits only `SHADOW_RESERVED`. The builder-owned ledger constraint permits only the atomic `STAKE_RESERVED` debit. There is no builder payout/release terminal row contract and no Edge builder settlement/release action.

That is intentional. Adding terminal statuses or ledger credits before operator evidence is proven could silently create the wrong bankroll state even in SHADOW.

Current V1 settlement remains separate and authoritative only for V1 single bets.

## 8. Decision

Builder lifecycle implementation is **BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE**.

Reservation enablement remains OFF. No durable builder ticket should be created in production while the only safe terminal lifecycle is unknown, because a reservation could strand SHADOW bankroll/exposure.

The correct failure mode is to keep the builder ticket non-settlement-ready and preserve the existing zero-write production gate.

## 9. NEXT EXACT ACTION

1. Preserve at least one exact quote-bearing event snapshot through completion using the already-frozen event ID, combination selection UUID and component UUIDs.
2. After that event is terminal, inspect operator-provided post-match evidence without fuzzy/name matching and determine whether any public or authenticated read-only source ties a terminal ticket result/recalculated price/payout to the same exact combination identity.
3. Reconcile the published tennis-specific and general Bet Builder void rules with observed operator behavior; do not select a rule by code inference.
4. Only if exact operator evidence is sufficient, design a separate SHADOW one-ticket lifecycle contract with an atomic ticket-status + ledger mutation and exact idempotency.
5. Until then keep `builder_reservation.enabled` absent/false, keep builder settlement `NOT_IMPLEMENTED`, preserve V1 settlement/email behavior and keep `automatic_real_betting=false`.

## 10. Required proof for any future implementation PR

A future lifecycle implementation PR must include:

- at least one exact before/after operator evidence sample for a frozen composition,
- explicit treatment of WIN / LOSS / void-selection recalculation / all-void / cancellation / retirement cases supported by evidence,
- exact payout/recalculated-odds provenance,
- no use of V1 signal/bet identity,
- one experiment-row transaction mutex shared with current bankroll writers,
- replay/idempotency proof,
- zero model/probability/risk-math changes,
- exact-head full GREEN CI before merge,
- production rollout with reservation gate still disabled until a separate enablement decision.
