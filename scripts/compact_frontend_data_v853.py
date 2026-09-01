from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from prune_results_payload_v854 import prune_results

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'frontend' / 'data'
TARGETS = (
    DATA / 'results.json',
    DATA / 'history.json',
    DATA / 'symphony2_current.json',
    DATA / 'symphony2_history.json',
    DATA / 'symphony2_stats.json',
)


def _path_label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _compact_json(path: Path, data) -> dict:
    before = path.stat().st_size if path.exists() else 0
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(path)
    after = path.stat().st_size
    return {
        'path': _path_label(path),
        'status': 'ok',
        'before_bytes': before,
        'after_bytes': after,
        'saved_bytes': before - after,
        'saved_pct': round((before - after) * 100 / before, 1) if before else 0.0,
    }


def prune_symphony2_publication(path: Path) -> dict:
    """Remove only zero-support offer rows from the public Symphony snapshot.

    They have ``operator_model_probability=None`` and therefore cannot be used in
    a composition. Aggregate offer/zero-support diagnostics remain in the
    snapshot/stats. Compositions and every scored exact operator selection stay
    untouched. This is publication-only and runs after engine + settlement.
    """
    if not path.exists():
        return {'status': 'missing', 'path': _path_label(path)}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        return {'status': 'skipped-non-object', 'path': _path_label(path)}

    removed = 0
    kept = 0
    for match in data.get('matches') or []:
        if not isinstance(match, dict):
            continue
        rows = match.get('scored_selections')
        if not isinstance(rows, list):
            continue
        keep = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get('operator_model_probability') is None:
                removed += 1
                continue
            keep.append(row)
            kept += 1
        match['scored_selections'] = keep

    data['publication_prune_v940'] = {
        'version': 'v9.4.0',
        'policy': 'DROP_ZERO_SUPPORT_ROWS_AFTER_ENGINE_KEEP_COUNTS_AND_COMPOSITIONS',
        'removed_zero_support_rows': removed,
        'kept_scored_rows': kept,
        'model_math_changed': False,
        'tracker_history_changed': False,
    }
    report = _compact_json(path, data)
    report.update({'removed_zero_support_rows': removed, 'kept_scored_rows': kept})
    return report


def compact(path: Path) -> dict:
    if not path.exists():
        return {'path': _path_label(path), 'status': 'missing'}
    if path.name == 'symphony2_current.json':
        return prune_symphony2_publication(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    return _compact_json(path, data)


def main() -> None:
    results_prune = prune_results(DATA / 'results.json')
    report = [compact(path) for path in TARGETS]
    print(json.dumps({
        'version': 'v9.4.0-safe-publication-compact',
        'targets': report,
        'results_publication_prune': results_prune,
        'legacy_symphony_publication': False,
        'production_math_changed': False,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
