from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT / 'frontend' / 'data' / 'results.json',
    ROOT / 'frontend' / 'data' / 'history.json',
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
    report = [compact(path) for path in TARGETS]
    print(json.dumps({'version': 'v8.5.3', 'targets': report}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
