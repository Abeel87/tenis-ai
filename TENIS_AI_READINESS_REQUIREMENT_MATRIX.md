# Tenis AI — LOGIC-08 consumer readiness requirement matrix

Status: **PHASE-3 AUDIT CONTRACT / ZERO RUNTIME WIRING**

Audited main: `eec6483ed942ebab9193ef4bd4681ac352f3490c`.
Canonical semantic owner: `backend/readiness_engine_shadow.py`.
Legacy consumer inventory: `TENIS_AI_READINESS_CONSUMER_MAP.md`.

This matrix defines what each legacy `model_ready` use-site would need before any migration. It does **not** replace a gate, select a freshness cutoff, promote SHADOW, or change probability/training/PLAYABLE/iNeed$.

## Global rules

- Legacy `model_ready` remains unchanged until a consumer has its own validated sufficiency policy.
- Missing policy or unaligned evidence means **UNKNOWN / NO MIGRATION**, never inferred `READY` or `NOT_READY`.
- `identity` may fail closed only on deterministic identity evidence; no fuzzy aliases or provider-ID namespace guessing.
- `freshness`, `current_season`, `surface`, `serve_return` and `opponent_context` remain policy-UNKNOWN where LOGIC-08 has evidence but no approved sufficiency threshold.
- `rank_context` can be `READY` only under the existing hard presence contract in the SHADOW engine; it is not a universal quality verdict.
- PBP `market_evidence_v940.market_ready`, Symphony `learning_model_ready`, and Superbet operator availability remain separate contracts.
- Learning consumers also depend on LOGIC-09 prediction-ledger integrity; guard consumers may depend on LOGIC-10 ownership work.

## Runtime / collection consumers

| ID | Exact use-site | Current legacy effect | Required semantic contract before migration | Market / local contract | Evidence owner | UNKNOWN / missingness rule | Policy status | Risk / decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | `backend/history_tracker.py:L145` | Drops the whole pre-match history entry when legacy readiness is false. | `identity`; all other dimensions must be attached per prediction/market rather than as one global boolean. | Frozen prediction + market identity + scheduled-time cutoff. | Current prediction producer + future LOGIC-09 ledger. | Any market without its own sufficiency policy remains UNKNOWN and must not be silently excluded from the future ALL-predictions ledger. | **DEFER LOGIC-09** | **High** sampling/settlement bias risk; no LOGIC-08 gate swap. |
| R02 | `backend/market_lab_v741.py:L112` | Prevents Market Lab enrichment unless legacy ready, `service_model`, and `exact_first_set` all exist. | `identity`; serve/return evidence is required conceptually, but its sufficiency remains UNKNOWN. Freshness/current-season/surface cannot be promoted without policies. | Existing `service_model` + `exact_first_set`; BO3/BO5 compatibility stays separate. | Current Engine service model + Market Lab. | Missing service/exact-set stays local NOT-APPLICABLE; semantic evidence with no threshold stays UNKNOWN. | **NO MIGRATION** | **High** because output probabilities/markets could change. |
| R03 | `backend/pbp_cache_recovery.py:L61` | Selects PBP recovery targets only when legacy ready + service model. | Deterministic `identity`; semantic model quality must not be a prerequisite for collecting missing PBP evidence. | `service_model` is the existing local selector; PBP readiness is an output, not an input. | Identity layer + PBP cache recovery. | Missing identity fails closed; missing PBP is expected input-to-recovery, not NOT_READY. | **POLICY NOT APPROVED** | **Medium/High** coverage behavior; audit before widening targets. |
| R04 | `backend/pbp_cache_recovery.py:L95` | Counts/supplies recovered profiles only for legacy-ready service-model matches. | Same identity boundary as R03; output accounting must distinguish collection coverage from semantic match readiness. | Existing recovered profile/service-model contract. | PBP cache recovery. | Absent profile/PBP remains missing evidence; do not map to global NOT_READY. | **POLICY NOT APPROVED** | **Medium** telemetry/data-shape impact. |
| R05 | `backend/pbp_enrich.py:L1224` | Selects enrichment targets only when legacy ready + service model. | Deterministic `identity`; semantic readiness must not become circular prerequisite for evidence acquisition. | Existing `service_model`; PBP market readiness is produced later. | Identity layer + PBP enrich. | Missing PBP means candidate for enrichment, not semantic failure. | **POLICY NOT APPROVED** | **Medium/High** provider/cache load and coverage risk. |
| R06 | `backend/pbp_enrich.py:L1290` | Counts ready/enriched matches only after legacy-ready + service-model gate. | Separate collection completeness from semantic readiness. | Existing profile + Early Hold/PBP evidence contracts. | PBP enrich + `pbp_market_evidence.py`. | Missing profile/evidence remains explicit missingness. | **POLICY NOT APPROVED** | **Medium** diagnostics/coverage impact. |
## Learning / SHADOW consumers

