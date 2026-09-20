# LOGIC-09 phase 3 — immutable settlement/common-set audit

Status: **SHADOW IMPLEMENTATION CONTRACT**

Base audited: `main` at `0bb7613322ce77bfafcb551bcb7dcb960fd6dda0`.

This phase does **not** change production settlement semantics, model math, probability, thresholds, weights, training, Player DNA, Surface Elo, Symphony, PLAYABLE, SHADOW/PROD, telemetry, dynamic weights, or iNeed$ calculations.

## 1. Canonical owners

- Terminal match result owner: `backend/live_history_settle.py`.
  - exact provider match identity: `match_key = id:<Live Tennis API match_id>`;
  - stores `result`, `settled_at`, `settlement_source`, and `settlement_version` in `frontend/data/history.json`;
  - terminal result states: `completed`, `retired`, `void`.
- Candidate settlement scorer: `backend/signal_settlement.py::settle_signal_live`.
  - already owns hit/miss/void/unverifiable semantics for supported signal markets;
  - retirement semantics are market-aware;
  - game-state markets deliberately remain `unverifiable` because final set scores do not prove an early checkpoint state.
- Prospective prediction owner: `backend/prediction_ledger_shadow.py`.
  - immutable pre-selection snapshot;
  - source ledger rows remain untouched.
- Exact downstream selection population owner: `backend/prediction_ledger_selection_shadow.py`.
  - only exact positive PLAYABLE/Symphony evidence becomes a selected-population membership;
  - absence remains `N/D`, not `false`.

## 2. Settlement sidecar identity contract

New additive SHADOW owner: `backend/prediction_ledger_settlement_shadow.py`.

A ledger prediction can consume terminal history only when all of the following hold:

1. the ledger row was captured strictly before its scheduled start;
2. `match_key` is an exact numeric Live Tennis provider key `id:<match_id>`;
3. history contains exactly one row with the same exact `match_key` and internally consistent `match_id`;
4. ledger and history `scheduled_time` resolve to the exact same instant;
5. history is terminal (`settled`/`void`) and its final result state is `completed`, `retired`, or `void`;
6. `settled_at` exists and is not before scheduled start;
7. `settlement_source` and `settlement_version` are present;
8. the existing canonical `settle_signal_live()` scorer returns `hit`, `miss`, or `void`.

Any failure is `N/D` with a reason code. There is no fuzzy name matching, no provider-ID conversion, no nearest-time matching, no nearest-line matching, no reconstructed checkpoint state, and no network request.

## 3. Market semantics

The sidecar does not define market settlement rules. It delegates to `signal_settlement.py`.

Relevant prospective ledger families currently supported by the canonical scorer include:

- `match_winner`,
- `set1_winner`, `set2_winner`, `set3_winner`,
- `total_sets`,
- `set1_total`,
- `match_total`.

`game_state` remains `N/D` / canonical scorer `unverifiable` unless a future canonical checkpoint-tape settlement owner is separately approved. Final set scores must never be used to infer early game-state checkpoints.

Retirement and void behavior is inherited from `settle_signal_live()`; this phase does not rewrite it.

## 4. Common-test-set metric contract

Binary model metrics may use only rows that satisfy all of:

- immutable prospective ledger row;
- exact terminal settlement evidence above;
- `result in {hit, miss}`;
- Current, CatBoost, and TabPFN all available on the same prediction row.

`void` rows remain auditable but are excluded from binary accuracy/Brier/log-loss.

Populations remain separate:

- `ALL`,
- exact positive `PLAYABLE`,
- exact positive `SYMPHONY_SELECTED`,
- exact positive `PLAYABLE_AND_SYMPHONY`.

Missing downstream selection evidence is never interpreted as a negative selection fact.

iNeed$ remains outside this phase because there is still no local prospective owner with proven exact identity + pre-match placement chronology.

The sidecar may report factual metrics (`n`, binary accuracy at 0.5, Brier, log-loss, mean probability) on the exact common intersection. It must not emit a model ranking, winner, promotion decision, weight change, or automatic learning action. No minimum sample/promotion gate is invented in this phase.

## 5. Output and influence

Output: `frontend/data/prediction_ledger_settlement_shadow.json`.

Properties:

- additive SHADOW evidence only;
- source ledger is not mutated;
- zero network fetches;
- zero runtime gating;
- zero learning consumer;
- zero telemetry consumer;
- zero auto-promotion;
- all missing/ambiguous/conflicting evidence is fail-closed `N/D`.
