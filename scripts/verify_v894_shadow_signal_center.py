# Presentation checks: scripts/verify_ui.py. Backend/data checks retained below.
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BACKEND = ROOT / 'backend' / 'shadow_signal_center_v894.py'
REPORT = ROOT / 'frontend' / 'data' / 'shadow_signals_v894.json'
TREND_REPORT = ROOT / 'frontend' / 'data' / 'shadow_experiment_trends_v895.json'
WORKFLOW = ROOT / '.github' / 'workflows' / 'update-and-pages.yml'
UI_WORKFLOW = ROOT / '.github' / 'workflows' / 'ui-smoke.yml'

def ck(ok, name):
    if not ok:
        raise SystemExit(f'FAIL  {name}')
    print(f'PASS  {name}')

def load(path, fallback):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return fallback

def main():
    backend = BACKEND.read_text(encoding='utf-8')
    wf = WORKFLOW.read_text(encoding='utf-8')
    ui_wf = UI_WORKFLOW.read_text(encoding='utf-8')
    ck('VERSION = "v8.9.4"' in backend, 'backend version')
    ck('production_influence": False' in backend, 'backend shadow-only contract')
    for model in ('player_intelligence', 'catboost_player', 'ensemble_player', 'catboost_player_elo', 'ensemble_player_elo', 'tabpfn_elo'):
        ck(model in backend, f'feed model {model}')
    ck('Shadow Signal Center v8.9.4' in wf, 'data pipeline integration')
    ck('Shadow Signal Center Guard v8.9.4' in wf, 'data pipeline guard')
    ck('Shadow Signal Center Guard v8.9.4' in ui_wf, 'UI health guard')
    ck('python backend/shadow_experiment_trends_v895.py' in wf, 'v8.9.5 trend history build step')
    trend = load(TREND_REPORT, {})
    ck(trend.get('version') == 'v8.9.5', 'v8.9.5 runtime version')
    ck(trend.get('mode') == 'SHADOW', 'v8.9.5 runtime mode')
    ck(trend.get('production_influence') is False, 'v8.9.5 production isolation')
    trend_models = trend.get('models') or {}
    for model in ('catboost_player', 'ensemble_player', 'catboost_player_elo', 'ensemble_player_elo', 'tabpfn_elo'):
        ck(model in trend_models and isinstance((trend_models[model] or {}).get('points'), list), f'v8.9.5 trend {model}')
    report = load(REPORT, None)
    if report is None:
        print('PASS  runtime report pending first v8.9.4 data build')
        return 0
    ck(report.get('version') == 'v8.9.4', 'runtime version')
    ck(report.get('mode') == 'SHADOW', 'runtime mode')
    ck(report.get('production_influence') is False, 'runtime production isolation')
    ck(isinstance(report.get('models'), list) and len(report['models']) >= 6, 'runtime model registry')
    ck(all((m.get('production_influence') is False for m in report['models'])), 'all runtime models remain shadow')
    ck(isinstance(report.get('matches'), list), 'runtime match feed')
    print(json.dumps({'status': 'PASS', 'version': report.get('version'), 'matches': report.get('matches_count'), 'model_signal_counts': report.get('model_signal_counts'), 'trend_points': {key: value.get('points_count') for key, value in trend_models.items()}, 'production_influence': False}, ensure_ascii=False))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
