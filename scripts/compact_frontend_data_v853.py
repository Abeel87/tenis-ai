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


def compact(path: Path) -> dict:
    if not path.exists():
        return {'path': str(path.relative_to(ROOT)), 'status': 'missing'}
    before = path.stat().st_size
    data = json.loads(path.read_text(encoding='utf-8'))
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(path)
    after = path.stat().st_size
    return {
        'path': str(path.relative_to(ROOT)),
        'status': 'ok',
        'before_bytes': before,
        'after_bytes': after,
        'saved_bytes': before - after,
        'saved_pct': round((before - after) * 100 / before, 1) if before else 0.0,
    }


def main() -> None:
    results_prune = prune_results(DATA / 'results.json')
    report = [compact(path) for path in TARGETS]
    print(json.dumps({
        'version': 'v8.5.4-symphony2',
        'targets': report,
        'results_publication_prune': results_prune,
        'legacy_symphony_publication': False,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
