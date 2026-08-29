from __future__ import annotations

"""CLI entrypoint for the deep MODEL/RAW Symphony.

This process is intentionally separate from the operator-aware Symphony runner so
an unexpectedly expensive deep lattice cannot hold the whole FULL data pipeline
forever. The caller owns the wall-clock timeout; this runner keeps the existing
MODEL/RAW maths and writes the deep report only through the runtime's atomic
writer.

v9.3R wraps only the report scheduler with an exact per-match fingerprint cache.
A killed process can therefore leave already-finished match rows in the existing
Actions cache, while the published deep report remains all-or-nothing.
"""

import argparse
import json

try:
    from . import symphony_scenario_runtime_v93 as runtime
    from . import symphony_incremental_cache_v93r as incremental_cache
except ImportError:
    import symphony_scenario_runtime_v93 as runtime
    import symphony_incremental_cache_v93r as incremental_cache

VERSION = "v9.3E-deep-runner"

# Any adapter that can alter a cached row participates in the token.  A version
# change invalidates old rows before reuse; the current match + Shadow payload is
# fingerprinted independently for data changes.
ENGINE_TOKEN = "|".join((
    runtime.VERSION,
    runtime.PERFORMANCE_VERSION,
    runtime.PAIR_MATRIX_VERSION,
    runtime.PROGRESS_TELEMETRY_VERSION,
    runtime.PAYLOAD_RANK_CACHE_VERSION,
    runtime.BEAM_MASK_MASS_VERSION,
    runtime.BEAM_SCREEN_VERSION,
    runtime.COHERENCE_VERSION,
    runtime.compact.VERSION,
))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legs", type=int, default=4)
    args = parser.parse_args()

    cache = incremental_cache.install(runtime.deep, runtime.core, ENGINE_TOKEN)
    try:
        result = dict(runtime.run(legs=args.legs))
    finally:
        cache.uninstall()

    result["runner_version"] = VERSION
    result["incremental_cache_version"] = incremental_cache.VERSION
    result["incremental_cache_engine_token"] = ENGINE_TOKEN
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
