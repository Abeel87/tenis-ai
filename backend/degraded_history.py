from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from history_tracker import archive_predictions, history_stats, load_history, save_history

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS_PATH = OUT / "results.json"
HISTORY_PATH = OUT / "history.json"
HISTORY_STATS_PATH = OUT / "history_stats.json"
META_PATH = OUT / "meta.json"


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def capture_history(
    results_path: Path = RESULTS_PATH,
    history_path: Path = HISTORY_PATH,
    stats_path: Path = HISTORY_STATS_PATH,
    meta_path: Path = META_PATH,
    now: datetime | None = None,
) -> dict:
    """Freeze green pre-match picks even when the history provider is unavailable."""
    now = now or datetime.now(timezone.utc)

    results = _read_json(results_path, [])
    if not isinstance(results, list):
        results = []

    entries = load_history(history_path)
    entries = archive_predictions(entries, results, now=now)
    entries = sorted(
        entries,
        key=lambda entry: entry.get("scheduled_time") or "",
        reverse=True,
    )[:2500]

    # Zawsze twórz pliki historii/statystyk, nawet jeśli jeszcze nie ma typów.
    save_history(history_path, entries)
    _write_json(stats_path, history_stats(entries))

    meta = _read_json(meta_path, {})
    if not isinstance(meta, dict):
        meta = {}

    tracked = sum(1 for entry in entries if entry.get("signals"))
    pending = sum(
        1
        for entry in entries
        if entry.get("status") in ("pending", "upcoming")
        and entry.get("signals")
    )
    degraded = bool(meta.get("degraded_reason"))

    meta.update(
        {
            "history_matches": tracked,
            "history_pending": pending,
            "history_capture_at": now.isoformat(),
            "history_capture_mode": "last-analysis" if degraded else "current-analysis",
        }
    )
    _write_json(meta_path, meta)

    return {
        "history_matches": tracked,
        "history_pending": pending,
        "capture_mode": meta["history_capture_mode"],
        "source_results": len(results),
    }


def main() -> None:
    print(json.dumps(capture_history(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
