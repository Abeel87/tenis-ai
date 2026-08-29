from __future__ import annotations

"""Symphony v9.3H — hard coherence guard for exact scenario composition.

This adapter does not change any model probability.  It only improves how the
scenario composer interprets already-computed market selections:

* player names are matched by the same tokens regardless of ``First Last`` vs
  ``Last, First`` presentation;
* first-set game handicaps become exact-path predicates because the Symphony
  state already contains the exact first-set score;
* only one game-handicap selection from the same period may enter one Symphony,
  preventing opposite or redundant handicap legs from describing one story.

The guard is runtime-only and can be installed/uninstalled around existing
Symphony runners without touching training, PROD/SHADOW scores or Superbet
prices.
"""

import re
import unicodedata

VERSION = "v9.3H-hard-scenario-coherence"
ONE_PER_HANDICAP_MARKETS = {
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
    "set_handicap",
}


def _person_key(value) -> tuple[str, ...]:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    return tuple(sorted(tokens))


def resolve_side(match: dict, pick, fallback) -> int | None:
    """Preserve the legacy resolver, then safely accept token-order variants."""
    side = fallback(match, pick)
    if side in {1, 2}:
        return side

    wanted = _person_key(pick)
    if not wanted:
        return None
    p1 = _person_key(match.get("p1"))
    p2 = _person_key(match.get("p2"))
    # Ambiguous token sets must never be guessed.
    if not p1 or not p2 or p1 == p2:
        return None
    if wanted == p1:
        return 1
    if wanted == p2:
        return 2
    return None


def _set1_handicap_predicate(core, match: dict, candidate, original_side):
    side = resolve_side(match, candidate.pick, original_side)
    line = candidate.line
    if side not in {1, 2} or line is None:
        return None

    def predicate(outcome: dict) -> bool:
        score = outcome.get("set1")
        if not score or len(score) < 2:
            return False
        margin = float(score[0]) - float(score[1])
        if side == 2:
            margin = -margin
        return margin + float(line) > 1e-9

    return predicate


class InstalledCoherenceGuard:
    def __init__(self, core) -> None:
        self.core = core
        self.installed = False

    def install(self):
        if self.installed:
            return self
        core = self.core
        self.original_side = core._side_for_pick
        self.original_predicate = core._predicate
        self.original_compatible = core._compatible

        def side_for_pick(match: dict, pick):
            return resolve_side(match, pick, self.original_side)

        def predicate(match: dict, candidate):
            existing = self.original_predicate(match, candidate)
            if existing is not None:
                return existing
            if str(getattr(candidate, "market", "") or "") == "set1_game_handicap":
                return _set1_handicap_predicate(core, match, candidate, self.original_side)
            return None

        def compatible(a, b):
            if not self.original_compatible(a, b):
                return False
            market_a = str(getattr(a, "market", "") or "")
            market_b = str(getattr(b, "market", "") or "")
            if market_a == market_b and market_a in ONE_PER_HANDICAP_MARKETS:
                return False
            return True

        core._side_for_pick = side_for_pick
        core._predicate = predicate
        core._compatible = compatible
        self.installed = True
        return self

    def uninstall(self) -> None:
        if not self.installed:
            return
        core = self.core
        core._side_for_pick = self.original_side
        core._predicate = self.original_predicate
        core._compatible = self.original_compatible
        self.installed = False


def install(core) -> InstalledCoherenceGuard:
    return InstalledCoherenceGuard(core).install()
