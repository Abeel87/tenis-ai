from __future__ import annotations

"""Isolated runner for capturing, settling and training NEURO SHADOW evidence.

This module is deliberately opt-in. Production/Symphony/PLAYABLE code does not
import it. The runner reads the already-built canonical Superbet context and
writes only dedicated NEURO SHADOW history/stat/training/current files.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from backend.neuro_shadow_current_v936 import DEFAULT_CURRENT_PATH, refresh_current_feed
from backend.neuro_shadow_history_v935 import (
    DEFAULT_HISTORY_PATH,
    DEFAULT_STATS_PATH,
    append_prediction_batches,
    settle_history,
)
from backend.neuro_shadow_market_adapter_v935 import adapt_market_context
from backend.neuro_shadow_training_v936 import DEFAULT_TRAINING_PATH, refresh_training_artifact

VERSION = "neuro-shadow-runner-v9.3.6"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"


def _read_rows(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def capture_matches(
    matches: Iterable[dict[str, Any]],
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    stats_path: Path = DEFAULT_STATS_PATH,
) -> dict[str, Any]:
    """Capture exact current Superbet selections as immutable SHADOW forecasts."""
    matches_seen = matches_with_operator = adapted = 0
    batches: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []

    for match in matches or []:
        if not isinstance(match, dict):
            continue
        matches_seen += 1
        context = match.get("superbet_market_v91") or {}
        if not isinstance(context, dict) or context.get("operator_verified") is not True:
            continue
        matches_with_operator += 1
        rows = adapt_market_context(match, context)
        adapted += len(rows)
        if rows:
            batches.append((match, rows))

    persist = append_prediction_batches(
        batches,
        history_path=history_path,
        stats_path=stats_path,
    )

    return {
        "version": VERSION,
        "mode": MODE,
        "matches_seen": matches_seen,
        "matches_with_verified_operator": matches_with_operator,
        "adapted_predictions": adapted,
        "added_predictions": int(persist.get("added") or 0),
        "production_influence": False,
        "playable_influence": False,
    }


def capture_file(
    results_path: Path = DEFAULT_RESULTS_PATH,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    stats_path: Path = DEFAULT_STATS_PATH,
) -> dict[str, Any]:
    return capture_matches(
        _read_rows(results_path), history_path=history_path, stats_path=stats_path
    )


def settle_file(
    results_path: Path = DEFAULT_RESULTS_PATH,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    stats_path: Path = DEFAULT_STATS_PATH,
) -> dict[str, Any]:
    return settle_history(
        _read_rows(results_path), history_path=history_path, stats_path=stats_path
    )


def train_file(
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    training_path: Path = DEFAULT_TRAINING_PATH,
) -> dict[str, Any]:
    return refresh_training_artifact(history_path, training_path)


def current_file(
    results_path: Path = DEFAULT_RESULTS_PATH,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    training_path: Path = DEFAULT_TRAINING_PATH,
    current_path: Path = DEFAULT_CURRENT_PATH,
) -> dict[str, Any]:
    return refresh_current_feed(results_path, history_path, training_path, current_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="NEURO SHADOW isolated capture/settlement/training/current runner")
    parser.add_argument("action", choices=("capture", "settle", "train", "current", "run"), nargs="?", default="run")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS_PATH)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING_PATH)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT_PATH)
    args = parser.parse_args()

    payload: dict[str, Any] = {"version": VERSION, "mode": MODE}
    if args.action in {"settle", "run"}:
        payload["settlement"] = settle_file(
            args.results, history_path=args.history, stats_path=args.stats
        )
    if args.action in {"capture", "run"}:
        payload["capture"] = capture_file(
            args.results, history_path=args.history, stats_path=args.stats
        )
    if args.action in {"train", "run"}:
        payload["training"] = train_file(history_path=args.history, training_path=args.training)
    if args.action in {"current", "run"}:
        payload["current"] = current_file(
            args.results,
            history_path=args.history,
            training_path=args.training,
            current_path=args.current,
        )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
