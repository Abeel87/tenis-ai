# Source-contract repair — 2026-11-02

The owner requested repairs and deployment after the remaining source problems
were described. Fresh base: `83ab0ca7d56aa9edb474f833b84286a6dfc046d4`.
This change repairs the canonical TML loader; it does not change model math,
learning thresholds, forecasts, settlement or Neuron/Self Evolution SHADOW status.

## Reproduced defect and repair

The declared Challenger ongoing URL returned HTTP 200, a valid 50-column CSV
header, 493 bytes and zero matches. The provider catalogue confirmed that same
file. Its displayed link label is not an alternative URL. The previous loader
misclassified every empty DataFrame as a transport failure and could retain an
obsolete ongoing snapshot.

Only the three explicitly declared rolling feeds now accept an empty frame with
the required identity schema. Annual empty archives, missing/invalid headers and
real download failures remain invalid. Cache reads and freshness preview use the
same canonical validator. Valid emptiness replaces old rows, records the real
fetch time, and is exposed in `empty_source_keys`/`fresh_empty`; no rows are
invented. A failed refresh retains the old timestamp and emits its warning.

The regressions failed before the fix: 5 failures. All 22 focused cache, source
and freshness tests passed afterwards. A real seven-source fetch at 08:52 UTC
produced **7 successful / 0 failed** reads. The 62 short-history players gained
no qualifying pre-match rows from that refresh; this is an ingestion correctness
fix, not a claimed model-coverage or accuracy gain.

## Remaining data boundaries

Strict complete-token coverage against the same 394-fixture input, using clean
declared current/2025 history strictly before 2026-11-02:

| Tour | Fixtures | At least one player missing history |
| --- | ---: | ---: |
| ITF | 217 | 216 |
| Challenger | 124 | 33 |
| WTA | 29 | 6 |
| ATP | 24 | 1 |

These counts include already-started fixtures and are not Neuron scoring counts.
The existing PBP schema audit (`41408800156`, artifact `13124423209`) projected
30 unique payloads: zero were ready for model-history ingestion and no duplicate
calibration sample proved schema compatibility. Existing bounded provider
backfill remains active; raw point tapes are not substituted for validated
serve/return histories or cross-provider identities.

The frozen 2024 candidate still contains 12,474 rows, but three source hashes and
the candidate hash differ from the Sept 17 lock. Original artifact `10509752222`
records 6,063 raw Challenger rows versus 5,936 now. It contains hashes/reports,
not the old raw rows, so a complete old/new field comparison is unavailable.
All nine current visible resolution changes are `none -> exact` for archive-only
players. No global ID, exact-shadow or score conflict was found in the candidate.
Those findings do not authorize treating old history as current form.

## Separately reviewed 2024 candidate

The owner requested repairs/deployment after the remaining archive problem was
described. The new candidate is a fresh audit revision from the four official
source files whose raw hashes, dates and logical hashes are recorded; it is not
represented as byte-equivalent to the historical candidate. The full previous
manifest is retained in the JSON evidence and the revision's basis records the
previous expected fingerprints.

All existing ID, score, exact-shadow and visible-resolution exclusions remain.
In addition, the review freezes exclusions for **all 236 archive-only player
keys** absent from the current clean baseline, including players not on today's
fixture list. This removes 854 additional candidate rows, leaving **11,620**.
Every exclusion has actual matching source-row evidence. Ten numeric consistency
checks of the surviving serve/return counters found zero violations; unknown
values remain unknown. The baseline identity-set digest is recorded.

Both canonical archive audits now recheck that every remaining candidate player
exists in the current baseline. Removing those identities later fails closed;
the exclusion list does not expand automatically. This closes the future-fixture
gap in the former visible-only identity check. Original conflict checks, the
frozen TASK 016 shape, source URLs and strict source/candidate fingerprint checks
remain in force. The equivalence workflow reads the exact reviewed row count
from the locked manifest instead of retaining the obsolete hardcoded 12,474.

The new checks were reproduced failing before implementation. Final regression:
**1893 passed** in 87.04s (two existing NumPy empty-fixture warnings); archive
focused tests: 16 passed. UI smoke after the required delivery build retained
394 matches and all 216 Symphony cards; both readiness fixtures passed.

The same-input runtime-equivalence audit verifies the new 11,620-row lock and zero
identity changes. Its separate integration gate correctly remains **false**:
adding the candidate would alter shared surface priors and change 35 matches
without direct archive history. This is reported, not suppressed, and no archive
is imported. Model probability, training and current form remain unchanged.
The full candidate safety audit and remote CI are pending. No provider replacement
or automatic re-locking is authorized or performed.

Machine-readable receipts, hashes, before/after summaries and exact limitations
are in `history_source_contracts_20261102.json`. Full CI and deployment are pending.
