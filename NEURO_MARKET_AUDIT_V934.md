# Tenis AI — NEURO / Superbet market audit v9.3.4

Snapshot: `main` at `48875e93491b982b3a6db7559b90ffe2e63f102d` after the 2026-08-31 22:50 UTC data refresh.

## Scope

Audit only. This document does **not** change MODEL/RAW, Symphony2, Superbet PLAYABLE, thresholds, training, settlement, SHADOW/PROD promotion or model weights.

Architecture remains:

`DANE/MODELE -> SYMFONIA -> FILTR AKTUALNEJ OFERTY SUPERBET -> PLAYABLE`

NEURO is proposed as a separate SHADOW meta-model and must not bypass this contract.

## Current Symphony2 coverage

Current verified Superbet universe:

- verified fixtures: **93**
- exact operator selections: **16,363**
- scored selections: **4,768 (29.14%)**
- zero-support / UNSCORED selections: **11,595 (70.86%)**
- state-supported selections: **4,647**
- above current 55% actionable threshold: **1,546**

Current supervised Symphony2 support exists only for:

| canonical market | training support rows | current offered | current scored | status |
|---|---:|---:|---:|---|
| `exact_match_score` | 276 | 394 | 394 | EXISTING_SUPPORTED |
| `match_total` | 974 | 1,688 | 1,688 | EXISTING_SUPPORTED |
| `match_winner` | 158 | 186 | 186 | EXISTING_SUPPORTED |
| `set1_exact_score` | 1,332 | 1,218 | 1,218 | EXISTING_SUPPORTED |
| `set1_total` | 877 | 1,054 | 1,054 | EXISTING_SUPPORTED |
| `total_sets` | 108 | 228 | 228 | EXISTING_SUPPORTED |

Everything else is correctly left UNSCORED by Symphony2 today; it must not receive a fabricated percentage.

## Unscored market map

The full current zero-support gap is exactly **11,595 selections**:

