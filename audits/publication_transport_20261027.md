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
- Fresh-main integration, CI and production publication remain pending until
  corresponding evidence is recorded in the live checkpoint.

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