| ID | Exact use-site | Current legacy effect | Required semantic contract before migration | Market / local contract | Evidence owner | UNKNOWN / missingness rule | Policy status | Risk / decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R07 | `backend/autolearn_v84.py:L1223` | Excludes non-legacy-ready matches from AutoLearn observation capture. | Per-prediction `identity` + frozen pre-match inputs + market-specific readiness; no universal semantic gate. | Outcome/settlement must map to the exact frozen prediction population. | **LOGIC-09** prediction ledger + AutoLearn. | Predictions lacking an approved market policy remain observable as UNKNOWN, not silently removed from ALL. | **DEFER LOGIC-09** | **Critical** selection-bias/training risk; no migration here. |
| R08 | `backend/specialist_learning_v79b.py:L465` | Excludes non-legacy-ready matches from specialist learning capture. | Per-specialist/per-market requirements; identity and chronology are hard prerequisites, other dimensions require evidence. | Specialist signal contract + exact market outcome. | **LOGIC-09** + specialist owner. | UNKNOWN must remain a recorded state; it cannot be converted to a negative training label. | **DEFER LOGIC-09** | **Critical** learning-population risk. |
| R09 | `backend/shadow_lab_v78e6.py:L109` | Legacy boolean controls whether SHADOW signals are extracted and whether row is treated as data-insufficient. | `identity` plus the exact requirements of each SHADOW signal; generic freshness/current-season/surface sufficiency is not approved. | `extract_shadow_signals()` contract. | SHADOW Lab + originating signal owners. | UNKNOWN must be distinct from both `below_green_threshold` and hard missing-data rejection. | **NO MIGRATION** | **High** experiment-selection semantics. |
| R10 | `backend/shadow_lab_v78e6.py:L125` | Copies legacy readiness into SHADOW row output. | Observational copy only; future side-by-side semantic states may be added without replacing the legacy field. | SHADOW row schema. | SHADOW Lab telemetry. | Preserve tri-state and provenance if added. | **OBSERVABILITY LATER** | **Low** if additive only. |
| R11 | `backend/shadow_lab_v78e6.py:L148` | Skips history/entry capture when legacy readiness is false. | Same per-prediction requirement as history capture; should align with LOGIC-09 population semantics before replacement. | Scheduled-time cutoff + match key. | SHADOW Lab + LOGIC-09. | UNKNOWN remains observable; no automatic exclusion policy. | **DEFER LOGIC-09** | **High** historical experiment bias. |

## Telemetry / guard consumers

| ID | Exact use-site | Current legacy effect | Required semantic contract before migration | Market / local contract | Evidence owner | UNKNOWN / missingness rule | Policy status | Risk / decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R12 | `backend/update.py:L372` | Counts legacy-ready visible fixtures. | No gate replacement required. Additive telemetry may count semantic states only when joined to the exact results snapshot/match ids. | Aggregate/meta only; no market gate. | `backend/readiness_engine_shadow.py` artifact + update/meta publisher. | Report UNKNOWN explicitly; never fold UNKNOWN into NOT_READY. | **FIRST OBSERVABILITY CANDIDATE** | **Low** if side-by-side and non-gating. |
| R13 | `backend/update.py:L382` | Publishes the legacy count as `meta.model_ready`. | Keep legacy field stable; any semantic aggregate must use a new clearly SHADOW-labeled field. | Publication metadata schema. | update/meta publisher. | Missing or stale aligned readiness artifact means semantic aggregate absent/N/D, never zero. | **FIRST OBSERVABILITY CANDIDATE** | **Low** if additive only. |
| R14 | `backend/prediction_integrity_v78a.py:L152` | Emits a missing-`best_of` warning only when legacy ready. | The invariant is structural prediction context, not universal semantic readiness. Future change belongs to guard ownership audit. | `best_of`/BO3/BO5 integrity contract. | **LOGIC-10** guard ownership. | Missing `best_of` remains explicit missingness; semantic UNKNOWN must not suppress a structural warning by assumption. | **DEFER LOGIC-10** | **Medium** warning/guard behavior. |
## Frontend presentation consumers

