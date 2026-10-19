# Tenis AI — execution checklist i checkpoint pracy

Status: **KANONICZNA LISTA WYKONAWCZA / PUNKT WZNOWIENIA**

Ten plik odpowiada za:

1. kolejność programu napraw i możliwość odhaczania etapów,
2. jednoznaczny punkt wznowienia po przerwaniu pracy, limicie czatu, zmianie agenta albo przesunięciu `main` przez boty.

Nie wolno zaczynać kolejnego etapu tylko dlatego, że „wydaje się następny”. Najpierw sprawdź ten plik, bieżący GitHub i ostatni checkpoint.

---

## 0. Legenda statusów

- `[ ]` — nie rozpoczęto,
- `[~]` — rozpoczęte / w toku,
- `[x]` — zakończone i potwierdzone dowodem,
- `[!]` — blocker / konflikt wymagający rozwiązania,
- `[S]` — SHADOW/audyt gotowy, ale bez promocji do PROD.

Element wolno oznaczyć `[x]` tylko wtedy, gdy istnieje odpowiedni dowód: commit/PR, test, artefakt audytu, zielone CI albo produkcyjna weryfikacja — zależnie od rodzaju zadania.

---

# 1. LIVE CHECKPOINT - od tego miejsca ma zaczynac kolejny czat

**REFRESH CONTRACT REPAIR — 2026-10-19, PR #550 / FRESH-MAIN VALIDATION**
- AUTHORIZATION: owner requested repairs after the GitHub-only health report.
- ORIGINAL BASE: `3a7ee2d468839313e1b655b4b79f5ae4abe0f914`.
- LAST VERIFIED MAIN: `8573c4fcc858b9cb9c9d5dc042cd768e9128ce4b`, observed
  2026-10-19 09:31 UTC. Only three generated Neuron SHADOW files changed;
  the bot commit is incorporated unchanged into this branch.
- BRANCH: `fix/refresh-contracts-20261019`; checkout `tenis-ai-repair`; PR #550.
  Initial head: `b5947f6508ab1bad2f9f8d45495410dd6a736902`.
- [x] Fresh main, open PRs, failed logs and canonical owners inspected.
- [x] Reproduce and repair false O/U pairing and whole-catalogue builder rejection.
- [x] Stream existing Player DNA feature ingestion without changing outputs;
  instrument workflow memory. Runner shutdown is observed, OOM is not proven.
- [x] 92 focused tests; full suite 1712 passed in 53.56s; UI static/runtime smoke
  passed on real data. Snapshot audit and synthetic memory proof are recorded in
  `audits/refresh_contracts_20261019.md`.
- [x] Publish PR. Initial UI health run `39217141650`: 1712 passed in 55.73s;
  eight of ten workflows green. Player DNA `39217141663` passed recent-form /
  Player State and scorer evaluation (RSS 4,089,540 / 4,755,876 KB, exit zero).
- [!] The same DNA run later stopped at current-card scoring, runner shutdown at
  08:02:25 UTC. No full workflow or production recovery is claimed.
- [!] Point Tape `39217141673`, job `117943537486`, stopped at opponent-strength
  evaluation with runner shutdown at 07:58:22 UTC. Cause is not proven OOM.
- [x] Extend bounded input ingestion to the canonical opponent audit; preserve
  complete-population prior indexes and original field precedence. Independent
  3000-point/30-match parity proof: identical rows/order/counters/pandas dtypes.
- [x] Reproduce eager current-card allocation (20,306,690 bytes on a 20 MB fixture).
  Reuse canonical repeatable file input across current/downstream consumers;
  preserve repeated passes, labels, feature values and model artifacts. Exact
  old/new 3000-point parity for five feature paths; active current-card integration
  compares fitted artifacts and second-pass profiles. Full local suite: **1729 passed
  in 53.89s**; diff whitespace check passed.
- [x] Head `f23bf50` passed eight workflows including UI health `39221003925`;
  Point Tape `39221003825` and DNA `39221003942` were still running during follow-up.
- [x] Reproduce pandas flattening of shared feature maps: 41.46 MB peak versus
  8.83 MB with canonical column-wise frame construction on the same fixture.
  Exact DataFrames, fitted coefficients and predictions checked; latest full suite
  **1733 passed in 63.16s**.
- [x] Head `11f20db` passed eight workflows. UI health `39222655833` passed
  **1733 tests in 47.60s**, browser/runtime and isolation checks. At 09:31 UTC,
  DNA `39222656168` had passed current-card scoring, market backtest, dynamic
  walk-forward and dynamic current-card scoring; hold calibration was running.
  Point Tape `39222656167` had passed opponent/pressure/tiebreak/recent-form/
  small-sample/matchup evaluation and the point scorer. Neither full workflow
  was yet complete; these are CI observations, not production confirmation.
- [x] Main advanced via Neuron bot commit `8573c4f` at 09:16:37 UTC.
  Integrated its generated files unchanged. Combined-tree full local suite:
  **1733 passed in 59.70s**. Fresh GitHub CI is required for this integration;
  do not count earlier-head results as final-head CI.
- [ ] Verify updated CI against fresh main; merge only green.
- [ ] Verify normal post-merge Superbet/Builder and Player DNA refresh evidence.
- FILES: canonical Superbet audit/quote collector, Player DNA scorer/recent-form/
  Player State/opponent/current/downstream ingestion, workflow memory probes, regression tests,
  audit, registry, architecture and this checkpoint.
- LIMITS: no new recovery evidence for provider HTTP 410 (196595/201913).
  Full production memory use and resolution of runner shutdown remain unproven.
- DO NOT REDO: prior app/Solar/storage fixes or unrelated PRs #523/#537/dependencies.
- NEXT EXACT ACTION: verify complete CI for the published fresh-main integration
  and recheck live main; merge only green and inspect normal
  post-merge producer logs and source times.
- BANS: model mathematics/features/weights/training policy, probability/thresholds,
  PLAYABLE decisions, settlement, iNeed economics/scope, builder lifecycle enablement,
  automatic SHADOW-to-PROD promotion and real betting.

**APP RELIABILITY AND OBSERVABILITY — 2026-10-16, DEPLOYED AND VERIFIED**
- AUTHORIZATION: owner approved the six proposed improvements after Solar:
  resilient refresh, PLAYABLE explanations, actual Self Evolution reports,
  lazy admin reports, synchronized preferences and common data status.
- BASE: `553d5c294cf94f5aa6d3a4c6ac94f285f495106c`; branch
  `feat/app-reliability-20261016`, isolated worktree `tenis-ai-reliability`.
- PR: #549; rebased onto bot-only main
  `924f53e3eee92ebf79dd864636713971292a289b` before publication.
- MERGED: `97352f92542fe394560f530cbd19ef64d75558ca`, PR head
  `ad7df99e1c0472b9af2a6d4a4f071303dc3905bd`; fresh main unchanged at merge.
- [x] Fresh main/PR/CI and canonical-owner inspection; no unrelated PR changes.
- [x] Browser reproduction of refresh clearing the visible list (0 instead of 1).
- [x] Implement/verify transactional refresh and read-only availability reasons.
- [x] Prepare whitelisted Self Evolution report through the existing private
  runtime publisher, tier C; preserve artifact privacy and SHADOW authority.
- [x] Lazy admin views, owner-scoped preferences and data status.
- [x] Chromium user/moderator/admin flows, failed/empty refresh, direct account
  change during failure, report metrics, lazy reports and 320/412/1280 px layout.
- [x] Static/runtime smoke, 48 focused Python tests, lossless delivery projection
  with all 273 PLAYABLE comparisons. Full regression: 1697 passed, two obsolete
  exact-source assertions updated for request timeout and restricted research
  push publication; both now pass in the focused suite.
- [x] Live additive migration `20261016130209` and publisher Edge version 4.
  Migration filename matches the version assigned by the deployment service.
  Transactional RLS proof: own read/update allowed, cross-user read/update/insert
  denied, anon grants absent, test rows rolled back. Advisors: no new findings.
  Both reader and publisher reject unauthenticated requests with HTTP 401.
- [x] Final local full suite: 1699 passed. GitHub full suite: 1699 passed in
  52.07s, health job `116987723321`, run `38905256988`. All 12 PR checks green;
  deployment-only Neuron step correctly skipped on PR. No review comments.
- [x] Research publisher job `116991562290`, run `38906585849` SUCCESS.
  Active research generation `c0b78b56-a83b-4bfc-ab86-618810e12729`, one tier-C
  object, 3349 bytes; SHA-256 `6cab12a35fbc78e0fa642e7ef91d8501c0ee316fb949e5a8a8e2eee4a161f533`
  exactly matches the locally validated projection of actual run `38879366541`.
- [x] Full tests, green PR, additive schema/compatible Edge rollout, merge,
  Pages/private report verification and final checkpoint.
- [x] Full publication `38906585956` SUCCESS, build `116993412931` and
  Pages deploy `117004513403`. Generated-data regression: 1699 passed in 51.84s.
  Data-only commit: `dd29571485d6dba4bde318ce6b1a0d61135bc8ea`.
- [x] At 13:47:27 UTC all five public frontend assets exactly matched tested
  source bytes. Live index: 98 matches, 148585 bytes, original Direct/AutoLearn
  dates present. Public research-report path returns 404; private tier C remains
  active. Proof: `audits/app_reliability_publication_20261016.json`.
- CLOSEOUT: `docs/app-reliability-closeout-20261016`; documentation only.
- NEXT EXACT ACTION: no further app repair or manual deployment required.
  Reopen the installed PWA to load the new assets. Normal data schedules and
  private core publication continue independently. Tests use isolated browser
  authentication; physical-device/production-account sign-in is not claimed.
- DO NOT REDO: reproduction, actual artifact projection from run 38879366541,
  Solar design, existing Superbet repair or model training.
- BANS: model math/weights/training, probability, PLAYABLE decision rules,
  settlement, iNeed economics/scope, real bets and automatic PROD promotion.

**SOLAR UI AND READABLE REPORTS — 2026-10-16, DEPLOYED AND VERIFIED**
- AUTHORIZATION: owner selected Solar and requested implementation/deployment plus
  readable replacements for raw code/JSON everywhere. Existing UI-only direct-commit
  exception applies; no model/learning promotion is authorized.
- SOURCE: `4326094a6a5d36f5f5e2fe296bc466d70c306bac`, synchronized with
  fresh main `0159adc4a6bf1dd98675656378b33b5e012bcf21` before publication.
- TEST FOLLOW-UP: `2f82042bff6279f977e4980a6059e8a09b8c1ef6`; closeout branch
  `docs/solar-ui-closeout-20261016`, isolated checkout `tenis-ai-solar`.
- [x] Raw report reproduction and canonical-owner audit.
- [x] Solar in canonical stylesheet, shared readable report rendering, compact
  overview/Neuron, source-safe odds emphasis, manifest/PWA cache refresh.
- [x] Structured report regression; UI static/runtime smoke; 17 focused Python
  tests; real Chromium user/moderator/admin test with isolated authentication.
- [x] Mobile layout 320/412 px and desktop 1280 px checked; screenshots reviewed.
- [x] Full regression: 1680 passed; two exact-line inventory checks initially
  failed after the presentation code moved. The existing readiness inventory
  now records the same consumers plus one display-label token; the focused
  22-test suite (including both failing checks) passes. No readiness policy changed.
- [x] Both readiness fixture runtime smokes, decision-center, match-time and
  all 28 JavaScript syntax checks passed.
- [x] Remote full Python suite: 1682 passed in 51.69s (job `116963303305`).
  That run was superseded after the full suite by the test-only follow-up.
- [x] Fast Pages workflow `38898084567`, deploy job `116963302733` SUCCESS,
  including Deploy Pages. At 12:10:40 UTC, all five public frontend assets match
  tested source bytes; evidence: `audits/solar_ui_publication_20261016.json`.
- [x] PWA revision: `tenis-ai-mobile-presentation-20261016-solar`.
- [x] Delivery projection follow-up: remote browser job `116963303268` stopped
  at an obsolete exact-source assertion for the old Player DNA card. Replaced
  it with a rendered-coverage check using true/false/missing delivery summaries
  and conflicting full-record fields. Local delivery projection passes all
  273 PLAYABLE equivalence cases; production code and data are unchanged.
