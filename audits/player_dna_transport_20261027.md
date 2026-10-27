# Player DNA transport optimization — 2026-10-27

PR #563, companion to publication repair #562. Merge #562 first. Two existing workflow settings change:
full commit history is retained with `filter: blob:none`, and full-report
publication fetches only main without tags before the existing snapshot freshness
check, rebase and non-forced push.

No dataset, profile, scorer, model, simulation, settlement, evaluation guard or
SHADOW/PROD setting changes. This PR runs the complete existing DNA evaluation;
it does not weaken or skip that pipeline to obtain a passing status.

Both regressions were reproduced before repair: an obsolete historical blob was
eagerly transferred, and the publication fetch acquired an unrelated branch/tag.
The corresponding local Git tests now verify current files, all commit ancestry,
name-only diffs, old content on demand and concurrent-main preservation.
The combined transport suite passed 19 cases; full local regression passed 1820
cases in 60.63s. The combined PR's health job 121940417801 also passed 1820 cases
in 79.06s. The independent full DNA workflow and fresh-main merge are pending.

Keep the current source freshness rejection, exact identities and active training
data intact. No history rewrite, data deletion, training or probability change.
