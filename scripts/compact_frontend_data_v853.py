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
# The lightweight card feed is explicitly MODEL/RAW. It must never be built
# from the operator-aware `symphony_v90.json` report, otherwise missing
# Superbet availability can leak into the model-only UI.
SYMPHONY_REPORT = DATA / 'symphony_model_v93.json'
SYMPHONY_MATCH_CARDS = DATA / 'symphony_match_cards_v90.json'
SYMPHONY_CARD_VERSION = 'v9.3I'
SYMPHONY_CARD_LAYER = 'MODEL_RAW_DEEP'


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
    keep = (
        'key', 'label', 'market', 'pick', 'line', 'checkpoint',
        'path_probability', 'raw_market_probability', 'scenario_layer',
        'scenario_candidate_only',
    )
    out = {key: leg.get(key) for key in keep if leg.get(key) is not None}
    # Hard publication contract: even if an upstream diagnostic row happens to
    # carry operator metadata, the MODEL/RAW card feed can never advertise it as
    # playable. Superbet has a separate projection/UI layer.
    out['analysis_only'] = True
    out['operator_playable'] = False
    return out


def _card_path(path: dict) -> dict:
    keep = ('path', 'set1', 'set2', 'set3', 'match_score', 'total_games', 'probability_mass')
    return {key: path.get(key) for key in keep if path.get(key) is not None}


def build_symphony_match_cards() -> dict:
    """Publish the already-computed deep MODEL/RAW AUTO Symphony for match cards.

    The full deep report can be several MB because it carries 2..6 compositions,
    alternatives and exact-path diagnostics. Match list UI only needs the
    recommended MODEL/RAW composition plus a few explanatory paths. No model
    probability is recalculated here and no Superbet availability gate is read.
    """
    if not SYMPHONY_REPORT.exists():
        return {
            'path': str(SYMPHONY_MATCH_CARDS.relative_to(ROOT)),
            'status': 'source-missing',
            'source': str(SYMPHONY_REPORT.relative_to(ROOT)),
        }

    source = json.loads(SYMPHONY_REPORT.read_text(encoding='utf-8'))
    source_mode = str(source.get('mode') or '')
    if not source_mode.startswith('MODEL_RAW'):
        return {
            'path': str(SYMPHONY_MATCH_CARDS.relative_to(ROOT)),
            'status': 'source-rejected',
            'source': str(SYMPHONY_REPORT.relative_to(ROOT)),
            'source_mode': source_mode or None,
            'reason': 'RAW_CARD_SOURCE_MUST_BE_MODEL_RAW',
        }

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
            comp = next((
                comps.get(str(n)) for n in (2, 3, 4, 5, 6)
                if isinstance(comps.get(str(n)), dict) and comps.get(str(n), {}).get('selection')
            ), None)
            if not comp:
                continue
            recommended = int(comp.get('legs') or len(comp.get('selection') or []))

        selection = [
            _card_leg(x) for x in (comp.get('selection') or []) if isinstance(x, dict)
        ]
        if len(selection) < 2:
            continue

        rows.append({
            'id': match.get('id'),
            'match_key': match.get('match_key'),
            'p1': match.get('p1'),
            'p2': match.get('p2'),
            'scheduled_time': match.get('scheduled_time'),
            'best_of': match.get('best_of'),
            'path_engine': match.get('path_engine'),
            'recommended_leg_count': recommended,
            'layer': SYMPHONY_CARD_LAYER,
            'analysis_only': True,
            'operator_playable': False,
            'composition': {
                'story_type': comp.get('story_type'),
                'scenario_narrative': comp.get('scenario_narrative'),
                'symphony_score': comp.get('symphony_score'),
                'joint_probability': comp.get('joint_probability'),
                'path_coverage': comp.get('path_coverage'),
                'exact_path_scope': comp.get('exact_path_scope'),
                'analysis_only': True,
                'operator_playable': False,
                'selection': selection,
                'top_paths': [
                    _card_path(x) for x in (comp.get('top_paths') or [])[:3]
                    if isinstance(x, dict)
                ],
            },
        })

    payload = {
        'version': SYMPHONY_CARD_VERSION,
        'source_version': source.get('version'),
        'source_mode': source_mode,
        'source_report': SYMPHONY_REPORT.name,
        'layer': SYMPHONY_CARD_LAYER,
        'analysis_only': True,
        'operator_playable': False,
        'prices_used': False,
        'external_requests': 0,
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
        'source': str(SYMPHONY_REPORT.relative_to(ROOT)),
        'layer': SYMPHONY_CARD_LAYER,
        'matches': len(rows),
        'bytes': SYMPHONY_MATCH_CARDS.stat().st_size,
        'source_bytes': SYMPHONY_REPORT.stat().st_size,
        'analysis_only': True,
        'operator_playable': False,
        'external_requests': 0,
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
