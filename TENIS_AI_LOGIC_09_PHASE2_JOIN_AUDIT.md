# LOGIC-09 phase 2 — exact downstream join audit

Status: **AUDIT / DESIGN ONLY — SHADOW evidence, zero runtime or learning change**

Audit date: 2026-09-20.

Git base: `711f8bc5bb013684c4ecb0d1be2ecd220886bcc6` (merge of phase-1 closeout PR #417; post-merge `Tenis AI UI & Project Health` run #2649 SUCCESS).

Production data evidence: normal Update run `35498754494` / runtime-source artifact `10600994247`, produced from phase-1 code head `039740786ae7026980fa0931465d03e632450879` and subsequently published by bot commit `d6c23007bc59052eb9e9be63e5a4fd11758b6944`. The audit reads the frozen runtime artifacts; it does not recompute model decisions.

This phase does **not** authorize changes to model math, probability, thresholds, weights, training, Player DNA, Surface Elo, Symphony, Neuron, PLAYABLE, settlement, iNeed$ calculations, telemetry consumers or dynamic weights.

## 1. Prospective ledger population

`frontend/data/prediction_ledger_shadow.json` contains:

- 2131 immutable `ALL` rows;
- 88 exact `id:<match_id>` match identities; there are no fallback name/date match keys in this first prospective population;
- 2131/2131 Current scores available;
- 2131/2131 CatBoost scores available;
- 187/2131 TabPFN scores available;
- exact Current + CatBoost + TabPFN intersection: 187;
- settlement result/source/time: null on all 2131 rows at this audit snapshot.

Supported ledger markets in this snapshot are `match_total`, `set1_total`, `game_state`, `match_winner`, `set1_winner`, `set2_winner`, `set3_winner` and `total_sets`.

The ledger identity remains `match_key + candidate_key + producer_version`, but downstream joins must not assume that a downstream owner's raw `key` string equals `candidate_key`.

## 2. Canonical PLAYABLE owner audit

Owner: `backend/superbet_playable.py` / `history.json.playable_autolearn_signals_v912`.

Canonical downstream selection identity is the parent match identity plus `superbet_playable.signal_signature(signal)`:

`(market, normalized_pick, line, checkpoint, player)`.

Real frozen evidence in the audited runtime artifact:

- history entries: 1486;
- entries carrying `playable_autolearn_signals_v912`: 827;
- frozen PLAYABLE signals: 54,965;
- exact `(match_key, signal_signature)` identities: 54,965;
- duplicate exact identities: **0**;
- entries with valid `playable_captured_at_v912 < scheduled_time`: 819;
- valid-chronology PLAYABLE signals: 54,843;
- entries without a usable pre-match capture proof: 8 / 122 signals. Those 122 signals are audit-ineligible even if another field happens to match.

Prospective ledger exact join result:

- exact + chronology-valid PLAYABLE joins: **407 / 2131**;
- ambiguous exact joins: **0**;
- no exact frozen PLAYABLE evidence: **1724 / 2131** — this is `N/D`, not an inferred `playable=false`.

Important observed key-shape fact: some operator-projection signals have raw keys such as `superbet|...` while ledger candidates use AutoLearn canonical candidate keys such as `set1_total|11.5|under`. Therefore raw-key equality is not a legal join rule. The canonical owner signature is the join surface.

## 3. Canonical Symphony owner audit

Owner: `backend/symphony2_tracker.py` / `symphony2_history.json`.

Frozen composition identity is `prediction_id` / composition id. Each leg is identified by the same exact selection dimensions used by `symphony2_tracker.selection_signature`: match id + market + pick + line + checkpoint + player.

Real frozen evidence:

- Symphony history entries: 2305;
- entries with valid `captured_at < scheduled_time`: 2302;
- invalid/post-start entries: **3**, containing 6 legs. They are excluded from any phase-2 selection evidence;
- historical leg identities may occur in more than one frozen composition: 1039 leg identities repeat across compositions, with a maximum of 7 occurrences. Therefore a Symphony join must preserve the exact composition `prediction_id`; it may not collapse all historical compositions into one anonymous selected row.

Prospective ledger exact join result:

- exact + chronology-valid Symphony-selected ledger rows: **23 / 2131**;
- rows with more than one chronology-valid Symphony match in this prospective ledger: **0**;
- no exact frozen Symphony evidence: **2108 / 2131** — `N/D`, not inferred `symphony_selected=false`.

Market distribution of the 23 positive prospective joins: 21 `match_winner`, 2 `match_total`.

## 4. iNeed$ SHADOW owner audit

Owners: `backend/ineed_money.py`, `supabase/functions/ineed-sync/index.ts`, Supabase `ineed_signals`, `ineed_decision_snapshots`, `ineed_shadow_bets`.

The iNeed$ stable fingerprint is SHA-256 over exact operator + match id + canonical `superbet_playable.signal_signature(signal)`. A qualified decision freezes a snapshot; a SHADOW bet freezes `placement_snapshot`.

Read-only production Supabase evidence at audit time:

- `ineed_signals`: 743;
- `ineed_decision_snapshots`: 778;
- `ineed_shadow_bets`: 35;
- terminal/settled SHADOW bets: **35 / 35**;
- placement snapshots with timestamp: 35 / 35;
- placement snapshots with line field: 35 / 35;
- placement snapshots with checkpoint field: 35 / 35;
- placement snapshots with `scheduled_time`: **0 / 35**.

The first prospective ledger covers 88 match ids. Exact match-id overlap with the 35 frozen iNeed$ SHADOW bets is **0**. Therefore phase 2 currently has **no legal prospective `INEED_SELECTED=true` join**. Existing iNeed$ historical bets must not be backfilled into the new ledger by names, nearest time, market similarity or provider-id guessing.

Because `placement_snapshot` does not itself contain `scheduled_time`, future positive iNeed$ ledger joins must prove chronology by an exact match-owner join that supplies the same fixture schedule, then require `placement_snapshot.timestamp < scheduled_time`. The placement timestamp alone is insufficient.

## 5. Exact identity contract for a future SHADOW joiner

A future joiner may emit a positive downstream fact only when all required dimensions are proven exactly.

### Match identity

1. Prefer exact persisted `match_key` equality where both owners retain the same key.
2. For Symphony/iNeed$ bare `match_id`, accept only the deterministic `id:<match_id>` conversion when provenance proves the same canonical match-id namespace.
3. Do not join fallback name/date identities to numeric ids by similarity.
4. No fuzzy player matching, alias guessing, nearest scheduled time or cross-provider numeric-id comparison.

### Candidate / signal identity

Use the canonical Superbet signature dimensions, not raw key-string equality:

- canonical market;
- canonical pick;
- exact line when the market is line-bearing;
- exact checkpoint for `game_state`;
- exact canonical player dimension for player-specific markets.

For current prospective ledger `game_state` rows, checkpoint is encoded in strict candidate form `state|<checkpoint>|<score>`. A future joiner must parse only this exact form and must verify that its score token agrees with the row `pick`; malformed or conflicting identity is `N/D`.

### Chronology

A positive fact additionally requires owner-specific frozen evidence strictly before match start:

- ledger: `captured_at < scheduled_time`;
- PLAYABLE: `playable_captured_at_v912 < scheduled_time`;
- Symphony: `captured_at < scheduled_time`;
- iNeed$: `placement_snapshot.timestamp < scheduled_time`, with `scheduled_time` obtained only through a proven exact match join.

Missing, unparsable or post-start timestamps fail closed to `N/D`. They must never be repaired from a later snapshot.

## 6. Negative-case contract

The following cases are explicitly non-joins:

- same match but different market;
- same match/market/pick but different line;
- same match/market/line but different pick;
- different `game_state` checkpoint;
- malformed ledger candidate identity;
- ambiguous duplicate downstream identity where the required owner object cannot be identified uniquely;
- missing owner capture timestamp;
- capture at or after scheduled start;
- iNeed$ row without an exact prospective ledger match;
- any nearest-line, nearest-time, fuzzy-name or guessed provider-id match.

Absence of qualifying evidence is `N/D`. It is not equivalent to a frozen negative selection fact.

## 7. Settled common-test-set contract

The direct Current/CatBoost/TabPFN comparison set must be an exact prospective intersection. A row is eligible only if:

1. it is an immutable phase-1 ledger row captured before start;
2. Current, CatBoost and TabPFN scores are all frozen and available on that same ledger identity;
3. a canonical settlement exists for the exact same match/candidate signature;
4. settlement is `hit` or `miss` for binary accuracy/Brier/log-loss comparisons; `void` is excluded from binary model metrics but retained as explicit settlement evidence;
5. all compared models use the score semantics frozen in the ledger row; no later recomputation is allowed;
6. population membership is reported separately (`ALL`, exact PLAYABLE, `GENERATOR_SELECTED`, `SYMPHONY_SELECTED`, `INEED_SELECTED`). A downstream population must never replace the common `ALL` model intersection.

At this audit snapshot:

- three-model prospective common rows: **187**;
- common rows with chronology-valid exact PLAYABLE evidence: **67**;
- common rows with chronology-valid exact Symphony evidence: **4**;
- common rows with both PLAYABLE and Symphony evidence: **4**;
- settled prospective common rows: **0**.

Therefore no Current/CatBoost/TabPFN accuracy/Brier/calibration ranking may yet be produced from the new prospective ledger. Zero settled rows is an expected early-life state, not permission to use historical selected populations as a substitute.

## 8. Phase-2 audit decision

The real data proves that an exact SHADOW join is feasible for PLAYABLE and Symphony without fuzzy matching, and also proves that current iNeed$ history does not overlap the first prospective ledger. It additionally exposes owner-specific chronology failures that must fail closed.

A subsequent implementation step may add a **SHADOW-only, additive** join/evidence layer using the contract above. It must preserve all existing owners, keep missing selection facts as `N/D`, and must not wire the ledger into telemetry, dynamic weights, training, PLAYABLE, Symphony settlement or iNeed$ decisions.

No runtime/learning migration is authorized by this audit.