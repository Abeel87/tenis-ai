# Analysis development — 2026-11-11

Owner authorized all eight product ideas. Base: c71abdb5dd7c9797529dd67080b8c0f6f8fdb3a2.
This record describes implementation; the live checklist owns release status.

| Feature | Canonical implementation | Evidence/limit |
|---|---|---|
| Why this pick | app.js decision card | Existing exact-score scenario, recommended composition, joint probability, per-leg loss of joint mass; no invented rationale |
| Builder comparison | symphony2_engine + ineed_builder_shadow + presentation-data | Exact shared-state probabilities; exact current combined/subset quotes only; existing net economics at 1 PLN; SHADOW, no ranking/reservation effect |
| Data quality | readiness_engine_shadow + build_delivery | Profile source counts, surface sample, age and separate readiness dimensions; absent source != zero; exact snapshot alignment |
| Learning progress | neuron + admin overview | Model-version groups, surface/tour, common frozen AutoLearn baseline, Brier/log loss; market is match winner; older unknown context stays UNKNOWN |
| Opponent-context form | player_dna_player_state_shadow + match stats | Existing adjusted serve/return, season/surface support, inactivity, strict-prior observed 48h starts; minutes N/D; SHADOW |
| Prematch timeline | symphony2_tracker | Separate idempotent observation journal, exact fixture identity, source/observation time, max 32 observations/fixture; never training or settlement |
| Postmatch review | history-ui + presentation-data | Frozen expected markets vs existing terminal labels and score; unresolved/void separated, no invented causal explanation |
| Targeted history | history_player_priority_backfill + admin diagnostics | Existing exact IDs/quotas/cooldowns; nearest upcoming start breaks equal-coverage ties; per-player PBP download/parse yield; model-history gain N/D |

No new model, probability, ranking, threshold, weight, source identity policy,
settlement logic, real bet or auto-promotion. Recommendations are not chosen by
the diagnostic EV panel. Removing a leg is an informational comparison, not an
instruction to split a required Bet Builder into independent bets.

Publication files keep raw match objects losslessly. Heavy observations/context
load only with match details; history-supply loads only in admin routes. Same
inputs produce the same index. UI data requests remain behind existing auth and
role handling. Service worker release changes ensure refreshed static assets.

## Existing release blocker found

FAST deployment run 42995748539, job 130439311641 failed on 2026-11-11 in
`runtime_snapshot.py::verify`: `Duplicate entries or archive larger than 1 GiB`.
The captured main has 236,431,278 top-level JSON bytes and 853,612,926 bytes in
four restored chunk manifests, total 1,090,044,204 bytes (>1,073,741,824).
The canonical archive now streams pack/hash/restore, with a 4 GiB expanded-byte
budget and 4 MiB manifest cap. Duplicate/path/type/membership/checksum guards
remain; all bytes verify before first restore write. The complete archive is
still preserved before public-only exclusions. Supabase object limits are unchanged.

## Verification

- `python -m unittest tests.test_analysis_development tests.test_runtime_snapshot_capacity -v`: 13 pass locally.
- `node tests/analysis_ui_contracts.mjs`: pass; positive/negative quote freshness,
  kickoff, source identity, missingness, escaping, immutable review, deterministic
  delivery, full-app routes, roles and logout on isolated temporary fixtures.
- Browser suite extended to Builder/changes/stats/decision panels at 320/412/1280px
  and retained screenshots. Full CI and production evidence tracked in checklist.
- Local full pytest and Chromium execution require unavailable dependencies;
  GitHub's normal dependency-equipped checks are the full-suite authority.

## Known limits and rollout

New journal entries, Neuron segments and Player State activity appear when their
normal producers next publish. Existing frozen predictions are not rebuilt. There
is no validated match-duration source, so minutes stay N/D. Exact operator quotes
can be absent and no synthetic replacement is generated. Historical source-age
readiness remains UNKNOWN until its separate evidence-based policy is selected.
No profitability or superiority claim follows from a small sample. This release
does not claim to repair missing upstream history or intermittent GitHub outages.
