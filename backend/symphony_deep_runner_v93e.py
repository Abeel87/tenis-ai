from __future__ import annotations

"""CLI entrypoint for the deep MODEL/RAW Symphony.

This process is intentionally separate from the operator-aware Symphony runner so
an unexpectedly expensive deep lattice cannot hold the whole FULL data pipeline
forever. The caller owns the wall-clock timeout; this runner keeps the existing
MODEL/RAW maths and writes the deep report only through the runtime's atomic
writer.
"""

import argparse
import json

try:
    from .symphony_scenario_runtime_v93 import run
except ImportError:
    from symphony_scenario_runtime_v93 import run

VERSION = "v9.3E-deep-runner"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legs", type=int, default=4)
    args = parser.parse_args()
    result = dict(run(legs=args.legs))
    result["runner_version"] = VERSION
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
