# LOGIC-12 - Bet Builder terminal sample #1 audit

Status: **AUDIT ONLY / SETTLEMENT STILL BLOCKED / NO RUNTIME OR DB CHANGES**

Audit base: `726d92002e00da9393d76cd173f246b9c0f7b0ce`.

## 1. Exact frozen sample

The bounded terminal-evidence collector was invoked read-only on 2026-09-22 at
`05:31:50Z`, after the first frozen probe window opened and before the other two
probe windows opened.

It performed exactly one public event request. Event `15059409` (Eva Lys vs
Gabriela Elena Ruse) passed the canonical exact pair/time identity check. The
operator event was terminal (`offerStateStatus` values were `finished`).

The same response did **not** expose an exact result object tied to frozen Bet
Builder selection UUID `0155873a-f67d-5288-a8a7-14e6b0f0e652`. The collector
observed no exact-combination result hit, `matchResults` was null and no usable
`oddsResults` result owner was present. The evidence status is therefore
`EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE`.

The other frozen events (`15059413`, `15063427`) remained `NOT_PROBE_WINDOW` and
were not requested. The immutable sample is stored in
`audits/logic12_builder_terminal_sample_15059409.json`.

## 2. What this proves

This proves that event completion alone is not an operator-authoritative Bet
Builder settlement signal. It also proves that disappearance of the pre-priced
combination offer after completion cannot be interpreted as WIN, LOSS, VOID or
CANCELLED.

The sample does not prove that Superbet never exposes terminal builder evidence
through another operator-owned surface. It proves only that the currently
approved public event evidence path did not expose that identity/result mapping
for this exact frozen composition at this observation time.

## 3. Current official-rule evidence

Current Superbet rules index (checked 2026-09-22):
`https://superbet.pl/wiki/regulamin`.

Relevant current publications:

- Bet Builder official communication NR 22/2023, current version dated
  25.02.2026: `https://superbet.pl/wiki/oficjalny-komunikat-nr-05-2023-z-dnia-01-09-2023r`.
- Tennis official communication NR 01/2023, current version dated 31.07.2026:
  `https://superbet.pl/wiki/oficjalny-komunikat-nr-01-2020`.

The Bet Builder communication defines Bet Builder as one wager made from several
selections in the same match/event and contains special rules for invalidated
constituents. The later tennis-specific communication explicitly says that when
one or more tennis SuperBets/Bet Builder selections are invalidated, the whole
wager is not simply cancelled; its total odds are recalculated from the valid
remaining selections, subject to the stated exception.

The repository must not invent a precedence engine from publication dates or
scope wording alone. A safe automatic implementation still needs authoritative
evidence for the terminal state of the exact constituent selections and the
resulting ticket-level odds/payout.

## 4. Settlement conclusion

`BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE` remains active.

Forbidden substitutes remain:

- applying V1 settlement independently to builder legs,
- treating the final match score as the builder ticket result,
- treating quote disappearance as a terminal result,
- multiplying/reconstructing surviving leg prices locally,
- deriving payout from Symphony or another model layer.

`settlement_result` and `payout` remain null in the captured sample.
`result_inferred=false`, `settlement_enabled=false`, and
`automatic_real_betting=false` are mandatory.

## 5. Next exact action

1. Keep the collector active only inside the two remaining frozen probe windows.
2. Capture event `15059413` no earlier than `2026-09-22T07:00:00Z` and event
   `15063427` no earlier than `2026-09-22T12:00:00Z`.
3. Preserve any exact operator-owned combination result object without mapping it
   to settlement semantics in the collector.
4. If the remaining completed events also expose no exact ticket result, record
   the same explicit N/D state; do not infer a result from legs.
5. Only after the evidence set is complete may a separate audit decide whether
   another authenticated/read-only operator surface is necessary. Builder
   reservation stays disabled until a separately proven whole-ticket lifecycle
   exists.