| canonical market | current offered / unscored | proposed owner family | audit classification | next action |
|---|---:|---|---|---|
| `player_total_games` | 1,826 | PLAYER_TOTAL / Player Model | EXISTING_MODEL_MAPPING_GAP + SETTLEMENT_GAP | connect exact line features, keep SHADOW until settlements mature |
| `match_game_handicap` | 1,420 | HANDICAP / match distribution | EXISTING_MODEL_MAPPING_GAP + SETTLEMENT_GAP | derive from existing match/game distribution, validate exact-line settlement |
| `set2_exact_score` | 1,218 | EXACT_SCORE / set-state | EXISTING_MODEL_MAPPING_GAP | reuse exact-score family only after set2-specific validation |
| `set2_total` | 1,044 | TOTALS / set distribution | EXISTING_MODEL_MAPPING_GAP + SETTLEMENT_GAP | create set2-specific training rows; do not copy set1 calibration blindly |
| `game_state` | 1,016 | GAME_STATE / Early Hold + state model | PBP_GAP | map 2/4/6 checkpoint state evidence; require PBP support |
| `set2_game_state` | 1,016 | GAME_STATE / set2 state | PBP_GAP | PBP-only; keep UNSCORED where state data is absent |
| `set1_game_handicap` | 728 | HANDICAP / set1 distribution | EXISTING_MODEL_MAPPING_GAP + SETTLEMENT_GAP | exact line model from set1 distribution + settlement |
| `set2_game_handicap` | 710 | HANDICAP / set2 distribution | EXISTING_MODEL_MAPPING_GAP + SETTLEMENT_GAP | set2-specific evidence required |
| `set_handicap` | 438 | SET_OUTCOME / match sets distribution | SETTLEMENT_GAP | current settlement quality is not ready; no promotion |
| `exact_sets` | 189 | SET_OUTCOME / total sets | EXISTING_SHADOW_EVIDENCE | evaluate current candidate shadow evidence before NEURO ownership |
| `p1_wins_a_set` | 186 | SET_OUTCOME / player match profile | EXISTING_SHADOW_EVIDENCE | candidate shadow is review-ready; evaluate reassignment first |
| `p2_wins_a_set` | 186 | SET_OUTCOME / player match profile | EXISTING_SHADOW_EVIDENCE | evidence exists but gate is not yet review-ready |
| `match_games_parity` | 174 | PARITY | TRUE_NEURO_CANDIDATE / WEAK_BASE | low-value family; only after adequate sample |
| `set1_games_parity` | 174 | PARITY | TRUE_NEURO_CANDIDATE / WEAK_BASE | only 2 settled current shadow rows; far too little evidence |
| `set2_games_parity` | 174 | PARITY | TRUE_NEURO_CANDIDATE / WEAK_BASE | only 2 settled current shadow rows; far too little evidence |
| `p1_exactly_1_set` | 168 | SET_OUTCOME / player match profile | EXISTING_SHADOW_EVIDENCE | candidate shadow review-ready; inspect before new model |
| `p1_exactly_2_sets` | 168 | SET_OUTCOME / player match profile | EXISTING_SHADOW_EVIDENCE | still collecting sample |
| `p2_exactly_1_set` | 168 | SET_OUTCOME / player match profile | EXISTING_SHADOW_EVIDENCE | strongest current candidate evidence; inspect before new model |
| `p2_exactly_2_sets` | 168 | SET_OUTCOME / player match profile | EXISTING_SHADOW_EVIDENCE | still collecting sample |
| `any_set_to_nil` | 166 | SET_OUTCOME / exact-set distribution | EXISTING_SHADOW_EVIDENCE | current candidate shadow is review-ready; do not replace with NEURO blindly |
| `match_total_aces` | 132 | SERVE / serve_props | EXISTING_MODEL_MAPPING_GAP | connect serve model to exact Superbet line + collect settlement |
| `most_aces` | 126 | SERVE / serve_props | EXISTING_MODEL_MAPPING_GAP | map player ace-strength comparison + settlement |

## Important finding: a large part of `MODEL: niepokryty` is not a true no-model problem

The current UI correctly says `MODEL: niepokryty`, but the audit shows three different reasons hidden behind the same label:

1. **Existing model-family mapping gap** — a model or distribution already exists, but the exact Superbet canonical selection is not yet wired/trained as an operator-line market.
2. **Evidence/settlement gap** — a shadow candidate exists, but there are not enough settled exact-line examples to grant production support.
3. **True no-model / weak-base family** — mainly parity-style markets and any family with no defensible existing distribution. These are the cleanest first candidates for a future neural specialist.

These states must be separated in telemetry and UI before NEURO is trained.

## Candidate shadow evidence already available

`superbet_candidate_signals_v925` is non-PLAYABLE shadow settlement evidence and currently reports **367 settled**, **278 hits**, **75.7% accuracy**, **Brier 0.1734** overall. It must not be treated as production proof because selection/capture thresholds and market mix matter.

Markets currently marked review-ready by that layer:

| market | settled | accuracy | Brier | note |
|---|---:|---:|---:|---|
| `any_set_to_nil` | 46 | 87.0% | 0.1207 | review-ready candidate evidence |
| `p1_exactly_1_set` | 47 | 76.6% | 0.1819 | review-ready candidate evidence |
| `p1_wins_a_set` | 65 | 76.9% | 0.1628 | review-ready candidate evidence |
| `p2_exactly_1_set` | 47 | 93.6% | 0.0752 | review-ready candidate evidence |

Notable hold/collecting examples:

- `p2_wins_a_set`: 60 settled, 60.0%, Brier 0.2415 — not review-ready.
- `exact_sets`: 42 settled, 71.4%, Brier 0.2064, but promotion subset is too small.
- `player_total_games`, `match_game_handicap`, set handicaps and `set2_total`: current captured rows are still pending / not settled enough.
- `set_handicap`: 87 currently unverifiable rows — settlement semantics/data quality must be fixed before any model promotion.

