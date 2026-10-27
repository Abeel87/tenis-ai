# Reliability audit and publication transport repair — 2026-10-27

User scope: inspect remaining faults, list confirmed problems and fix technical
causes. No changes to model mathematics, training, settlement, SHADOW/PROD or
active training data. Audit began on `00cf21d35163158d0bac65c773ba28dbb12da1b6`;
local implementation/real-byte fixtures use the subsequent successful core
publication `fea8efce330f031649d42be5f58096273a04f586`.

## Findings and disposition

| Finding | Evidence | Disposition |
| --- | --- | --- |
| Growing SHADOW report Git blobs | [Core run 40422422372](https://github.com/Abeel87/tenis-ai/actions/runs/40422422372), job 121921822197: GitHub warnings at 00:23:18 UTC for selection 94.23 MiB and settlement 93.29 MiB | Extend existing exact-byte transport to both files before the 100 MiB hard limit; retain complete JSON for every consumer |
| Publication fetches unrelated branches | Same job: local data commit 00:15:00, hundreds of branch fetch results only at 00:22:59 | Scope existing core and market fetches to main without tags; preserve rebase, freshness, retry and non-forced push |
| Full-history checkout transfers obsolete blobs | PR health job 121937370007 remained in Checkout from 00:38:20 through inspection at 00:43:46 UTC; market/DNA also waiting in full-history checkout | Keep depth 0 and use the existing checkout action's `blob:none` filter; current files and full commit history remain available, historical contents load on demand |
| Neuron training rejected | [Run 40298154578](https://github.com/Abeel87/tenis-ai/actions/runs/40298154578), job 121489179538: 10 fresh sources, one missing `atp_ongoing`, `RuntimeError`, `all_history_sources_available=false` | Correct fail-closed behavior; previous model retained. Do not weaken gate or modify training |
| Supabase errors | 2026-10-26 00:30 through 2026-10-27 00:30 UTC: three function HTTP 500s and three RPC HTTP 500s, all training archive GC; three PostgreSQL 57014 errors, latest 23:58:10 before deployment | Already addressed by GC #560/#561; no further timeout/ACL/index change justified |
| Other advisor findings and quota limits | Security/performance advisories match existing baseline; source quota reports explicit daily role cap | No evidence of a new authorization fault or a reason to drop indexes, revoke application RPCs or bypass quota |

The Neuron warning's `RuntimeError` corresponds to the canonical
`update.load_history` rejection of an empty downloaded frame. All other printed
quality gates passed; `REJECTED_KEEP_PREVIOUS` prevented replacement. A read-only
source probe during this audit returned HTTP 200, 2705 bytes and 11 CSV rows,
SHA-256 `3dee4c785e0776ad6a65c92b0e423632d81bd75f56815fcfc920edcfe1dcab19`.
This confirms recovery at probe time, not continuous provider availability.

## Canonical repair and safety

`scripts/history_publication_chunks.py` remains the only repository chunk owner.
Its existing CLI loop additionally processes selection and settlement reports,
with legacy JSON and absent optional reports supported. Pack verifies SHA-256
before removing the working JSON; restore verifies all parts and the full digest
before replacing the canonical file. Source rows, order, numeric representation,
identities, timestamps and all probabilities remain byte-identical.

Existing core/market/test/research/Pages restore boundaries already run before
consumers. Pages archives the restored JSON before removing the two additional
repository-only chunk folders. No Git history is rewritten and no runtime or
training archive is deleted. The next normal producer performs the storage
migration; the source PR does not replace generated data with an old snapshot.

The two publication fetches use `git fetch origin --no-tags
main:refs/remotes/origin/main`. Existing rebase, strict source freshness checks,
retry budgets and non-forced pushes are unchanged. This removes unrelated refs
from the fetch scope; it does not promise a fixed duration or reduce the existing
repository's historical size.

Full-history checkouts in core scope, UI health and market additionally use
`filter: blob:none`, supported by the existing `actions/checkout@v6` action.
Depth remains zero: all commit history and required comparison refs remain
available. Git fetches missing historical contents on demand with the checkout's
existing credentials. No branch, commit or historical report is removed.

## Validation

- Before repair: focused reproductions had **5 failures / 9 passes** (both report
  CLI paths, missing reports from restored runtime archive, two unbounded fetches).
- A second reproduction confirmed all **three** full-history checkout paths
  eagerly downloaded obsolete report bytes. The repaired integration test proves
  current bytes, complete merge ancestry, name-only diffs and lazy historical reads.
- After the additional checkout repair: **17 passed**. Coverage includes corruption rejection, multi-part
  restore/repack, unchanged bytes, complete runtime archive and Pages cleanup.
- Local-Git integration uses an actual shallow checkout with an all-branches fetch
  refspec, executes each real workflow fetch command and proves it
  obtains new main, excludes unrelated branch/tag objects and preserves both a
  concurrent report and the current generated report through rebase/non-forced push.
- Real production report round-trips are recorded in
  `publication_transport_roundtrip_20261027.json`: 98,810,660 and 97,819,113 bytes,
  six parts each, max 16,777,216 bytes, matching full SHA-256 after restoration.
- Final full local regression: **1818 passed in 56.13s**, two existing Neuron empty-fixture
  warnings. A truncated local CatBoost installation was reinstalled and its binary
  hash verified before this successful run; no repository dependency change.
- Fresh-main integration, all eight CI workflows and production publication have
  passed; immutable production evidence is recorded below.

Reference: [GitHub large-file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).
Checkout contract: [actions/checkout v6](https://github.com/actions/checkout/tree/v6).

The same transport settings for Player DNA are validated independently in a
companion PR, because that workflow also executes the complete SHADOW evaluation.
This publication repair does not change the DNA workflow or its model.

Read-only inspection of all 13 advisor-listed public functions confirmed fixed
search paths and internal caller checks for administrative/staff actions. The two
anonymous functions intentionally return aggregate public counts or a username
availability boolean. No ACL change was made. Leaked-password protection remains
an existing optional Auth hardening advisory, not an observed authorization bypass.

## FAST Pages checkout follow-up

The remaining FAST Pages full-history checkout has the same confirmed cost:
run 40429328294, job 121942894969, 00:54:31–00:57:58 UTC (**207 seconds**).
An added instance of the existing real-Git integration test failed before repair
because it found the obsolete report blob locally. Adding `filter: blob:none`
to that checkout preserves depth zero and passes the unchanged behavioral test.
The focused transport suite now passes **18 cases in 4.00s**. Scope classification,
source restoration, runtime archive, build and deployment are unchanged. Fresh-main
CI and the post-merge FAST production check are recorded in the live checkpoint.

## Production verification of #562

PR #562 merged as `126eb6c8f988b84d19a9ef6c04b5e81cee6fc180` after all eight
workflows succeeded on head `eed462ae90b06c8648b180738f58695005dc9cb2`.
The checked base `7930d7f7f72f725c465a12e211acfa6311d42930` was unchanged
immediately before merge. Final CI health: 1818 passed in 72.94s.

Normal [production run 40429939252](https://github.com/Abeel87/tenis-ai/actions/runs/40429939252)
completed successfully, including build 121945202492 and Pages 121952884115.
Both production regressions passed: 1818 cases in 51.57s before generation and
1818 in 54.09s after generated layers. Publication commit:
`f0bc07f9e3118c136dba209031b4541fb7ca8569`.

The complete commit/rebase/push step took 35 seconds (01:23:08–01:23:43 UTC).
The unchanged-main fetch/rebase finished at 01:23:14.876, under one second after
the local commit output at 01:23:14.584. No unrelated branch fetches or report
size warnings remain for the two repaired reports. Git still warns separately
about the current `results.json` blob (71.77 MiB); that source is not changed here.
Core scope checkout took 44 seconds; UI checkout measured 42 seconds versus 342
seconds before the filter, with full ancestry retained.

Independent reconstruction of all three ledger/report files verified every part
and full SHA-256. All **94,701** pre-existing frozen predictions retain their IDs
and complete row hashes. The **2,304** new predictions bring all three exact ID
sets to **97,005** rows. Canonical ledger/selection source hashes align and all
SHADOW isolation flags remain false. The two reports contain 101,299,842 and
100,171,509 bytes in seven and six parts respectively (maximum 16 MiB).

Downloaded runtime artifact **12702427235** was independently verified: all
55 source file sizes/checksums match its manifest; the three complete restored
JSON files exactly match Git reconstruction. Machine-readable evidence:
`publication_transport_production_20261027.json`.

Capacity observation, not a changed policy: this runtime archive contains
948,570,292 uncompressed JSON bytes against the existing 1 GiB verification
bound. Preserve source data and review capacity before that bound is reached;
this transport repair does not silently raise the bound or discard records.

FAST follow-up validation: all seven workflows passed on
`19816b1db569ade429c51f783483bf595701b3ff`; health job 121954221226
passed **1819 tests in 63.55s** and both project/runtime guards had zero failures.
The real UI smoke also passed on the fresh 474-match / 312-Symphony-match feed.
Main subsequently published market data. The branch now integrates
`283c7ba2fd187b490ae6c7ca33a7ffe4e360cbde`; refreshed CI, merge and FAST
production verification are pending. No generated snapshot is replaced by this PR.
