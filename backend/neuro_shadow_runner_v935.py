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
    load_history,
    settle_history,
)
from backend.neuro_shadow_market_adapter_v935 import adapt_market_context
from backend.neuro_shadow_state_v935 import CANDIDATE_CAPTURE_READY_MARKETS
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


def _match_identity(match: dict[str, Any]) -> Any:
    return match.get("match_id") or match.get("id") or f"{match.get('p1')}|{match.get('p2')}|{match.get('scheduled_time')}"


def _selection_prediction_key(match: dict[str, Any], selection: dict[str, Any]) -> str:
    """Mirror tracker prediction_key without building the costly state."""
    return "|".join(
        str(x or "")
        for x in (
            _match_identity(match),
            selection.get("market"),
            selection.get("pick"),
            selection.get("line"),
            selection.get("player"),
            selection.get("market_id"),
            selection.get("outcome_id"),
        )
    )


def _ready_candidates(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row for row in (context.get("canonical_selections") or [])
        if isinstance(row, dict)
        and row.get("operator_available") is True
        and str(row.get("market") or "") in CANDIDATE_CAPTURE_READY_MARKETS
    ]


def capture_matches(
    matches: Iterable[dict[str, Any]],
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    stats_path: Path = DEFAULT_STATS_PATH,
) -> dict[str, Any]:
    """Capture only new exact Superbet selections as immutable SHADOW forecasts.

    Existing exact selections are rejected before state-space construction, so
    unchanged hourly refreshes avoid recomputing the expensive state per match.
    """
    matches_seen = matches_with_operator = adapted = 0
    skipped_captured = new_candidate_selections = 0
    batches: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    existing_keys = {
        str(row.get("prediction_key"))
        for row in load_history(history_path)
        if isinstance(row, dict) and row.get("prediction_key")
    }

    for match in matches or []:
        if not isinstance(match, dict):
            continue
        matches_seen += 1
        context = match.get("superbet_market_v91") or {}
        if not isinstance(context, dict) or context.get("operator_verified") is not True:
            continue
        matches_with_operator += 1

        candidates = _ready_candidates(context)
        if not candidates:
            continue
        fresh = [
            selection for selection in candidates
            if _selection_prediction_key(match, selection) not in existing_keys
        ]
        if not fresh:
            skipped_captured += 1
            continue
        new_candidate_selections += len(fresh)

        # Preserve model_signals and all context metadata, but send only unseen
        # canonical selections through the costly shared-state adapter.
        fresh_context = dict(context)
        fresh_context["canonical_selections"] = fresh
        rows = adapt_market_context(match, fresh_context)
        adapted += len(rows)
        if rows:
            batches.append((match, rows))
            for row in rows:
                key = "|".join(
                    str(x or "")
                    for x in (
                        _match_identity(match), row.get("market"), row.get("pick"),
                        row.get("line"), row.get("player"), row.get("source_market_id"),
                        row.get("source_outcome_id"),
                    )
                )
                existing_keys.add(key)

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
        "matches_skipped_already_captured": skipped_captured,
        "new_candidate_selections": new_candidate_selections,
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