Conclusion: **first harvest trustworthy existing shadow evidence, then let NEURO compete against it.**

## Canonical model-family registry to implement

The next implementation should produce one machine-readable registry with one owner and one state per canonical market:

- `RESULT`: match/set winner.
- `TOTALS`: match/set totals, total sets.
- `EXACT_SCORE`: exact match/set score.
- `GAME_STATE_EARLY`: score after 2/4/6 games and Early Hold/PBP-derived state.
- `HANDICAP`: match/set game handicap, set handicap.
- `PLAYER_TOTAL`: participant total games.
- `SERVE`: aces, most aces, double faults when available.
- `SET_OUTCOME`: wins a set, exactly N sets, set-to-nil style outcomes.
- `PARITY`: odd/even games.
- `UNASSIGNED`: no defensible existing owner yet.

Each row must expose:

`canonical_market`, `family`, `existing_model_sources`, `training_support`, `settlement_support`, `pbp_required`, `coverage_status`, `neuro_eligible`, `reason`.

## NEURO v1 contract

NEURO v1 should be a **meta-model SHADOW**, not a replacement for Symphony2.

Suggested input feature groups:

- current/base model score,
- CatBoost score,
- TabPFN score when available,
- Adaptive score,
- Surface Elo / player-strength features,
- Player Model / Player Intelligence outputs,
- serve profile features,
- Early Hold/PBP state features,
- market family, canonical market, pick, line, checkpoint,
- surface, tour, best-of, player scope,
- Symphony state probability where defensible,
- data-quality / missingness indicators,
- model disagreement / spread features.

Missing model values must remain explicit missingness features; never silently replace an unsupported market with 50% and call it model evidence.

### NEURO outputs

For each exact current Superbet selection:

- `neuro_probability_shadow`
- `neuro_support_rows`
- `neuro_data_quality`
- `neuro_market_family`
- `neuro_model_inputs_present`
- `neuro_calibration_status`
- `neuro_result = pending/hit/miss/void/unverifiable`

### Hard safety gates

Until an explicit later promotion PR:

- `production_influence = false`
- `playable_influence = false`
- `symphony_prod_influence = false`
- no weight mutation
- no threshold mutation
- no replacement of MODEL/RAW values
- no fabricated scores on zero-training-support families

## Tracking / UI design

Future UI after backend shadow contract is stable:

- add **🧠 NEURO** as a separate top-level view next to Symphony;
- add a small 🧠 indicator in the match details near `SUPERBET — realne rynki i linie`;
- show `MODEL`, `SYMPHONY`, and `NEURO SHADOW` separately, never overwrite one with another;
- NEURO dashboard: predictions, settled/pending, hit/miss/void, accuracy, Brier, log-loss, calibration, confidence buckets, by-market, by-surface, by-tour, by model-source presence;
- direct comparison charts: `NEURO vs Symphony2`, `NEURO vs best existing source`, and disagreement subsets.

## Recommended implementation order

1. Add machine-readable canonical ownership registry.
2. Add audit generator/tests proving all current canonical Superbet markets are classified.
3. Split `MODEL: niepokryty` internally into mapping/evidence/PBP/true-no-model reasons (UI wording can remain simple initially).
4. Reuse candidate-shadow settlement evidence for families already being tracked.
5. Repair/complete exact-line settlement for handicap/player-total/set2 families.
6. Only then add NEURO SHADOW dataset/training/tracker.
7. Add NEURO UI after backend telemetry exists.
8. Promotion to any production influence requires a separate reviewed PR and statistically meaningful per-market evidence.

## Decision

Do **not** train one neural network over all 11,595 unscored selections immediately.

First fix ownership and evidence. Then use NEURO as a controlled challenger/meta-model. This preserves the working architecture while giving us a clean path to expand coverage without inventing confidence.