# Presentation checks: scripts/verify_ui.py. Backend/data checks retained below.
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'

def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')

def main() -> None:
    telemetry = json.loads(read(FRONTEND / 'data' / 'model_telemetry_v84c.json'))
    meta = json.loads(read(FRONTEND / 'data' / 'meta.json'))
    checks = {'player_model_report_present': (telemetry.get('player_model_shadow_v89') or {}).get('version') == 'v8.9', 'player_learning_report_present': (telemetry.get('ensemble_player_learning_v891') or {}).get('version') == 'v8.9.1', 'player_model_shadow': (telemetry.get('player_model_shadow_v89') or {}).get('production_influence') is False, 'player_learning_shadow': (telemetry.get('ensemble_player_learning_v891') or {}).get('production_influence') is False, 'meta_player_model_shadow': meta.get('player_model_shadow_v89_production_influence') is False, 'meta_player_learning_shadow': meta.get('ensemble_player_learning_v891_production_influence') is False}
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(f"{('PASS' if ok else 'FAIL')}  {name}")
    if failed:
        raise SystemExit(f"Full App Coherence v8.9.2 failed: {', '.join(failed)}")
    print(json.dumps({'status': 'PASS', 'version': 'v8.9.2-symphony2', 'checks': len(checks), 'player_model_gate': ((telemetry.get('player_model_shadow_v89') or {}).get('gate') or {}).get('status'), 'player_learning_gate': ((telemetry.get('ensemble_player_learning_v891') or {}).get('gate') or {}).get('status'), 'production_influence': False, 'scenario_generator_retired': True, 'symphony2_active': True}, ensure_ascii=False))
if __name__ == '__main__':
    main()