- [x] Final Delivery/security workflow `38898885890` SUCCESS: dependencies
  `116965940770` and Chromium browser `116965941032`, user/moderator/admin,
  report expansion, mobile/desktop layout and all 273 projection cases.
- [x] CodeQL `38898084834` SUCCESS for the deployed UI source.
- [x] Final UI health workflow `38898885692`, job `116966187071` SUCCESS.
  Its lightweight scope includes the report/static/runtime/readiness checks;
  the full Python suite passed separately above on the same production code.
- FILES: frontend app/style/index/manifest/sw; report/static/browser tests;
  readiness source inventory and contract test; audit, registry, architecture
  and this checkpoint.
- DO NOT REDO: completed Superbet/model/storage repairs and design selection.
- NEXT EXACT ACTION: no further Solar source repair or manual deploy required.
  Reopen the installed PWA to load the updated assets. Normal data/model
  schedules continue independently; unrelated PRs stay untouched. Physical
  phone behavior and production sign-in are not claimed tested by the harness.
- BANS: backend/model math, probabilities, thresholds, weights, training,
  PLAYABLE, settlement, iNeed economics/scope, auth rules and real betting.


**SUPERBET DIRECT COVERAGE REPAIR — 2026-10-16, DEPLOYED AND VERIFIED**
- AUTHORIZATION: user approved the proposed collection repair, shared discovery,
  verified identity reuse, missing-price diagnostics and refresh reliability work.
- SOURCE: PR #547, head `252bdb252fb458e137f8dd2abee5c880a255ea00`, merged as
  `ec908de4764b344db87297a35ca5131e5882db2b` against freshly rechecked main
  `fcca685f8e236544c15f9354c08ae8a6ab0d92c5`. Closeout branch:
  `docs/superbet-discovery-verification-20261016`.
- [x] Reproduce: public v3 nested fixture schema was ignored; main Direct lacked XHR
  discovery. Six new regression cases failed before repair.
- [x] Canonical discovery ownership, price-free identity continuity, fail-closed
  empty refreshes, bounded transient retry and admin diagnostic presentation implemented.
- [x] Read-only live probe: 167 discovered events; 75 app candidates; 76 unique reads;
  73 exact verified matches; two TIME_MISMATCH rejections; no transport failures.
- [x] Focused final Direct/discovery/PWA regression: 47 passed. Earlier broader
  discovery/fixture/iNeed suite: 75 passed. Static UI check passed.
- [x] Runtime UI smoke passed for real data and both readiness fixtures; match-time
  and decision-center smoke passed.
- [x] Full final-source local regression: 1682 passed in 136.90s. Remote full suite:
  1682 passed in 42.57s (health job `116926938869`). Initial validation issues were
  corrected before the final green runs.
- [x] All 12 PR workflows passed: 15 successful checks and two intentional
  production-only skips. Mobile browser job `116926938893` passed. Fresh main
  remained unchanged before the green-only merge.
- [x] Production Update/Pages `38887707148` SUCCESS; deploy job `116937787096`.
  Final full regression after generated layers: 1682 passed in 33.96s.
  Data commit / last verified main: `91aa93cde9009d149efa22159731f9380b95c877`.
- [x] Published Direct at `2026-10-16T10:37:56.264334+00:00`: 84 app fixtures,
  189 discovered event URLs, 65 candidates, 62 exact verified matches, 66 unique
  event reads and zero fetch failures. Remaining reasons: 19
  `NOT_IN_DISCOVERED_CATALOGUE`, three `TIME_MISMATCH`. Counts describe this
  source snapshot, not PLAYABLE, all operator coverage or a fixed success rate.
- [x] Read-only public verification at 10:55 UTC: app.js and sw.js match tested
  source bytes; Direct matches the data commit and manifest SHA-256; delivery
  diagnostics exactly project source counts/reasons. All 84 fixtures are accounted
  for, all included prices have fresh observation times and all 62 identity hints
  are price-free. PWA cache revision: `20261016-superbet-discovery`.
- [x] Private core publication `38890316033` and its normal GC both SUCCESS.
  Publisher confirmed 135 files / 125 uploaded objects, active generation
  `802caca8-85e2-4e24-9034-4ae549d188f6` at 10:57:40 UTC for the same source SHA.
- [x] Subsequent normal market refresh `38890316143` also SUCCESS. At 10:59:32 UTC,
  it freshly revalidated 62 remembered identities and resolved 74/84 fixtures,
  with 200 discovered URLs, 78 unique reads and zero fetch failures. Seven
  catalogue gaps and three time mismatches remain. Last verified main:
  `90b52346ff84b5e0ed85e76758efc4212423c986`; its drift is generated data only.
  These are producer-run counts; the independent public-byte proof above covers
  the earlier core snapshot.
- NEXT EXACT ACTION: observe normal schedules and actual source timestamps; no
  further source repair or manual refresh is required for PR #547. Reopen the PWA
  for the new admin diagnostics. Catalogue gaps and schedule mismatches remain
  explicit; do not weaken exact identity/time/market verification to fill them.
- DO NOT REDO: October 15 capacity/compression/settlement fixes; unrelated #523/#537 remain untouched.
- BANS: model math, thresholds, probabilities, training, PLAYABLE rules, iNeed economic
  calculations/scope, builder lifecycle, settlement, paid quota changes and real bets.


**APPLICATION TECHNICAL REPAIR — 2026-10-15, DEPLOYED AND VERIFIED**
- AUTHORIZATION: user requested technical repairs and a broader code/application review. Model/scoring/economic semantics, existing market scope and SHADOW isolation are preserved.
- SOURCE: PR #545, head `04f947691e5116545bf5e1766003905a207268ac`, merged as `698de5f4807c7da900a64e8bf95195deccab4f33` against freshly rechecked main `a154d1e4e21457879ba14a3b18a435fa7d1a77c6`. Closeout branch: `docs/app-repair-verification-20261015`.
- [x] Canonical audit/reproductions and minimal fixes: unrelated Direct sample gate, uncounted timeout attempts, missing iNeed history restore, missing evaluation counts shown as zero and stale oldest-500 ledger balance. Evidence: `audits/technical_health_20261015.md`.
- [x] Full regression: baseline 1663 and final 1671 passed; all 28 frontend JavaScript syntax checks and UI static/runtime smoke pass. Project health: zero failures / one pre-existing warning.
- [x] PR CI: all 11 triggered workflows green; 14 successful checks and two intentional PR-only production skips. Actual mobile Chromium E2E job `116387034668` passed user/moderator/admin scenarios. Real production sign-in and the physical phone were not tested.
- [x] Fresh-main check and green-only merge. Post-merge UI/Project Health, CodeQL and Delivery/security workflows are green.
- [x] Live Direct recovery in core run `38725160239`, job `116390007426`: `OK`, five of five candidates resolved, zero rejected, fresh file generated `2026-10-15T11:13:21.896639Z`.
- [x] History diagnostics: at `11:16:17.761439Z`, 23 calls yielded 12 normal settlements, one retirement, eight not ready and two HTTP 410 errors. Preserved cache proves the same original two errors at `07:33:33.817667Z`: matches `196595` and `201913`. The provider still does not return their results; no fabricated settlement or repeated transient retry was applied.
- [x] Core/Pages run `38725160239` completed SUCCESS, producing data commit `7edf464019a93600039536b3cc763209098b4858`. Its final full regression on generated data passed 1671 tests. Public `ineed.js`, `sw.js`, `data/meta.json` and `data/superbet_direct_current.json` are HTTP 200 and exactly equal the deployed source bytes.
- [x] Supabase private core publication `38728379426`: active generation `5a4b9ae3-4ea2-4e05-89f2-59732e730cce` at `11:38:06.319514Z`, 195/195 objects and 75,647,514 bytes verified; zero missing objects or size mismatches.
- [x] Normal market refresh `38728379362` SUCCESS; data commit `d04151496663ead3c873b9d7c25fb0ea4156839c`. Direct refreshed again at 11:38 UTC with five exact matches; builder artifact `OK` with 500 offers. No eligible dynamic composition remains a true empty result, not a source failure.
- [x] iNeed run `38729088692` SUCCESS including exact history restore. SQL at `11:42:50.157535Z`: runtime status OK, 144 matches, 26 final signals, zero V1 match-winner candidates, zero evaluations, automatic real betting false. Builder quote input is fresh/OK; reservation remains explicitly disabled.
- REAL LIMITATIONS: two unavailable external provider results (HTTP 410); V1 accepts only existing final PLAYABLE match-winner signals; builder lifecycle remains disabled by its operator-evidence gate. No guarantee of model profitability or physical-phone behavior.
- DO NOT REDO: compression/capacity rollout, the merged technical repair, baseline audit or passing PR tests. Automatic FAST run `38725160253` deliberately skipped deployment for backend scope; its green status is not Pages deployment proof.
- NEXT EXACT ACTION: no further technical rollout is pending for PR #545. Observe normal schedules and the weekly report; obtain provider corrections for HTTP 410 matches `196595` and `201913` before any settlement change. Reopen the installed PWA to receive the new cache revision; physical-device behavior is not claimed verified. Continue the existing model-reorganization program only under its own authorization. Do not merge unrelated #523/#537.
- BANS: no model math, probability/threshold/weight/training/PLAYABLE changes, result reinterpretation, V1 market expansion, builder enablement, real bets, history deletion or quota/billing changes.

**TRAINING ARCHIVE PRO CAPACITY — 2026-10-15, DEPLOYED AND VERIFIED**
- AUTHORIZATION: user requested safe capacity increase, then confirmed buying Supabase Pro. Live organization API confirms `pro` / `tier_pro`; one project in the organization. Pro includes 100 GB file Storage; its 8 GB database disk is separate.
- SOURCE: PR #543, head `49998c69b497562ae99ee292ba614f6730d5f96b`, merged as `0f02cd392f5a9d697b267cbde6057f8fe59cc9be` against fresh main `c2694952c5832aa4def19d177d1656ad385b6b28`. Documentation closeout branch `docs/archive-pro-deployment-20261015`. Open PR #523 contains an older unrelated 900 MB project-ceiling proposal and must not be merged as part of this change.
- [x] Live baseline: archive 292,100,801 B / 17,506 objects; runtime 152,901,969 B; avatar 1,253,751 B; total 446,256,521 B. Both active guards still have 300 MB / 750 MB limits before rollout.
- [x] Previous compression follow-up resolved: archive run 38652823135 completed successfully, all 14,358 files verified. Later run 38668491226 also completed with 14,599 entries. Do not redo compression or dispatch a duplicate recovery for those runs.
- [x] Canonical change prepared: migration `20261015100822_training_archive_pro_capacity.sql` changes only two archive-cap constants to 30,000,000,000 B and two project-ceiling constants to 75,000,000,000 B. Existing function bodies, triggers, ACLs, dedupe, lock and retention are preserved.
- [x] SQL reproduction / validation: rollback-only temporary tables show old 300 MB cap rejects 447,419,670 B; proposed guards accept that snapshot and exact 30 GB / 75 GB boundaries, reject +1 B through both guards, and account for missing physical uploads. No production rows changed by these checks.
- [x] Local regression: 1661 passed initially; the two missing-fixture tests passed after restoring the canonical Git chunks, for 1663 passing tests in total. Remote exact-head 7/7 workflows and 10/10 checks succeeded; fresh main equalled PR base immediately before merge.
- [x] Exact reviewed migration applied as Supabase migration `20261015102024_training_archive_pro_capacity`. Both live function definitions equal the previous definitions with only the four reviewed bigint constants replaced. ACLs remain identical: no anon/authenticated execution, service_role allowed. Archive object count/bytes and runtime/avatar Storage were unchanged by the migration. Security advisors have no new findings relative to baseline.
- [x] Actual failure reproduced in run 38702056330 attempt 1: `reserved bytes 329873534 > 300000000`. After rollout, attempt 2 completed SUCCESS; manifest `6e8808b5-ac20-4371-8b54-bcf2ff61a780` is complete at `2026-10-15T10:24:59.774426Z`, with all 14,602 entries verified, 155,409,092 logical bytes and zero missing/wrong-size physical objects.
- [x] Post-publication physical Storage: archive 330,004,249 B / 17,538 objects, runtime 140,415,539 B / 310 objects, avatar 1,253,751 B; total 471,673,539 B. The archive has passed the former 300 MB limit successfully and has 29,669,995,751 B of its new 30 GB budget available at this observation.
- FILES: capacity migration, `docs/training-archive.md`, registry and this checkpoint. Corrected stale documentation that still described the pre-dedupe 250 MB admission calculation.
- NEXT EXACT ACTION: no further capacity rollout or manual archive recovery is needed. Observe normal scheduled publication and existing retention/GC through the weekly report. Retain the 25 GB nominal safety margin; re-evaluate quotas before downgrading the plan or adding organization projects. Do not reapply the migration or rerun the completed archive attempt.
- DO NOT REDO / BANS: no model, probability, threshold, training, PLAYABLE, settlement, iNeed$, SHADOW/PROD, compression, retention, history deletion, credentials, billing or workflow changes. No real bets.