| ID | Exact use-site | Current legacy effect | Required semantic contract before migration | Evidence owner | UNKNOWN / missingness rule | Policy status | Risk / decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R15 | `frontend/app.js:L30` | Card copy says analysis is waiting for sufficient player data when legacy false. | Presentation may eventually show semantic reasons, but only from an exact aligned SHADOW artifact; no frontend inference. | Backend readiness artifact. | UNKNOWN must render as `N/D`/„nieustalone”, not as „brak danych” or false. | **OBSERVABILITY AFTER META** | **Low/Medium** copy semantics. |
| R16 | `frontend/app.js:L63` | Moderator „Problemy” filter treats `!model_ready` as a problem. | Filtering is behavior, not pure observability; must stay legacy until explicit UI policy exists. | UI + backend readiness artifact. | UNKNOWN cannot automatically become a problem. | **NO MIGRATION** | **Medium** visible-list behavior. |
| R17 | `frontend/app.js:L63` | Moderator badge uses legacy readiness for `DANE OK / DANE -` and badge class. | Side-by-side semantic badge may be additive later; legacy badge remains authoritative until policy approval. | UI + backend readiness artifact. | UNKNOWN gets a distinct `N/D/SHADOW` state if exposed. | **OBSERVABILITY LATER** | **Low** if additive, higher if replacing legacy badge. |
| R18 | `frontend/app.js:L75` | Diagnostic panel displays legacy model-ready coverage count. | Safe read-only destination for a later semantic tri-state aggregate once exact-snapshot telemetry exists. | History coverage + readiness aggregate. | Missing aggregate displays `N/D`, never zero. | **SECOND OBSERVABILITY CANDIDATE** | **Low**. |
| R19 | `frontend/app.js:L82` | Admin overview counts legacy-ready matches. | Keep current count; later add separate SHADOW READY/NOT_READY/UNKNOWN counts. | update/meta + readiness aggregate. | UNKNOWN is a separate count; stale/missing artifact = no semantic metric. | **OBSERVABILITY AFTER R12/R13** | **Low** if additive. |
| R20 | `frontend/app.js:L98` | Admin technical payload exposes per-match legacy `model_ready`. | May later expose semantic readiness object beside it; frontend must not calculate dimensions. | Backend readiness artifact. | Missing object remains absent/N/D. | **OBSERVABILITY LATER** | **Low** if additive. |

`frontend/app.js:L63` contains three exact token occurrences implementing two semantic use-sites (problem filtering and badge rendering). `frontend/app.js:L98` contains two occurrences in one technical-view object expression. Across the phase-3 consumer set there are **22 exact `model_ready` tokens on 19 source lines**, represented by R01–R20.

## Separate contracts that must not collapse

- PBP: `backend/pbp_market_evidence.py::market_evidence_v940.market_ready` is per-market evidence sufficiency. It may be READY/NOT_READY under its existing explicit market contract even while generic semantic dimensions remain UNKNOWN.
- Symphony: `learning_model_ready` is a Symphony learning-model state, not match-level semantic readiness.
- Superbet: operator availability/evidence says whether the exact current offer exists; it does not say whether model data are semantically sufficient.
- PLAYABLE remains downstream and fail-closed on its own exact-offer/model contract; this phase does not alter it.

## Selected first observability path

The first safe candidate is **R12/R13 (`backend/update.py` aggregate/meta telemetry), side-by-side only**. A future implementation PR may publish SHADOW-labeled semantic counts only if it can prove exact snapshot alignment by match identity/source reference. It must preserve `meta.model_ready`, must not import or execute SHADOW logic inside Current Engine calculation, and must omit/N-D the semantic aggregate when alignment is unavailable.

After that, R18/R19 are the preferred UI destinations because they are diagnostic/admin counters. R16 is explicitly **not** an observability candidate because it changes which matches are shown as problems.

## Phase-3 conclusion

No runtime/learning consumer is approved for gate replacement. R07/R08/R11 are blocked on LOGIC-09 population integrity; R14 is deferred to LOGIC-10 guard ownership. PBP acquisition paths need a separate identity/provider-load audit before widening targets. Generic freshness/current-season/surface/serve-return/opponent sufficiency remains UNKNOWN until evidence selects policies.