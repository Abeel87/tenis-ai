# Binary probability release gate — 2026-11-11

## Release candidate and required checks

Source PR #590 head f01df12c2dc8cd1c879938aece7b7f5f865c1a59 has 14 successful checks and one expected deploy-neuron-ui skip. The original Point Tape run 43062117267 / job 130667168120 completed successfully without restarting its source audit.

Fresh-main verification PR #591 candidate 75e548461c45f00252002d17dff324e6dcf4a159 has tree 6c5184e7fdc3ea149f873a7a68b32fbfad6b586d, incorporating main aad184a6fa3fe5e0b323581becab11b44d6db5a3. Its full health job 130750798537 reports 1957 passed, 9 subtests passed, Project health PASS and Runtime health PASS. Chromium, dependency, CodeQL and applicable context/data audits pass (12 successful checks). The candidate is verification-only and must never be merged.

## Two independent archive failures remain real failures

Candidate-lock run 43086106003 / job 130750796763 has candidate_lock_safety_verified=true but fingerprint_lock_matches=false. Runtime-equivalence run 43086105910 / job 130750797426 has locked_candidate_verified=false, runtime_contains_locked_2024_sources=false and runtime_equivalence_gate_passed=false. It reports 11620 locked rows, 43 unrelated output changes, 191 surface-prior changes and zero identity changes. These failures do NOT establish safe archive integration and are not waived or marked green.

The canonical registry's 2026-11-02 source contract explicitly keeps the 2024 archive outside runtime/training, preserves its original frozen manifest and rejects auto-relocking. The runtime-equivalence workflow itself requires runtime_contains_locked_2024_sources=false, integration_authorized=false and separate_mitigation_or_integration_pr_required=true: absent archive sources are the expected isolation boundary, not a defect to repair by importing them.

All 19 paths matching tml[-_]2024 in the main and candidate trees are byte-identical. The complete candidate-vs-main delta has only the 12 files belonging to PR #590; it does not modify the archive owners, manifest, model/update/history owners or workflow gates. The independent research workflows were triggered on #591 by the refreshed frontend/data/results.json relative to its older ci/symphony2-clean-base, not by a change to archive behavior in #590. The historical lock-drift condition is already recorded in the canonical registry and previous feature-release evidence.

Release decision: the archive remains blocked from integration, with both red reports retained. These separate archive-integration research failures do not block the canonical binary-probability repair, whose source PR is green and whose fresh-main runtime/health/browser/security validation is green. No archive code, frozen lock, CI guard, model SHADOW status or real-betting authorization is changed. Do not merge #591. GitHub main branch metadata reports protected=false / required contexts empty; this does not replace the repository's substantive green source/fresh-main requirements.

## Merge/publication boundary

Immediately before merge main must still equal aad184a6fa3fe5e0b323581becab11b44d6db5a3. Merge #590 with expected source head, then require actual merge tree to equal tested candidate 6c5184e7fdc3ea149f873a7a68b32fbfad6b586d. The synthetic pull/590/merge ref was stale (parents fe997e1... and f01df12...); it is not fresh-main proof. Actual publication requires a normal successful data/Pages pipeline plus a direct public runtime-7/learning-7 snapshot, exhaustive supported binary-pair validation and live frontend verification. A green build or merge alone is insufficient.

## Actual merge and publication handoff

PR #590 merged as 2be8a27e19a89adb0c5dbc4c2e31fca1a1df81d6 with expected source head. Actual merge parents aad184a6fa3fe5e0b323581becab11b44d6db5a3 and f01df12c2dc8cd1c879938aece7b7f5f865c1a59, tree6c5184e7fdc3ea149f873a7a68b32fbfad6b586d EXACTLY matches tested candidate. #591 closed without merge.

Normal production Update tennis data and deploy Pages run43094143033 started20:11:23Z on merge. Publication remains pending. Direct HTTP read still sees runtime-6/learning-6 generated18:50:47Z (148 matches,237 complete supported binary pairs,237 inconsistent,0 duplicate groups; SHA256f4635b10063cc949a11675b4a9027b7e857f965df1581d76900e8249df431500). This is old public data and must not be called a verified repair. Continue production verification before closing task/disabling automation.
