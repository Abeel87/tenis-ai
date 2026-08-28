from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'frontend' / 'data'
TARGETS = (
    DATA / 'results.json',
    DATA / 'history.json',
)
SYMPHONY_REPORT = DATA / 'symphony_v90.json'
SYMPHONY_MATCH_CARDS = DATA / 'symphony_match_cards_v90.json'
SYMPHONY_CARD_VERSION = 'v9.0D.2'


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


def track_deep_symphony_stats() -> dict:
    """Track v9.3 MODEL/RAW after the current deep report has been generated.

    This is intentionally placed in the final data-publication stage: the deep
    report and canonical settlement feed already exist, while the tracker remains
    observation-only and cannot affect the model build that just finished.
    """
    backend = ROOT / 'backend'
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from symphony_model_tracker_v93 import run
    return run()


def _card_leg(leg: dict) -> dict:
    keep = ('key', 'label', 'market', 'pick', 'line', 'checkpoint')
    return {key: leg.get(key) for key in keep if leg.get(key) is not None}


def build_symphony_match_cards() -> dict:
    """Publish only the already-computed AUTO Symphony needed by match cards.

    The full Symphony report is several MB because it carries 2..6 compositions,
    alternatives and path diagnostics. Match list UI must not download all of that
    just to show a three-line preview, so this feed keeps only one recommended
    composition per match. No probability/model is recalculated here.
    """
    if not SYMPHONY_REPORT.exists():
        return {'path': str(SYMPHONY_MATCH_CARDS.relative_to(ROOT)), 'status': 'source-missing'}

    source = json.loads(SYMPHONY_REPORT.read_text(encoding='utf-8'))
    rows = []
    for match in source.get('matches') or []:
        if not isinstance(match, dict):
            continue
        try:
            recommended = int(match.get('recommended_leg_count'))
        except (TypeError, ValueError):
            recommended = 2
        if recommended not in (2, 3, 4, 5, 6):
            recommended = 2

        comps = match.get('compositions') or {}
        comp = comps.get(str(recommended))
        if not isinstance(comp, dict) or not comp.get('selection'):
            comp = next((comps.get(str(n)) for n in (2, 3, 4, 5, 6)
                         if isinstance(comps.get(str(n)), dict) and comps.get(str(n), {}).get('selection')), None)
            if not comp:
                continue
            recommended = int(comp.get('legs') or len(comp.get('selection') or []))

        rows.append({
            'id': match.get('id'),
            'match_key': match.get('match_key'),
            'p1': match.get('p1'),
            'p2': match.get('p2'),
            'scheduled_time': match.get('scheduled_time'),
            'recommended_leg_count': recommended,
            'composition': {
                'story_type': comp.get('story_type'),
                'symphony_score': comp.get('symphony_score'),
                'joint_probability': comp.get('joint_probability'),
                'path_coverage': comp.get('path_coverage'),
                'selection': [_card_leg(x) for x in (comp.get('selection') or []) if isinstance(x, dict)],
            },
        })

    payload = {
        'version': SYMPHONY_CARD_VERSION,
        'source_version': source.get('version'),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'matches_count': len(rows),
        'matches': rows,
    }
    tmp = SYMPHONY_MATCH_CARDS.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(SYMPHONY_MATCH_CARDS)
    return {
        'path': str(SYMPHONY_MATCH_CARDS.relative_to(ROOT)),
        'status': 'ok',
        'matches': len(rows),
        'bytes': SYMPHONY_MATCH_CARDS.stat().st_size,
        'source_bytes': SYMPHONY_REPORT.stat().st_size,
    }


def main() -> None:
    symphony_model_stats = track_deep_symphony_stats()
    symphony_cards = build_symphony_match_cards()
    report = [compact(path) for path in TARGETS]
    print(json.dumps({
        'version': 'v8.5.3',
        'targets': report,
        'symphony_model_stats': symphony_model_stats,
        'symphony_match_cards': symphony_cards,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