**RUNTIME COMPRESSION — DEPLOYED AND VERIFIED, 2026-10-14**
- USER AUTHORIZATION / SCOPE: apply lossless compression safely. Transport representation only; source data and all model/PLAYABLE/iNeed$ logic remain unchanged.
- ROLLOUT SOURCE: 11a93279558b7de3b3031b6a2f8d2b231217db3d. Documentation refreshed onto verified main d17aa8553584c786a06e42a85df4b8be30a5e78f after normal LOGIC-08 and tennis-data publications; all intervening changes are frontend/data files. Reader PR #540 merged as 000cf233caf59ae36dc992729f55dfb532bd7e6a; writer PR #541 merged as 11a93279558b7de3b3031b6a2f8d2b231217db3d.
- [x] Reader-first deployment: all 8 reader PR workflows green, Fast frontend deploy 38651028754 success. Public runtime-data-transport.js and sw.js exactly matched the tested files, including both gzip formats and the compressed-runtime PWA revision, before writer merge.
- [x] Writer: all 7 required PR workflows and 10 checks passed. Combined local suite 1663 passed; focused 26 passed; JS legacy/gzip/corruption 29 passed.
- [x] DNA publication and normal GC: run 38651976599 success; active generation 146c2a93-01b0-4720-80e7-e1c758b7db56. Active bytes 81,078,067 -> 11,039,619.
- [x] Core publication and normal GC: run 38652233887 success; active generation c9a570e3-2a18-426c-b351-14213e85102f. Active bytes 629,107,600 -> 83,576,790.
- [x] Live integrity proof: 35/35 compressed transport objects and manifests match tested SHA-256, lengths and access tiers. All 282 active core/DNA objects exist in Storage with matching lengths; no missing objects or size mismatches.
- [x] Exact reconstruction: four oversized JSON files preserve original source SHA-256/length. History preserves all 2500 records, order and original compact chunk bytes; source SHA-256 f1f2af0631b6d3547a59c2859954f4e67903b5c4b8bb53a4ff33f3232db82499. History source 213,335,321 B -> 20,346,368 B compressed chunks.
- [x] Storage after manual migrations and normal GC: physical project 885,085,931 -> 269,516,673 B (615,569,258 B released). Active runtime 760,779,372 -> 145,210,114 B at this checkpoint, before the normal queued market refresh. Archive remains 123,052,808 B; no archive/history deletion or cap increase.
- [x] Normal market publication/GC run 38652243714 also succeeded. Active runtime is now 149,088,172 B (core 83,576,790; DNA 11,039,619; market 54,223,318; Neuron 248,445), compared with 760,779,372 B before this rollout.
- [x] Archive capacity block cleared: fresh run 38652823135 passed the unchanged 750,000,000 B project guard and created manifest 8a01f96d-c04f-476a-92c4-7de4585c7879 for 14,358 files / 152,323,220 B. Durable upload is progressing; 10,601 entries were verified at this checkpoint.
- [~] Asynchronous archive follow-up (observed 2026-10-14 23:26 UTC): run 38652823135 was in progress and its manifest was staged, not complete. The workflow continues independently. Do not infer full archive completion from the inventory artifact or successful start; use its live run/manifest.
- NEXT EXACT ACTION: read-only check of the existing archive run and its manifest at the next status review; record completion or the concrete error. Do not dispatch a duplicate run. Compression itself is deployed and verified; no further compression changes or model work are required.
- ROLLBACK: retain the backward-compatible reader; revert the writer representation and republish the same canonical JSON via existing OIDC activation. Recheck capacity before restoring larger objects. Existing GC stays authoritative.
- DO NOT REDO: compression or completed reader/writer migrations. PR #537 remains separate/unmerged; no model math, probability, thresholds, training, promotion, settlement, iNeed$ calculations, archive retention, authorization, workflow, storage-cap or paid-plan changes.

**SELF EVOLUTION PANEL DELIVERY REPAIR — 2026-10-10, IN PROGRESS**
- VERIFIED BASE: `2832a1bc645f8d8036a4c6c872b50719cf8f43b6`; open PR #523 and dependency PRs do not overlap this repair.
- BRANCH: `fix/self-evolution-panel-delivery`; PR #534. Heads c1375cdb and 0466e838 passed 10/10 workflows. Resumed 2026-10-11 on data-only main f43e5520; fresh CI is required before merge.
- ROOT FAILURE: app.js renders a permanent missing-module placeholder if an older HTML shell omits the separate presenter or that request fails. Current public HTML and JS both exist; the exact phone cache/network cause is not proven.
- REPRODUCTION: runtime smoke omitting the optional script fails at the Self Evolution route assertion, matching the screenshot. Canonical repair bundles the unchanged presenter into app.js and removes the separate script/import/cache entry. No second loader or presenter.
- LIVE RESEARCH VERIFIED: scheduled main runs 37924098106 (Oct 9) and 38046146528 (Oct 10) succeeded. Oct 10 restored Oct 9 memory, reports memory_run_number=2, tracks=3; SHADOW_EVIDENCE_POSITIVE with 50 holdout fixtures, Brier candidate 0.180190223 vs Current 0.182710775. Descriptive holdout evidence, NOT prospective promotion or financial ROI.
- TESTS: pre-fix regression reproduced; post-fix runtime smoke PASS for real feed and both readiness fixtures; static/decision smoke PASS. Full final pytest: 1649/1649 PASS (30.65s); focused readiness/UI pack 9/9 PASS. Initial remote head 10/10 GREEN. 2026-10-10 refreshed head 0466e838 also passed 10/10. Overnight data-only main synchronization and production deployment pending.
- NEXT EXACT ACTION: verify local tests, publish PR, require all exact-head checks green, compare fresh main, merge and verify public app.js plus legacy-shell route.
- HARD BANS: no training/model/probability/settlement/PROD changes or real betting. Do not redo the already successful research runtime.

**SELF EVOLUTION ADMIN STATUS UI — 2026-10-09, BRANCH & PR PENDING**
- VERIFIED MAIN BASE: c66ec0ccbd738040ac2417af8c0d306742e172d0; later data bot commits may move main.
- ACTIVE TASK: display truthful research status in administrator UI; NO changing canonical evolution trainer, price archivist or model owners.
- BRANCH: feature/self-evolution-admin-ui-20261009; PR/CI pending.
- FILES: frontend/self-evolution-ui.js, frontend/app.js, frontend/index.html, frontend/style.css, frontend/sw.js, tests/test_self_evolution_ui.py, docs, registry, architecture and this checkpoint.
- OBSERVED 2026-10-09 05:31Z-ish: no confirmed schedule/workflow_dispatch main Self Evolution run among recent Github workflow executions. PR-success is not real training.
- REAL QUOTE RUN: Superbet refresh 37874967907 (2026-10-09 02:31Z) succeeded; archival evidence artifact created but logged NO_VERIFIED_PREMATCH_QUOTES (0 accepted, eight DIRECT_UNVERIFIED_IDENTITY_OR_ASOF, plus inaccessible dynamic/prepriced). No economic learning evidence.
- UI POLICY: show last main actual run and run-artifact metadata, N/D for unseen Brier, champion, ROI; link official Actions report, no secret tokens, admin route only.
- NEXT EXACT ACTION: commit branch and open PR; verify UI/static/full CI exact head GREEN; check fresh main/overlap; merge only green; verify fast Pages deployment and administrator route. Do not claim learning gains or UI available until deployment proof.
- HARD BANS: no PROD model calculations, probability/threshold/weights, training, settlement, Superbet fetch, Symphony/PLAYABLE/iNeed, SHADOW-PROD promotion, real bets.


