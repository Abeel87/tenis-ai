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
| Publication fetches unrelated branches | Same job: local data commit 00:15:00, hundreds of branch fetch results only at 00:22:59 | Scope existing core, market and full DNA fetches to main without tags; preserve rebase, freshness, retry and non-forced push |
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

The three publication fetches use `git fetch origin --no-tags
main:refs/remotes/origin/main`. Existing rebase, strict source freshness checks,
retry budgets and non-forced pushes are unchanged. This removes unrelated refs
from the fetch scope; it does not promise a fixed duration or reduce the existing
repository's historical size.

## Validation

- Before repair: focused reproductions had **6 failures / 9 passes** (both report
  CLI paths, missing reports from restored runtime archive, three unbounded fetches).
- After repair: **15 passed**. Coverage includes corruption rejection, multi-part
  restore/repack, unchanged bytes, complete runtime archive and Pages cleanup.
- Local-Git integration executes each real workflow fetch command and proves it
  obtains new main, excludes unrelated branch/tag objects and preserves both a
  concurrent report and the current generated report through rebase/non-forced push.
- Real production report round-trips are recorded in
  `publication_transport_roundtrip_20261027.json`: 98,810,660 and 97,819,113 bytes,
  six parts each, max 16,777,216 bytes, matching full SHA-256 after restoration.
- Full local regression: **1816 passed in 65.18s**, two existing Neuron empty-fixture
  warnings. A truncated local CatBoost installation was reinstalled and its binary
  hash verified before this successful run; no repository dependency change.
- Fresh-main integration, CI and production publication remain pending until
  corresponding evidence is recorded in the live checkpoint.

Reference: [GitHub large-file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).
