from __future__ import annotations

"""Runtime guard for Symphony v9.3A deep MODEL/RAW lattice.

BO3 gets the new exact set1+set2 state lattice. BO5 stays evidence-only in this
first v9.3A step instead of expanding a huge set2×set3×set4×set5 state space.
That keeps full-build runtime bounded and, more importantly, never invents an
exact joint probability for a state space we have not compacted safely yet.
"""

try:
    from . import symphony_engine_v90 as core
    from . import symphony_scenario_lattice_v93 as deep
except ImportError:
    import symphony_engine_v90 as core
    import symphony_scenario_lattice_v93 as deep

VERSION = "v9.3A-runtime-bounded"


def run(legs: int = 4) -> dict:
    original = deep._build_deep_outcomes

    def bounded(match: dict):
        if core._best_of(match) == 5:
            return []
        return original(match)

    deep._build_deep_outcomes = bounded
    try:
        result = dict(deep.run(legs=legs))
    finally:
        deep._build_deep_outcomes = original

    result["runtime_guard_version"] = VERSION
    result["bo3_exact_scope"] = "SET1+SET2+MATCH"
    result["bo5_scope"] = "EVIDENCE_ONLY_PENDING_COMPACT_DEEP_STATE"
    return result