**SELF EVOLUTION PHASE 2c — EXACT OPERATOR QUOTE EVIDENCE (2026-10-08, PR PENDING)**
- VERIFIED MAIN at branch creation: 6507d3db6e8955e2366819ef523685192270aa3a (#531 merged; later market refresh may advance main).
- ACTIVE: passively archive verified pre-start real Superbet quote evidence from current direct/exact/dynamic sources via existing market refresh; no extra HTTP requests.
- BRANCH: feature/self-evolution-quote-evidence-20261008, PR/CI pending.
- FILES: backend/superbet_quote_evidence.py, tests/test_superbet_quote_evidence.py, .github/workflows/superbet-market-refresh.yml, docs, registry, architecture, checkpoint.
- OBSERVED: 2026-10-08 11:30Z exact BB had SOURCE_UNAVAILABLE, dynamic BB DIRECT_INPUT_STALE; zero verified BB prices in those sampled files, not evidence that bookmaker universally has no markets.
- CURRENT blocker: no successful main Self Evolution schedule/manual run observed as of 12:29Z; no exact historical quote-to-decision ledger; no ROI/EV.
- NEXT EXACT ACTION: commit, PR, verify targeted/full exact-head GREEN; compare fresh main; merge only green; inspect genuine main market refresh quote artifact and its audited counts, separately verify first main Self Evolution runtime.
- HARD BAN: no PROD model probability/weight/training, no settlement/PLAYABLE/Symphony/iNeed changes; no synthetic quotes or real-money execution.


**SELF EVOLUTION PHASE 2b — 2026-10-08, PR PENDING**
- ACTIVE TASK: persistent research-only SHADOW Champion/Challenger evaluation with frozen 14-day prospective trials; modify only canonical backend/self_evolution_shadow.py.
- LAST VERIFIED MAIN: fc08dc05c14fc80ac1ce6df0e543389ad4a48564 (phase 2a #530 merged; data commits may advance main).
- BRANCH: feature/self-evolution-prospective-memory-20261008, PR/CI pending.
- FILES: backend/self_evolution_shadow.py, tests/test_self_evolution_shadow.py, .github/workflows/self-evolution-shadow.yml, docs, registry, architecture, checkpoint.
- STATUS: source and negative tests authored; no remote test, merge or first main research run proven yet.
- NEXT EXACT ACTION: commit source, open PR, run exact-head required green CI; compare current main; merge only after all GREEN; inspect authentic successful main workflow report and memory artifact.
- BLOCKERS: no observed successful main research run; exact historical bookmaker quotes not available; memory artifacts have limited retention.
- HARD BANS: zero model/training math, probability owners, settlement, PROD/PLAYABLE/Symphony/iNeed modifications; no real wagers or historic-ROI claims.


**SELF EVOLUTION PHASE 2a — 2026-10-08 (branch, pending PR CI)**
- LAST VERIFIED MAIN: `9811ff2b7bf467d664c6a43285c2084ede55527e` (PR #527 phase-1 merged, 11/11 GREEN).
- BRANCH: `feature/self-evolution-market-specialists-20261008`; PR/CI pending.
- ACTIVE TASK: add read-only market-specific challenger research to canonical SHADOW owner; do not create parallel trainer.
- MODIFIED: backend/self_evolution_shadow.py, tests/test_self_evolution_shadow.py, docs/SELF_EVOLUTION_SHADOW.md, registry, architecture, checkpoint.
- BLOCKERS: no confirmed manual/scheduled `main` research report yet; historical exact operator quote ledger not available, so EV/ROI learning is N/D.
- HARD BANS: no PROD probability/weights, Player DNA, Symfonia, PLAYABLE, iNeed, settlement, quote authority, real bets or automatic promotion. No speculative future results or hindsight quotes.
- NEXT EXACT ACTION: run full CI and verify exact-head GREEN; compare latest `main`; merge only green; inspect genuine `main` Self Evolution research artifact and factual sample counts; phase 2b collect prospective exact quote evidence only after contract audit.




**PUBLICATION RECOVERY + WATCHDOG FOLLOW-UP (2026-10-08):**
- [x] PR #525 merged as `ad5924f655c3eb5261274d4cd3c91aa9fd8b3124` after 7/7 successful workflows; remote full regression 1612/1612. Exact ledger chunk migration is production-proven: Update `37734745919` and later `37742821901` both passed build, commit and Pages deploy. Do not redo the size-limit repair.
- [x] Public metadata advanced from October 6 to `2026-10-08T07:24:35.345783+00:00` with 216 fixtures / 209 visible / 42 model-ready; successful hourly refresh `37745497239` followed. These counts describe that snapshot, not current guaranteed PLAYABLE availability.
- [!] By 11:00 UTC the core/market schedules had not produced a later refresh, although Neuron completed at 10:55. Existing watchdog listens only to cron and selected pushes; it has no completion trigger for independent Neuron/Player DNA jobs. New branch `fix/superbet-completion-watchdog` adds those completion wakeups, gated to successful main/non-PR sources before API reads. Existing 40-minute evidence freshness, active-run exclusion, quota and concurrency remain unchanged.
- [x] Pre-fix regression: completion trigger absent and three invalid completion sources incorrectly reach Actions lookup (4 failed / 26 passed).
- [~] Authorized core build rerun of `37742821901` is in progress to recover current data. The watchdog change still requires CI, fresh-main comparison and merge only green.
- **NEXT EXACT ACTION:** validate and merge the watchdog follow-up; confirm current core/Pages result and operator timestamps, then observe the next eligible completion wakeup. Never claim GitHub cron timing is guaranteed. No model math, probability, training, PLAYABLE, settlement, SHADOW/PROD or real-money changes.


**PUBLICATION INCIDENT (2026-10-07 23:00 UTC / 2026-10-08 Poland):**
- [x] Fresh main `0809d89fde799d94311713f034bda73679d9193a`; open PR #523 is unrelated.
- [x] Confirmed Update run `37683103451`, build `113005557830`: all generation and full-regression steps pass; commit push fails because `prediction_ledger_shadow.json` is 101.67 MiB, above GitHub's 100 MiB blob limit.
- [x] Regression fails before repair (ledger remains an unbounded blob); targeted publication/ledger tests pass after repair: 34/34. Real 103,792,840-byte source ledger round-trips across seven chunks with identical SHA-256. UI runtime smoke passes.
- [x] Branch `fix/prediction-ledger-publication` extends the existing `scripts/history_publication_chunks.py` owner. Legacy JSON remains accepted; existing workflow restore/pack boundaries now include the ledger. Pages drops only repository chunk copies after restoring the full JSON and archiving runtime sources.
- [x] Full local regression: 1612/1612 passed in 32.16s. Public meta still reports `2026-10-06T07:37:13.348536+00:00`.
- [ ] Full remote CI and production recovery.
- [x] User explicitly authorized GitHub publication and green-gated deployment on 2026-10-08. Rebased onto fresh main `984e582`; authorization blocker resolved.
- **NEXT EXACT ACTION:** publish the authorized source-only repair to `Abeel87/tenis-ai`, run full CI, compare fresh main, merge only green, and observe a successful Update-and-Pages plus current public data timestamp. Do not claim production recovery before this succeeds.
- **DO NOT REDO:** the identified size-limit diagnosis or prior unrelated model repairs. No history deletion/truncation, probability, training, PLAYABLE, settlement, SHADOW/PROD or real-betting change.

**Ostatnia aktualizacja checkpointu:** 2026-09-24

**READINESS EARLY PUBLICATION (2026-09-25, in progress):** PR #514 merged as `5d32b4b36a1eda53f1d5359d42d6179444a792c6` after 9/9 green checks and fixed the exact metadata projection plus Point Tape memory blowup. Production Player DNA #36153841589 built aligned evidence and passed projection, but its hour-long backtests overlapped Superbet data commit `25975b8714529943a3b3e9f97f383ffd40186c3e`; the new pre-push digest guard correctly rejected stale publication. Branch `fix/readiness-publish-before-backtests` publishes just the exact sidecar plus meta immediately after its guard, then runs heavy backtests separately. Hourly Superbet workflow completion triggers the same short guarded readiness portion; stale digests are skipped without publishing. NEXT: green PR, fresh-main comparison, merge, verify an hourly or push-triggered exact sidecar/meta commit, FAST Pages deploy, and equality of the live results/meta/sidecar digest. Legacy model_ready and all probability, PLAYABLE and iNeed$ logic remain unchanged.\n\n**READINESS META EXACT-SNAPSHOT REPAIR (2026-09-25, in review):** Branch `fix/readiness-meta-post-dna-projection` adds canonical `project_observability_meta()` after the Player DNA exact digest guard and commits `meta.json` with the SHADOW sidecar. A pre-rebase `origin/main:results.json` digest check aborts stale publication on every push retry. Regression tests cover aligned projection, unchanged legacy metadata, stale digest rejection, isolation rejection, workflow order and pre-push guard. This addresses observed `meta.semantic_readiness_shadow=N/D / RESULTS_SNAPSHOT_MISMATCH` despite later aligned sidecar. No probability/model math, PROD gate, PLAYABLE, iNeed$ or settlement changes. NEXT: complete PR CI, fresh main, merge only green, observe a post-merge Player DNA run and Fast Pages deploy, then verify `meta` digest equals sidecar digest and `available=true` only for current results; on later core refresh, temporary N/D remains safe until next Player DNA report.

**MODEL / DELIVERY READ-ONLY AUDIT (2026-09-25 11:02 UTC):** Main `381f4b11ef6ba5692521ddee492f808e50e6e3a3`, no open PR. Published meta updated `07:48:14Z`: 113 visible fixtures, 47 legacy model_ready, integrity PASS and Current calibration on an untouched CAL slice (1766 rows / 236 matches, Brier delta -0.00268, log-loss delta -0.00704). Production iNeed$ persisted EV has 0 formula discrepancies across 472 rows with odds/probability/EV (`p * odds * 0.88 - 1`); this checks arithmetic, not probability calibration. Player CatBoost SHADOW holdout n=1235 has Brier 0.21502 versus fixed ensemble-player 0.21328, and remains watch/zero production influence. Ensemble-Player Elo SHADOW Brier 0.21288 versus 0.21325 on same holdout, a small descriptive improvement only; match-winner subset n=38 is too small for promotion. Concrete delivery mismatch: current `readiness_engine_shadow.json` generated 08:18:24Z is evidence-ready, exact 113-result snapshot checked by Player DNA workflow, while published `meta.json` still says semantic readiness `N/D / RESULTS_SNAPSHOT_MISMATCH` because it was written earlier by core at 07:48 and Player DNA publication does not update meta. NEXT: isolated delivery repair to project the already-validated exact-snapshot readiness into meta after Player DNA guard, with fail-closed regression tests and no model math/PLAYABLE changes; separately accumulate same-market match-winner calibration/settlement before any model promotion. Do not infer model error from small holdout or EV alone.

**TRAINING ARCHIVE CAPACITY CHANGE (2026-09-25, production verified):** User authorized a bounded 250,000,000 → 300,000,000 B archive cap increase after verifying the Free organization's 1 GB Storage quota. Physical project Storage measured 561,343,745 B (archive 249,998,501 B; runtime 310,091,493 B; avatar 1,253,751 B). Branch `fix/training-archive-budget-300mb` changes only the two canonical SQL budget functions and preserves the independent 750,000,000 B project ceiling, reservation accounting, 2 latest complete manifests, pins and 168h grace. The previous inventory #36083363734 failed at 250,010,336 B and safely abandoned its manifest. Current GC audit #12 planned/deleted 0/0 B. NEXT: pass full PR CI, compare fresh main, merge only green, apply production migration, query both active function definitions and physical storage, then run a bounded inventory once and verify its manifest plus GC audit. If any gate fails, do not bypass it or claim green.

**TRAINING ARCHIVE 300 MB VERIFIED (2026-09-25 10:54 UTC):** PR #511 merged as `143a67b0adae334a0b91b591c836b0e1c24b0c8b` after all 7 PR workflows GREEN. Production migration `training_archive_budget_300mb` is applied: both canonical budget functions contain 300,000,000 B archive and unchanged 750,000,000 B project ceiling; anon/authenticated EXECUTE false, service_role true. Inventory rerun #36083363734 attempt 2 is GREEN, manifest complete at `10:53:46Z` with exactly 10,521/10,521 entries. Archive reserved 276,887,581 B; physical project Storage 588,232,825 B. Last observed GC #32 kept 2 manifests, 0 pins, grace 168h; apply #12 planned/deleted 0/0 B. NEXT: observe scheduled GC and later inventories; no retention shortcut or further limit increase by default. DO NOT REDO this migration or the successful inventory.

**PLAYABLE WATCHDOG CONTINUITY (2026-09-24):** PR #509 merged as `22ce7e6dfdcad58cbec5f4fa69cc3104ed660f65` after 5/5 green PR workflows. The scheduled Superbet refresh/watchdog did not fire on time after 11:57 UTC, so the 11:29:42Z operator context approached the UI's 90-minute expiry. The watchdog now also starts on an independent Player DNA SHADOW data push, using the existing active-run/freshness guard; it does not alter odds, models, risk or betting. Merge push triggered watchdog #36002097920 GREEN, which dispatched actual Superbet refresh #36002149645 GREEN. New operator context was generated at `2026-09-24T12:57:59.852105Z`, committed as `84fd2ef56ed93bea69044db75bcdf1f43f566085`: 49 matched matches, 41 verified offers, 27 projected PLAYABLE before Symphony. Fast Pages deploy #36002616650 completed GREEN including Deploy Pages. This proves the immediate recovery, not a guarantee against every future GitHub cron delay or a gap-free phone display. NEXT: observe the next independent Player DNA push and consecutive refresh boundaries; manually reopen the installed PWA to verify the visible cards. iNeed$ remains SHADOW/email only, with no automatic real bets.

**INEED$ LAST-DECISION VISIBILITY (2026-09-24):** PR #507 merged as `3e2c0b5424a298f97c53d45481440812dd59f49d` after iNeed$ SHADOW, UI/Project Health, CodeQL, and Delivery/security GREEN. Fast frontend deploy #35996817770 completed successfully with `Deploy Pages` GREEN. The staff UI now reads immutable `ineed_decision_snapshots` for the last runtime sync instead of deriving rejection counts from the latest 80 mutable `ineed_signals`. Detailed counts/examples are shown only when the snapshot count equals the runtime evaluation count; otherwise the UI reports `N/D`. `CORRELATION_LIMIT` is translated. The last observed sync at 11:32 UTC had 15 rejected match-winner decisions (6 total exposure, 5 correlation, 4 low EV); five earlier virtual bets remain pending. No model/EV/risk/SHADOW/email/settlement change. NEXT: verify the installed PWA on the user's device after reopening and observe another natural sync; do not claim the phone UI is verified from CI alone.\n\n**INEED$ MATCH-WINNER SCOPE (2026-09-24, production verified):** PR #504 merged as `bb52b3717726bce487fa25f1a80c7ff7287a8b64` after 1584/1584 local tests and 9/9 green CI workflows. Migration `ineed_match_winner_scope` is applied in production; the SHADOW insert guard accepts only an exact match-winner market/pick. Post-merge `iNeed$ SHADOW` rerun #35970211599 attempt 2 succeeded at 11:14 UTC. Runtime health is `OK`: 48 source signals, 18 retained `match_winner`, 30 filtered out; fresh Direct enrichment resolved 17 matches. The latest 18 persisted decisions are 5 `QUALIFIED`, 7 `LOW_EV`, 5 `TOTAL_EXPOSURE_LIMIT`, 1 `MARKET_NOT_AVAILABLE`, all on `match_winner`; five virtual bets are PENDING and `automatic_real_betting=false`. Builder SHADOW retains its separate first-set/game scope and reported zero eligible compositions. EV/model/probability/tax/risk/stake math and thresholds are unchanged. NEXT: observe normal future syncs and settlement; do not interpret SHADOW qualifications as realized profit or enable real betting. The unrelated archive 250 MB cap/grace blocker remains open.

**TRAINING ARCHIVE LIVE OBSERVATION (2026-09-24 11:53 UTC):** A failed inventory run #35993043797 hit the unchanged 250,000,000 B reservation guard (`250004438` B), and its own manifest was immediately abandoned. After the previous failed run #35857075162 reached the canonical 24h stale threshold, the existing `training_archive_abandon_stale_manifests(24)` abandoned exactly one manifest and removed its 10,000 incomplete entries. Observer #24 at `11:53:15Z` preserved the latest 2 complete manifests and 0 active pins, with 17 complete/15 expirable, 1172 current candidates / `148348524` B, and 52 grace-ready / `16032341` B. Exactly 50 newly eligible objects / `324698` B now have uninterrupted grace until `2026-10-01T11:53:15Z`. Physical archive remains 12372 objects / `249998501` B; latest apply #8 planned/deleted 0 objects / 0 B. No physical deletion or retention policy change. NEXT: let the remaining staged manifests each reach their 24h threshold, let the scheduled GC continue observations and exact apply audit; do not rerun inventory expecting success until eligible bytes are actually reclaimed. Superbet refresh #35993043446 and downstream Fast Pages deploy #35993476480 completed successfully, with operator context generated 11:29:42Z. Installed phone UI remains unverified.\n\n**TRAINING ARCHIVE STAGED-MANIFEST REPAIR (2026-09-24):** PR #502 passed all 7 workflows and merged as `d57d1b443541b6a9d521725c5bbe1707b55f0dc1`; full local regression was 1583/1583 GREEN. Production migration `training_archive_abandoned_manifests` is applied, `training-archive-gc` v2 and `training-archive-publish` v4 are ACTIVE. GC run `35970872835` attempt 2 is GREEN: preview retained newest 2 complete manifests, found 0 active pins, abandoned 33 staged manifests older than 24h, and observed 1122 candidates / `148023826` B with 52 grace-ready / `16032341` B. Apply audit #8 completed with 0 expired manifests, 0 planned/deleted objects and 0 deleted bytes, because no whole old complete manifest has all otherwise-unreferenced objects continuously grace-ready yet. Latest inventory `35979338710` still fails safely at reservation `250790282 > 250000000` B, but its new client cleanup immediately changed its own failed manifest to `abandoned`, proving new failures no longer leak live references. Production has 34 abandoned and 6 recent (<24h) staged manifests; the latter remain protected until the bounded reaper is allowed to process them. DB objects remain 12332 / `249736443` B. NEXT: let GC reap the remaining staged manifests after 24h and preserve a fresh 168h eligibility clock; reconcile the first later nonzero apply before rerunning inventory. Do not raise the cap, shorten grace, remove pins or directly delete objects.

**iNeed$ value visibility audit (2026-09-24):** Current `main` `edc687d76175b454de1cdcb923c3dabf18948be2` and active Supabase experiment `54139498-1ceb-46b4-bfe1-81cc3871499b` were checked read-only. Last persisted 45 distinct V1 signals: 30 `LOW_EV` (quoted odds 1.01–1.25; net EV −22.08% to −13.99%), 12 `ODDS_OUT_OF_RANGE` (1.003–1.009), 3 `MARKET_NOT_AVAILABLE`, zero `QUALIFIED`, zero bets. The workflow succeeds; no positive-value signal is being hidden by a failed sync. The UI currently buries these rejected rows in collapsed history and uses an uninformative empty message. A presentation-only fix on `frontend/ineed.js` surfaces last-sync rejection reasons and five expandable recent examples above the empty qualified list. Local syntax/diff check and 27 focused tests pass. NEXT: publish this isolated UI change, pass PR checks, merge only green, verify public Pages and installed PWA after reopening. Do not relax EV/risk thresholds or claim rejected signals are value. The separate Training Archive failure is budget `250790282 > 250000000` B; latest GC apply failed with SQL timeout `57014` after a safe preview showing 52 grace-ready objects / 16,032,341 B. Investigate that apply timeout under its own guarded repair before rerunning archive publication; never increase the cap or bypass grace/pins.

**PLAYABLE refresh-gap diagnosis (2026-09-23 20:10 CEST screenshot):** Published `main` snapshot `b8c2b79` has 204 matches and 31 backend final PLAYABLE matches. All 31 use operator context timestamp `2026-09-23T16:36:04.107281Z`, while Symphony was published at `17:17:37Z`. At screenshot time `18:10Z`, the operator context is ~94 minutes old and exceeds the UI's 90-minute safety bound. Isolated local branch `fix/playable-refresh-gap` changes the Superbet orchestration guard to count freshness from the operator work step start instead of workflow completion and uses a 40-minute guard horizon. Existing start-time/operator-verification safety remains unchanged. Local targeted tests: 28/28 GREEN. No push, PR, CI, production deployment, or real bet. NEXT: review actual Actions run durations and quota, publish branch only after remote-write authorization, pass full CI, then monitor source timestamp and UI PLAYABLE count around consecutive refresh boundaries.

**Active program:** Tenis AI logic/data/model reorganization.

**ACTIVE LOGIC/TASK:** `LOGIC-09 - Learning Integrity / Prediction Ledger` remains observation-only after the first post-midnight audit reached two leakage-safe complete-day folds for ALL and PLAYABLE; market breadth is still too thin for ranking/promotion. `LOGIC-12 - iNeed$ Bet Builder Redesign SHADOW` remains a parallel observation-only track with blocker `BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE` unchanged. Training Archive GC remains gated by the existing 168h grace.

**SUBSTEP:** PR #476 (`Add grace-safe training archive GC apply`) merged as `f0c345723e4ba9ca13a1d1581d347a7ddc9b0baa`. The production Supabase migration is present as `training_archive_gc_apply`; Edge Function `training-archive-gc` v1 is ACTIVE with `verify_jwt=false` and matches the canonical source contract revision `sha256:35602d6b005e10d2fc56d566efc06c56b5fffed128a478ab9e4ffa80ca0ab331`. Manual `Training archive retention GC` run #2 / `35780215151` completed SUCCESS on `cfe4ed973f4c543c76b7396fed0ba5b5f86130af`.

**ACTIVE BRANCH:** none for the completed archive repair. PR #502 is merged and production-deployed. No model, probability, threshold or iNeed$ calculation changes.

**UI PRESENTATION CHECKPOINT (2026-09-23):** PR #492 merged as `53d62e8e505b867a69653a0c63dc2b17e2c82fa1`. Match browsing keeps quick filters and search visible; tour/surface/sort are expandable with active-choice summary. Cards show published pick, probability and match status first; forecast, form and serve metrics remain available in expandable details. No model, offer, PLAYABLE or iNeed$ calculation changes. PR UI & Project Health, Symphony 2, CodeQL and Delivery/security checks are GREEN. Public GitHub Pages served updated `app.js` and `style.css` containing these controls after merge.

**UI FOLLOW-UP (2026-09-23):** User screenshots show iNeed$ WIN/LOSS/rejected history occupying a very long page and Symphony player-specific market labels omitting the published player name. PR #494 merged as `aa485064164575422d1fa5cf1384a132a844cfe2`: the UI groups loaded SHADOW bets by WIN/LOSS/other, splits rejected/expired by today versus older, shows compact expandable entries, and adds exact `player` context plus wrapped names in Symphony. The loaded batch remains capped at the existing 80-row queries; no backend, settlement, probability or risk calculation changed. PR iNeed$, Symphony, UI & Project Health, CodeQL and Delivery/security checks are GREEN. Post-merge Fast frontend deploy and UI & Project Health, CodeQL and Delivery/security are GREEN; public Pages served updated `ineed.js` and `app.js` with these controls.

**PWA UI DELIVERY FOLLOW-UP (2026-09-23):** User's installed Android app still displayed old iNeed$ full-size WIN/LOSS/VOID cards after PR #494 even though public Pages served the updated feature scripts. PR #496 merged as `2393875618b223d039f13455f2da8ba2bd1a19d4`: `frontend/sw.js` advances the UI cache key, bypasses HTTP cache for same-origin UI fetches, claims clients and reloads open windows on activation; `frontend/app.js` registers with `updateViaCache:'none'` and checks for updates on load, return to foreground and every five minutes while visible. No iNeed$ data, settlement, model, risk, or email path changed. PR checks and post-merge Fast frontend deploy/UI & Project Health/CodeQL/Delivery-security/iNeed$ SHADOW/Superbet watchdog checks passed. Public Pages `sw.js` was fetched on 2026-09-23 and verified to contain the new cache key, `no-store` fetch and client navigation. Installed phone UI has not been manually rechecked after closing and reopening the app; this is the next presentation acceptance check.

**ACTIVE PR:** none for runtime/model work. PR #496 is merged and public PWA worker verified; installed Android UI acceptance awaits a close/reopen and fresh screenshot.

**LAST VERIFIED MAIN:** `6e39b259a970b9f385ba7b9b4f665e29ba0ef62f` (2026-09-23 automated data refresh after PR #496 merge `2393875618b223d039f13455f2da8ba2bd1a19d4`). PR #492 Project Health, Symphony 2, CodeQL and Delivery/security are GREEN; post-merge Project Health is GREEN and public GitHub Pages serves updated JS/CSS. Earlier GC rerun #35833818115 attempt 2 completed preview and apply GREEN on PR #490 merge.

**INFRASTRUCTURE REPAIR CHECKPOINT:** PR #474/#475/#476 remain complete. PR #478 (`60ee8d56...`) fixed iNeed$ rejected-decision snapshots without changing calculations and was production-proven 20/20. PR #479 (`8470fd4b...`) added bounded retry/cache for transient runtime publisher GitHub OIDC failures and was production-proven on `market`. PR #480 merged as `4eed7d0a306b3603e880ccaf2664b4cd7d8754b4`, bounded `runtime-data-publish` signed-URL generation in batches of 8 and raised the client Edge response timeout from 60s to 120s without timeout retry. Edge Function `runtime-data-publish` v3 is ACTIVE; production `core` run `35800379357` activated generation `f308e99e-cb0a-464e-8644-48b0243d683d` with `311/311` physical objects and GC GREEN.

**TRAINING ARCHIVE CURRENT BLOCKER:** Scheduled GC run #35833818115 failed during the preview RPC with PostgreSQL `57014` (`statement timeout`); apply was skipped and no objects were deleted. A direct observer call at 2026-09-23 08:23 UTC completed with 1035 candidates and 0 grace-ready objects. PR #490 (`9df4c2c82f7bd7ef97d996a25048a4748cfbe446`) scoped a 30s timeout to the observer RPC and the production migration is applied (`proconfig` verified). Rerun #35833818115 attempt 2 completed preview observation #12 and apply audit #4; both GREEN. Observation #12 retained latest 2 complete manifests, 0 active pins, 1035 candidate objects / 147406562 B, 0 grace-ready objects; apply #4 expired 0 manifests and deleted 0 objects / 0 B.

**TRAINING ARCHIVE PRE-GRACE STATE:** the 250,000,000 B archive hard cap remains intentionally unchanged. Production GC apply audits prove pre-grace safety: apply #1 and apply #2 both completed with `expired_manifests=0`, `planned_objects=0`, `deleted_objects=0`, `deleted_bytes=0`. Current retention observation has `grace_ready_now=0`; earliest eligible grace maturity is `2026-09-23T14:05:13.238755Z`. Current eligible candidate inventory is 1035 objects / `147406562` B. No destructive deletion is legal before grace maturity.

**LOGIC-09 2026-09-23 UPDATE:** Persisted canonical artifact generated 06:45:56 UTC has 10956 rows, three-model common 997, common settled binary 324 and void 75. ALL and PLAYABLE each have 2 persisted temporal folds with zero train/test match overlap; SYMPHONY_SELECTED subsets still have one fold. Market breadth is still too thin for ranking.

**LOGIC-12 2026-09-23 UPDATE:** Persisted terminal evidence generated 06:53:27 UTC retains exactly 3 frozen candidates, with no exact whole-ticket settlement or payout; blocker `BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE` remains. Latest dynamic quote observation has zero eligible compositions and zero external requests.

**LOGIC-09 CURRENT EVIDENCE:** canonical source artifact `frontend/data/prediction_ledger_settlement_shadow.json` generated `2026-09-22T23:07:57.982774+00:00` has `rows=9854`, exact three-model common `960`, naturally settled common binary `308`, common void `75`, status `HAS_SETTLED_COMMON_ROWS`. Probability snapshots remain frozen and this remains descriptive SHADOW evidence only.

**LOGIC-09 TEMPORAL EVIDENCE:** deterministic read-only recomputation after UTC rollover (`as_of_utc_date=2026-09-23`) over the same frozen artifact rows gives `fold_count=2` for ALL and PLAYABLE. ALL fold 1: train `2026-09-20`, `train_rows=102`, late-settlement exclusions `15`, test `2026-09-21`, `test_rows=81`, overlap `0`. ALL fold 2: train through `2026-09-21`, `train_rows=190`, late exclusions `8`, test `2026-09-22`, `test_rows=110`, overlap `0`. PLAYABLE fold 1: train `48`, late exclusions `3`, test `10`, overlap `0`; fold 2: train `61`, late exclusions `0`, test `58`, overlap `0`. SYMPHONY_SELECTED and PLAYABLE_AND_SYMPHONY remain at `fold_count=1`.

**LOGIC-09 SAFETY:** Current/CatBoost/TabPFN probability snapshots stay frozen. `retraining_enabled=false`, `recalibration_enabled=false`, `ranking_enabled=false`, `promotion_enabled=false`; zero changes to probability/weights/thresholds/training/PLAYABLE/Symphony/Player DNA/Neuron/iNeed$.

**LOGIC-09 REMAINING GATE:** full DoD is NOT met. The chronology gate now has multiple folds for ALL/PLAYABLE, but market breadth remains thin: ALL common binary is `set1_total=181`, `match_total=112`, `match_winner=5`, `set2_winner=4`, and only `n=2` each for `set1_winner`, `set3_winner`, `total_sets`; PLAYABLE is `set1_total=91`, `match_total=22`, `match_winner=5`, `set2_winner=1`. Do not rank models, select a winner, change weights or migrate telemetry/runtime. Continue natural accumulation and keep small-N explicit.

**LOGIC-12 PARALLEL OBSERVATION / operator-evidence:** canonical `frontend/data/superbet_builder_terminal_evidence.json` generated `2026-09-22T20:29:18.033665+00:00` has 3 frozen candidates and still `settlement_result_available=false`, `payout_computed=false`, `result_inferred=false`. Events `15059409`, `15059413`, and `15063427` are all now `finished/finished`, but all remain `EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE`. Missing exact whole-ticket settlement stays `N/D`; inference from offer disappearance, event state or per-leg evidence remains forbidden.

### NEXT EXACT ACTION

1. PR #502, migration `training_archive_abandoned_manifests`, GC v2 and publisher v4 are completed and production-verified. Do not redo them.
2. Let scheduled GC reap each of the 6 remaining legacy staged manifests only after its 24h stale gate. Verify that active publisher manifests remain protected and failed new publications immediately become `abandoned`.
3. Preserve a fresh 168h continuous eligibility window for every object released by abandonment. The first newly released objects cannot mature before `2026-10-01T09:10:13Z`; later legacy staged manifests may extend their own windows beyond that time.
4. Reconcile the first later nonzero GC apply against latest-2 complete manifests, active pins, planned/deleted counts and bytes, then rerun Training Archive only after enough audited bytes have actually been reclaimed. Do not raise the 250 MB cap, shorten grace or delete objects directly.
5. Let normal Update/settlement runs continue natural LOGIC-09 accumulation. Do not backfill or recompute historical probabilities for Phase-4 evidence.
6. The normal 2026-09-23 Update persisted two leakage-safe folds for ALL/PLAYABLE. Continue factual per-market/per-population N accumulation; do not rank/promote models while market breadth remains thin.
7. Continue LOGIC-12 observation-only for the same 3 frozen operator-settlement identities. Missing exact whole-ticket terminal evidence remains `N/D`; never infer settlement or payout.
8. Without separate authorization do not change model math/probability/thresholds/weights/training/Player DNA/Surface Elo/Symphony/Neuron/PLAYABLE/current V1 risk/iNeed$ calculations or SHADOW->PROD.

# 2. Obowiązkowa checklista KAŻDEGO zadania / PR

## A. Start

- [ ] Sprawdź aktualny `main`/HEAD.
- [ ] Sprawdź wszystkie otwarte PR-y związane z tym obszarem.
- [ ] Sprawdź ostatnie workflow/CI i ostatni gate.
- [ ] Przeczytaj `AGENTS.md`.
- [ ] Przeczytaj `TENIS_AI_LOGIC_CONSTITUTION.md`.
- [ ] Przeczytaj odpowiedni wpis w `TENIS_AI_MODEL_DATA_REGISTRY.md`.
- [ ] Przeczytaj `TENIS_AI_EXECUTION_CHECKLIST.md` i `LIVE CHECKPOINT`.
- [ ] Ustal dokładnie jednego kanonicznego ownera błędu/logiki.
- [ ] Potwierdź, że nie istnieje aktywna równoległa implementacja tego samego rozwiązania.

## B. Audyt przed zmianą

- [ ] Odtwórz faktyczne zachowanie z kodu/runtime, nie z pamięci.
- [ ] Zapisz źródła wejściowych danych i provenance.
- [ ] Zapisz konsumentów wyniku.
- [ ] Zapisz guardy/walidatory przed i za modułem.
- [ ] Odtwórz problem testem, raportem lub audytem.
- [ ] Rozdziel: bug implementacyjny / problem danych / problem modelowy / debt dokumentacyjny.
- [ ] Jeśli zakres dotyczy probability/wag/progów/modelu — najpierw SHADOW/counterfactual i osobna autoryzacja.

## C. Implementacja

- [ ] Popraw/utwórz kanonicznego ownera **w miejscu**.
- [ ] Nie twórz nowego `vXXX`, wrappera ani równoległej runtime ścieżki jako obejścia.
- [ ] Nie zmieniaj downstream UI, aby ukryć zły upstream.
- [ ] Zachowaj provenance i reason codes.
- [ ] Dodaj testy regresyjne/leakage.
- [ ] Zaktualizuj registry/architekturę/checklistę, jeśli zmieniła się odpowiedzialność lub pipeline.

## D. Walidacja

- [ ] Testy jednostkowe są zielone.
- [ ] Testy sąsiednich modułów są zielone.
- [ ] Pełny wymagany pytest jest zielony.
- [ ] UI smoke jest zielony, jeśli zakres dotyczy UI/runtime danych.
- [ ] Project Health jest zielony.
- [ ] Security/CodeQL wymagane dla PR są zielone.
- [ ] Brak niezamierzonej zmiany probability/model math/settlement/PROD-SHADOW poza zakresem.
- [ ] Artifact odpowiada rzeczywistemu cache/snapshotowi, nie fixture'om testowym.

## E. Merge

- [ ] PR zawiera wyłącznie zakres zadania.
- [ ] Wszystkie wymagane CI = GREEN.
- [ ] Świeży `main` sprawdzony bezpośrednio przed merge.
- [ ] Jeśli `main` się przesunął — oceń drift; przebuduj/rebase i uruchom CI ponownie.
- [ ] Merge wykonany.
- [ ] Merge commit zapisany w checkpointcie.

## F. Po merge

- [ ] Sprawdź workflow/snapshot na `main`.
- [ ] Potwierdź brak regresji downstream.
- [ ] Odhacz zadanie w programie.
- [ ] Ustaw `NEXT EXACT ACTION` następnego etapu.
- [ ] Zapisz nowy checkpoint przed zakończeniem/przerwą.

---

# 3. PROGRAM GŁÓWNY — lista do odhaczania

## LOGIC-00 — Project Constitution / Operating Contract

Status: `[x] COMPLETED — PR #384 / merge 5269f6c467c3602fd6d557ed3385bc951008f07d`

Cel: jedna prawda o projekcie, jeden sposób pracy, jedna kolejność napraw.

- [x] AGENTS protocol.
- [x] Logic Constitution.
- [x] Model/Data Registry.
- [x] README canonical entrypoint.
- [x] ARCHITECTURE authority order.
- [x] Contract-doc tests.
- [x] Execution checklist + resume protocol.
- [x] Final CI green / fresh-main / merge / post-merge.

**Definition of Done:** spełnione.

---

## LOGIC-01 — Freshness Counterfactual

Status: `[x] COMPLETED — PR #386 / merge c9292b630c918f7fde0c9c48231629a10819c09f`

Cel: ustalić wpływ świeżości na Current player history bez zmiany PROD.

- [x] Baseline TASK 019.
- [x] Scenariusze 30/60/90/120/180/365.
- [x] PBP/Early Hold freshness osobno.
- [x] Zamrożone surface priors dla izolacji efektu historii gracza.
- [x] Profile/model-ready retained-lost + output deltas.
- [x] Brier/calibration `N/A` bez unbiased settled ledger — owner LOGIC-09.
- [x] Zero zmian PROD + CI + artifact.

**Definition of Done:** spełnione; nie wybrano cutoffu „na oko”.

---

## LOGIC-02 — Feature Provenance / Ranking Audit

Status: `[x] COMPLETED — PR #388 / merge 7328c0ec666272abf2a73b3b2a93d06f87d05704`

Cel: znać źródło, wiek i faktyczne użycie ranking features.

- [x] Fixture rank provenance.
- [x] TML `latest_rank` i `opponent_rank` provenance.
- [x] Current-vs-history i age audit.
- [x] Oddzielne counterfactuals fixture rank / historical rank / opponent rank.
- [x] Provenance report per player/match.
- [x] Zero zmian model math i zero promocji.

**Definition of Done:** spełnione.

---

## LOGIC-03 — Population / Priors Audit

Status: `[x] COMPLETED — PR #390 / merge abc13dd7204f69bcf32160c6e1f533f5e1ccc566`

Cel: sprawdzić mieszanie ATP/WTA/Challenger i wpływ globalnych priors.

- [x] Zmierzyć current `_surface_priors` per surface.
- [x] Rozbić priory na ATP / CH / WTA.
- [x] Zmierzyć różnice hold/break/serve/return.
- [x] Zmierzyć profile/fixture output zmieniające się przez mixed-population prior.
- [x] Sprawdzić produkcyjny fallback i oddzielić `surface_missing` od `<100` support.
- [x] Zaprojektować evidence-only hierarchy/fallback bez wdrażania do PROD.
- [x] SHADOW comparison.
- [x] Zero zmian model math / progu surface support 100 / PROD.
- [x] Artifact + pełne CI + fresh-main rebases po data-only bot drift + merge + post-merge green.

**Definition of Done:** spełnione dla fazy audytowej; brak promocji do PROD.

---

## LOGIC-04 — Context Engine SHADOW

Status: `[x] COMPLETED — PR #392 / merge c9acb27e48f41e9a5aaa0fa1bb041c65c5f45ab7`

Cel: jeden kanoniczny producent kontekstu meczu/historycznego rekordu, bez probability i bez runtime promotion.

- [x] Zdefiniować schema contextu.
- [x] current season / previous season / career prior.
- [x] days_old / opisowy freshness bucket.
- [x] surface / same_surface z missingness.
- [x] tour/event level tylko jeśli istnieje.
- [x] player rank / opponent rank / rank gap.
- [x] opponent tier wyłącznie jako opisowy rank band, nie strength score.
- [x] inactivity gap i obserwowalne położenie rekordu względem przerw bez diagnozy comeback/injury.
- [x] provenance/reason code dla każdego pola.
- [x] reużyć deterministic fail-closed identity resolution.
- [x] strict as-of i jawna date granularity.
- [x] brak zgadywania kontuzji/event level/aliasów.
- [x] SHADOW only; brak probability.
- [x] testy identity/time leakage.
- [x] artifact na dokładnym production cache/current snapshot.
- [x] pełne CI + fresh-main rebuild + merge + post-merge refresh/Pages GREEN.

**Definition of Done:** spełnione. Istnieje spójny SHADOW context schema z provenance; nie jest podłączony do Current/Player DNA/Symfonii ani PROD.

---

## LOGIC-05 — Opponent Strength Engine

Status: `[x] COMPLETED — SHADOW evidence / PR #394 / merge bd01b3c9bc1685a36c8762a2fd3ea64871fdc801`

Cel: wynik/statystyka ma znaczenie względem klasy przeciwnika.

- [x] Leakage-safe opponent-own-profile strength z strict-prior snapshotu.
- [x] Opponent strength bez ręcznego prostego przelicznika rankingu.
- [x] Ranking tier / continuous rank jako oddzielny benchmark, nie strength definition.
- [x] Surface-aware opponent strength z jawna missingness.
- [x] Event/tour context tylko z hard provenance; brak event level nie jest zgadywany.
- [x] Performance-vs-expectation residual jako SHADOW evidence.
- [x] Chronological holdout + 3-fold walk-forward validation.
- [x] Common sample vs profile/rank i lean-stateful baseline.
- [x] Dedykowane evidence w istniejącym Point Tape artifact.
- [x] SHADOW only; candidate replacement/promotion pozostają false.

**Definition of Done:** spełnione dla SHADOW evidence; szczegóły i metryki: `TENIS_AI_CHECKPOINT_LOGIC_05.md`. Brak promocji do PROD.

## LOGIC-06 — Opponent-Adjusted Serve / Return / Hold / Break

Status: `[x] COMPLETED — SHADOW evidence / PR #397 / merge c1d1328b38a9b71fc2b4b15f4dc5f34c86703200`

Cel: Player DNA evidence rozróżnia surowe procenty od kontekstu siły rywali.

- [x] Expected serve z strict-prior player serve + opponent return counts.
- [x] Serve residual.
- [x] Expected return z strict-prior player return + opponent serve counts.
- [x] Return residual.
- [x] Hold residual.
- [x] Break residual.
- [x] Overall i same-surface split.
- [x] Jawne support/confidence metadata diagnostyczne, nie strength proxy.
- [x] Raw vs adjusted na jednym common chronological holdout + walk-forward.
- [x] Brak nadpisania Player DNA PROD; no runtime activation.

**Definition of Done:** spełnione dla SHADOW evidence; szczegóły i metryki: `TENIS_AI_CHECKPOINT_LOGIC_06.md`. Brak promocji do PROD.

## LOGIC-07 — Player State

Status: `[x] COMPLETED — SHADOW evidence / PR #399 / merge 7d5e66a07ba400473302966e40592a591dfd71c3`

Cel: oddzielić „kim gracz zwykle jest” od „jak gra teraz”.

- [x] Current-season level.
- [x] Recent form jako descriptive evidence; bez wymyślonego magic freshness cutoff i bez probability activation.
- [x] Previous-season baseline + season delta z missingness.
- [x] Ranking momentum/provenance.
- [x] Serve trend.
- [x] Return trend.
- [x] Opponent-adjusted performance trend reużywający LOGIC-06.
- [x] Current-surface state z jawnie nieznanym surface bez inferencji.
- [x] Inactivity/gap scenarios 30/60/90/180 bez zgadywania przyczyny medycznej.
- [x] Matches-since-observed-gap evidence bez diagnozy comeback cause.
- [x] Support/confidence/provenance.
- [x] Read-only comparison z obecnym Current Engine; no write/recompute/runtime activation.

**Definition of Done:** spełnione jako descriptive SHADOW evidence. Finalny artifact i isolation contract: `TENIS_AI_CHECKPOINT_LOGIC_07.md`.

## LOGIC-08 - Readiness Engine

Status: `[x] COMPLETE - approved audit / SHADOW observability scope merged and post-merge verified`

Cel: koniec z jednym prostym `model_ready` dla wszystkiego, bez nieautoryzowanej migracji PROD.

- [S] Identity readiness - SHADOW semantics/reason codes gotowe; bez PROD migration.
- [S] Freshness readiness - brak zatwierdzonego cutoffu pozostaje jawnie `UNKNOWN`.
- [S] Current-season readiness - SHADOW evidence semantics gotowe.
- [S] Surface readiness - SHADOW evidence semantics gotowe.
- [S] Serve/return readiness - SHADOW evidence semantics gotowe.
- [S] PBP readiness - istniejacy jawny PBP contract reuzyty bez zmiany runtime.
- [S] Opponent-context readiness - SHADOW evidence semantics gotowe.
- [S] Market-specific readiness - tylko jawne PBP/Early Hold requirements; generic markets nadal `UNKNOWN`.
- [S] Reason codes - deterministic ordering + provenance/support.
- [x] Legacy consumer inventory - PR #403.
- [x] Consumer requirement matrix - 22 legacy tokens / 19 source lines; PR #406.
- [x] Exact-snapshot sidecar delivery - PR #410 + post-merge Player DNA proof.
- [x] R12/R13 additive meta observability - PR #411 + post-merge Update proof; stale/missing/misaligned = explicit `N/D`.
- [x] UI bez wymyslania danych - R18/R19 merged in PR #412; admin/diagnostics show backend SHADOW tri-state counts or N/D only; R16 remains legacy/NO MIGRATION.
- [x] Migration plan from legacy boolean - consumer-specific requirements are documented; runtime/learning migrations are explicitly deferred to LOGIC-09 and guard ownership to LOGIC-10 rather than silently promoted.

**Definition of Done:** met for LOGIC-08 approved scope. Exact-snapshot SHADOW evidence, provenance, fail-closed metadata observability and additive UI observability are merged and verified. No runtime/learning gate replacement was authorized in this logic. R07/R08/R11 continue in LOGIC-09; R14 continues in LOGIC-10.
---

## LOGIC-09 - Learning Integrity / Prediction Ledger

Status: `[~] ACTIVE - phases 0-4 merged and production-proven; natural common-set evidence is binary n=308; two closed complete-day folds exist for ALL/PLAYABLE, while market breadth remains too thin for robust ranking/promotion`

Goal: compare frozen prospective model outputs on the same exact population without selection leakage.

- [x] Phase-0 owner/population inventory + real selection-bias proof (`TENIS_AI_LEARNING_INTEGRITY_AUDIT.md`, PR #414; docs closeout #415).
- [x] Minimal frozen-ledger/common-test-set invariants documented and contract-tested.
- [x] Phase-1 immutable pre-selection prediction ledger for all supported prospective candidates (PR #416).
- [x] Phase-2 exact PLAYABLE/Symphony population evidence with strict chronology; missing evidence = `N/D` (PR #418/#419).
- [x] Phase-3 exact terminal settlement common-set owner using existing canonical terminal/scorer semantics; zero network, zero source-ledger mutation (PR #420).
- [x] Natural evidence maturity refreshed through the 2026-09-22 source artifact: `rows=9854`, exact common `960`, common binary settled `308`, common void `75`, status `HAS_SETTLED_COMMON_ROWS`; PLAYABLE common binary `119`. Zero retroactive prediction/backfill/recompute.
- [x] Phase-4 PR #470 merged as `361e279e83ebb25a2986374906da215dd350ccaa`: descriptive Brier/log-loss/accuracy + fixed 10-bin calibration on the identical common sample, per population and per market; no ranking/winner/promotion. Post-merge Update #841 and generated-artifact guard are GREEN.
- [x] Leakage-safe chronological audit implemented and production-proven: complete UTC days only, expanding prior-day train -> next complete-day test; train labels require `settled_at < test_day_start`. Post-midnight deterministic audit has two folds for ALL/PLAYABLE with zero train/test match-key overlap; fold 2 tests `2026-09-22` with ALL `test_rows=110` and PLAYABLE `test_rows=58`.
- [~] Market evidence is not broad yet: ALL common binary `set1_total=181`, `match_total=112`, `match_winner=5`, `set2_winner=4`, with `set1_winner`/`set3_winner`/`total_sets` at `n=2`; PLAYABLE is concentrated in `set1_total=91` and `match_total=22`. Keep small-N explicit.
- [x] Accumulate enough full UTC days / natural exact settlements to establish multiple temporal folds for ALL and PLAYABLE (2 folds as of UTC 2026-09-23 rollover).
- [ ] Continue natural exact settlement accumulation for broader market coverage and additional periods/populations.
- [ ] Audit/migrate telemetry only after broader evidence and separate authorization.
- [ ] Do not change ensemble weights or SHADOW->PROD; Phase-4 defines no minimum promotion threshold and no model winner.

**Definition of Done:** infrastructure, factual common-set metrics and multiple complete-day folds now exist for ALL/PLAYABLE, but full LOGIC-09 DoD is NOT met because market breadth outside `set1_total`/`match_total` remains too thin and Symphony-selected chronology still has only one fold. No ranking or promotion follows from current Phase-4 evidence.

---

## LOGIC-10 - Guard Ownership / Dead Logic Audit

Status: `[x] COMPLETE - PR #422 / #423 / #424 merged; final post-merge publication evidence recorded in closeout`

Cel: guardy chronia kontrakty, ale nie walcza z legalnym outputem innych modulow ani nie udaja roznych ownerow, gdy wywoluja ten sam verifier.

- [x] Lista aktywnych named workflow guard/validation invocations i owner kazdego: phase-3 local inventory = 92 invocations across 28 workflows, exact-set contract enforced by `tests/test_guard_ownership_audit_contract.py`.
- [x] Input/output/reason code i kolejnosc wykonania: BO5, presentation guards, 52 inline Python validators, PLAYABLE/Superbet runtime validation and quota-state exception mapped.
- [x] Wykrycie sprzecznych/duplikowanych guardow: BO5 collision fixed in #422; legacy presentation aliases fixed in #423; producer-vs-validator naming fixed in #424.
- [x] Audyt BO5 dead logic: canonical Current Engine BO5 output, Market Lab BO5 boundary and Serve Props BO5 boundary mapped, merged and post-merge verified.
- [x] Usuniecie/naprawa tylko po testach regresyjnych: phase 3 focused 24/24 and full local 1349/1349 GREEN; exact-head PR CI GREEN before merge.
- [x] Zero guardow naprawiajacych inne guardy / zero fake-owner aliases: semantic scan and phase-3 contract are merged in #424.

**Definition of Done:** COMPLETE. Every audited named guard has one explicit purpose/owner; historical guards no longer erase legal canonical output, fake-owner aliases are removed, and producer-vs-validator semantics are contract-tested.

---

## LOGIC-11 — Frontend Ownership / Data Provenance

Status: `[x] COMPLETE - phases 1-7 merged through PR #432; exact-head CI and post-merge production proof GREEN`

Cel: UI pokazuje dokładnie to, co backend faktycznie wyprodukował.

- [x] Runtime/import ownership mapped: `scripts/build_delivery.mjs` producer; `frontend/app.js` shell/list/detail; `presentation-data.js` presentation/data entrypoint; history/admin/iNeed$ feature owners explicit.
- [x] One shell owner for match list/detail: `frontend/app.js`; feature extensions remain separate and explicit.
- [x] Jeden effective PLAYABLE presentation gate: `TenisPresentation.availability()` composes backend final authority with `playable-ui.js` operator/signature validation; no competing active UI decision path found.
- [x] Historical frontend owners are physically absent; phase 6 removed ghost workflow/health references and phase 7 stops booting six no-consumer calculation helpers.
- [x] N/D zamiast sztucznego zero.
- [x] SHADOW jawnie oznaczone.
- [x] Timestamp = backend `generated_at`; phase 5 merged in PR #430.
- [x] Żadnych frontendowych probability/H2H/odds/identity fallbacków.
- [x] `ARCHITECTURE.md` owner map corrected in merged phase 1.

**Definition of Done:** COMPLETE. PR #432 merged as `5ad329b0...`; exact-head 10/10 GREEN. Post-merge Update+Pages #815 passed canonical UI, Symphony/PLAYABLE and final full regression, published refreshed data and deployed Pages. Follow-up Superbet publication and iNeed$ SHADOW are GREEN on the resulting current line.

---

## LOGIC-12 — iNeed$ Bet Builder Redesign

Status: `[~] ACTIVE - Phase-4/5 runtime evidence and guarded persistence/sync contract are merged/production-proven; exact pricing/terminal evidence collection is active; reservation enable flag remains OFF; settlement is blocked by `BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE`

Cel: iNeed$ ocenia rzeczywisty finalny Bet Builder, nie niezależne single.

- [x] Potwierdzono current state: iNeed$ ocenia/stakuje/rozlicza pojedyncze playable signals, nie finalną kompozycję BB.
- [x] Potwierdzono final Symphony composition jako jednostkę wejścia.
- [x] Zdefiniowano additive SHADOW composition record: composition id + min. 2 legs + canonical match/operator provenance.
- [x] Joint probability jest wyłącznie passthrough z Symfonii; iNeed$ SHADOW nie liczy nowej probability.
- [x] Exact verified Superbet combined odds: phase 2 curated pre-priced rows + phase 3 dynamic `v2/getSgaOddPrice`; zero leg-odds multiplication.
- [x] Phase 4: EV/Kelly/risk/stake całego buildera + jedna niepersistowana `SHADOW_PROPOSED` reservation per `composition_id`; PR #437 merged as `9a0ad2fe84298e847a2af7a6bc5afabdafee6963`.
- [x] Phase 5: pure `builder-ticket` SHADOW envelope freezes exact composition, quote provenance, Phase-4 economics and one reservation proposal; output cannot resemble current V1 signal and explicitly claims no persistence/settlement readiness.
- [x] Phase 1-5 remain SHADOW and are runtime-produced by the canonical Superbet refresh/scoped runner; PR #456 merged and normal production workflow proved summary-only evidence with zero builder rows/reservation writes and no V1/email regression.
- [x] Separate builder-ticket persistence/sync contract merged in PR #457: dedicated OIDC Edge action + existing atomic writer, double-gated by `builder_reservation.enabled=true` and exact contract version. Production flag remains absent/false, so current runtime performs zero builder writes.
- [x] Exact pricing/reprice evidence plumbing is merged and production-proven through PR #465-#469: separate bounded dynamic sidecar, no leg-odds multiplication, fail-closed first non-PR delivery `NO_ELIGIBLE_COMPOSITIONS` with 0 external requests.
- [~] Bounded read-only terminal operator-evidence observation is active for the same 3 frozen identities through their 96h windows; latest published sample still has 0 exact whole-ticket result hits. Missing evidence = `N/D`; no result/payout inference.
- [ ] One whole-ticket BB settlement with exact operator semantics for WIN/LOSS/VOID/PUSH/CANCEL/retirement and leg-void behavior remains blocked until exact whole-ticket operator evidence exists.
- [ ] Backtest na zamrożonych ofertach/operator context, jeśli dane pozwalają.

**Phase-5 merge proof:** PR #438 exact head `ac9d6d02...` passed 8/8 GREEN required workflows and merged as `73926853e4439f41a97c08ffd4be93f55e16c24f`. Post-merge isolation proves zero runtime/Supabase/settlement consumer.

**Definition of Done:** ekonomika iNeed$ odpowiada temu samemu finalnemu produktowi, który użytkownik faktycznie może zbudować w Superbet, z jawnie zweryfikowanym combined price i one-ticket settlement. Phase 5 closes only the pure ticket-envelope contract; persistence and settlement remain separate future phases.

# 4. CHECKPOINT PRZERWANIA — obowiązkowy przed zakończeniem/przerwą

Przed zakończeniem dłuższej sesji albo gdy istnieje ryzyko limitu/przerwania zapisz co najmniej:

- **ACTIVE LOGIC/TASK**,
- **SUBSTEP**,
- **BRANCH**,
- **PR**,
- **LAST VERIFIED MAIN**,
- **LAST COMPLETED WORK**,
- **CHANGED FILES**,
- **TEST STATUS**,
- **CI STATUS**,
- **BLOCKERS**,
- **DO NOT REDO**,
- **NEXT EXACT ACTION**,
- **RISKS / HARD BANS**.

Jeżeli nie można zaktualizować pliku przed nagłym przerwaniem, następny agent ma odtworzyć checkpoint z GitHub PR/commits/workflowów i dopiero wtedy kontynuować.

---

# 5. PROTOKÓŁ WZNOWIENIA NOWEGO CZATU

1. Odczytaj `AGENTS.md`.
2. Odczytaj `TENIS_AI_LOGIC_CONSTITUTION.md`.
3. Odczytaj `TENIS_AI_MODEL_DATA_REGISTRY.md`.
4. Odczytaj ten plik i `LIVE CHECKPOINT`.
5. Sprawdź żywy GitHub: `main`, branch, PR, CI, najnowsze commity.
6. Porównaj GitHub z checkpointem.
7. Jeśli bot przesunął `main`, oceń tylko drift względem aktywnego brancha; nie resetuj całej pracy.
8. Potwierdź checkboxy dowodami.
9. Kontynuuj od `NEXT EXACT ACTION`.
10. Nie rozpoczynaj wcześniejszego etapu od zera bez dowodu, że checkpoint był błędny.
11. Nie przeskakuj do kolejnego LOGIC, dopóki Definition of Done aktywnego etapu nie jest spełnione albo jawnie deferred/blocked przez właściciela projektu.

---

# 6. Zasada anty-chaos

Jeżeli podczas zadania pojawi się nowy problem:

- jeśli blokuje bieżący etap — wpisz jako blocker i napraw w jego ownerze,
- jeśli nie blokuje — dopisz do właściwego LOGIC/P0/P1/P2 w registry/checkliście,
- nie twórz nowej architektury na boku,
- nie zmieniaj kolejności programu bez zapisania powodu,
- nie uznawaj problemu za rozwiązany tylko dlatego, że UI przestało go pokazywać.

Celem checklisty jest to, żeby **stan projektu był w repo, a nie w pamięci pojedynczego czatu**.


## Active incident: Symphony hourly history — 2026-09-28

- [x] Fresh main checked: db764d9278a2b9e71a78300f0cc8a885f971c8db; open PRs are dependency updates only.
- [x] Root cause reproduced: hourly market refresh lacks history restore, while Symphony reads history.json; run 36386926310 reported zero training rows.
- [x] Regression fails on original workflow and passes with restore before consumers plus pack before git add.
- [~] Branch fix/symphony-hourly-history-20260928: workflow/test/registry repair; CI and production verification pending.
- [ ] Merge only after green CI and fresh-main comparison.
- [ ] Verify next real hourly refresh has restored history, model support and published recommendations (counts are data-dependent).
- Coverage audit: same run sees 437 app fixtures, 427 provider fixtures, 53 operator matched candidates, 40 verified contexts, 18 current prematch Symphony fixtures. Direct resolves 8/8 candidates, below its existing 64 limit; do not claim raising that cap fixes coverage.
- DO NOT REDO: PR #519 publication repair; no model math, threshold, weight, training-algorithm, settlement or SHADOW promotion changes.
- NEXT EXACT ACTION: finish this PR CI, fresh main, merge green, verify real hourly output; then investigate remaining exact provider overlap with evidence.


## LIVE coverage continuation — 2026-09-28
- [x] PR #520 history repair deployed; hourly run 36419314590 still has ready model, 33305 training rows; FAST Pages 36391355461 and 36419946806 success.
- [x] Snapshot 2de5456e6a133533c0d22f5c81626511089161af: 381 app rows; at 12:08Z 180 future rows; 19 verified operator contexts, 5 future Symphony rows, 4 PLAYABLE. Counts decrease with start times; no zero-history regression.
- [x] Root diagnostic gap reproduced: 12 early NO_SAFE_NAME_MATCH examples suppress later TIME_GUARD evidence despite 65 time rejections. Local tests fail before repair and pass 2/2 afterwards.
- [~] Branch audit/superbet-time-rejection-evidence: bounded reason-specific evidence, unchanged matching decisions; CI/merge pending.
- [ ] Inspect next real report's live.samples_by_reason.TIME_GUARD and compare app/provider timestamps before proposing any schedule repair.
- DO NOT REDO: history restoration; do not relax identity/time gates or manufacture recommendations. Remaining operator coverage is not yet repaired.
- NEXT EXACT ACTION: green CI -> fresh main -> merge -> inspect next normal operator refresh evidence.


## LIVE CHECKPOINT — current-offer queue, 2026-09-29
- ACTIVE TASK: repair missing current operator coverage; canonical owner `superbet_market_core.py`.
- LAST VERIFIED MAIN: `e4264856fac49587f79d77021b29161dce088c31`.
- [x] PR #521 merged as 16233bd82c83aa682cb033f8aa22bec8869df3bc; full production run 36438771639 succeeded.
- [x] Current production hourly 36512101984 and FAST deploy 36513516139 succeeded; Symphony at 02:25Z ready, 34399 training rows, 68 verified fixtures / 8900 scored selections.
- [x] Examined TIME_GUARD evidence: only two next-day 6-hour discrepancies; keep time checks unchanged.
- [x] Reproduced 48-due/24-attempted queue truncation; removed per-refresh slice in canonical retrieval owner. All four local regressions pass, old implementation fails full-queue test.
- BRANCH: `fix/drain-current-offer-queue`; PR creation/full CI pending.
- CHANGED FILES: core, `tests/test_superbet_offer_queue.py`, registry, this checkpoint.
- [ ] Green full CI, fresh main, merge, verify next production request queue and delivery.
- BLOCKERS: remaining unmatched source identities and offers absent from provider are not solved by removing the queue slice. No claim all 430 fixtures are playable.
- DO NOT REDO: history restoration and PR #521 diagnostic evidence; keep exact identity/bookmaker/time/line guards, monthly budgets, model math, thresholds and settlement unchanged.
- NEXT EXACT ACTION: inspect this PR CI, merge only green against fresh main, then verify real refresh `direct_fixture_requests_due/this_refresh/skipped_budget` and downstream Symphony data.


**SELF EVOLUTION SHADOW PHASE 1 (2026-10-08; separate authorized new feature):**
- [~] Branch `feature/self-evolution-shadow-research` from fresh main. Read-only autonomous ensemble research implemented in `backend/self_evolution_shadow.py`, tests in `tests/test_self_evolution_shadow.py`, daily isolated artifact workflow and canonical docs. All existing probability/math/weights/settlement and SHADOW/PROD gates remain unchanged.
- [x] Synthetic local six-test suite initially GREEN (chronology, source SHA, duplicate identity, minimum independent matches, no PROD influence). This is local targeted evidence, not full CI or live data proof.
- [ ] Open draft PR; run required CI and check fresh-main; merge only after all mandatory gates are green. Observe first post-merge scheduled/manual SHADOW research artifact and label shortage of prospective settlement as `COLLECTING_VERIFIED_HISTORY` rather than a learned winner.
- **NEXT EXACT ACTION for Self Evolution:** verify PR checks and new trainer on production ledger in isolated SHADOW run; no auto-promotion, no betting, no live UI claims. Future phases require strict pre-match operator odds evidence before EV optimization. This feature does not supersede publication-watchdog recovery checkpoint above.


## LIVE CHECKPOINT — authorized upstream settlement repair, 2026-10-12
- ACTIVE TASK: fix source winner-label corruption behind iNeed probability inflation.
- AUTHORIZATION: user approved Symphony repair, then explicitly approved all required history settlement/label corrections and retraining; preserve original history and iNeed ledger.
- BRANCH: `fix/symphony-probability-calibration-20261012`; initial base d796756e15528ba523a629bdf9b7314b61204cba.
- [x] Canonical failing reproducer: reversed full-name winner returns miss; nine regression failures before repair.
- [x] Unique exact-name settlement owner; auditable idempotent archive correction; iNeed resolver consolidation; unresolved training identity exclusion.
- [x] Existing iNeed experiment 3: all 22 settled outcomes independently checked, zero mismatches; no bankroll/DB writes.
- [x] Final local full suite: 1661 passed. Temporal replay: 110 later independent matches, paired Brier 0.295804 -> 0.261147 (still worse than 0.25 baseline; no financial superiority claim).
- [x] PR #535 exact head 8525f8ab4acd7641899c0b7b6a826e2ed5a1c146: 13 successful checks, shadow-sync intentionally skipped on PR. Fresh main remained d796756; merged green as 269ea958c2062706a817857e8532065f2f39556e.
- [x] Normal core reconciliation/training and Pages run 38225966332 succeeded, including final full regression and deploy_pages job 114744768701.
- [x] Verified main 2977a479de901007c60631083c9327c0d19bd628: published Symphony stats generated 2026-10-12T11:24:22Z, model ready, symphony2-learning-6; 91391 training / 22315 validation observations, including 30782 / 9082 corrected labels. Counts are observations, not independent matches.
- [x] Post-deploy iNeed experiment 3 remains 9 WIN / 13 LOSS / 2 PENDING, net -40.0559 PLN; runtime OK at 09:31:55Z, automatic_real_betting=false. No reset or direct DB writes performed.
- DO NOT REDO: audits on `audit/ineed-learning-readiness-20261012`; no reset of experiments or speculative probability formula.
- NEXT EXACT ACTION: source repair is deployed; collect prospective post-repair evidence before any profitability or promotion claim. Self Evolution and Neuron readiness remain separate SHADOW evaluations. No repeated source repair/replay needed.
- RISKS: retrospective quality improvement is not financial/prospective superiority; Neuron/Self Evolution and real betting remain unpromoted.
