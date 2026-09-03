# Canonical Point Event semantics gate

Status: **SHADOW / diagnostic only**.

Before introducing a canonical point-event training row, the cached Live Tennis PBP source must pass an empirical semantics audit on real restored cache.

Required evidence:

- observed shapes and value domains for `sets`, `games`, `points`, `server`, `point_winner`, `is_tiebreak`;
- transition samples around ordinary points, game boundaries, set boundaries and tie-breaks;
- explicit decision whether provider score arrays represent state before or after the point represented by a row;
- measured agreement between `point_winner` and score transitions where both are observable;
- explicit handling policy for rows with missing `point_winner` or `server`;
- no training feature may use future state or provider-derived win probability as target leakage.

Until that evidence is reviewed, `point_transition_audit.py` must keep the decision as `UNRESOLVED_UNTIL_REVIEWED` and no new point-level model may affect production, Symfonia 2.0 or Superbet PLAYABLE.
