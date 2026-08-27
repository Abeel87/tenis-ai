"""Offline reconciliation and reports from a single, final history snapshot.

No API calls, model fitting, or retroactive forecast decoration.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from autolearn_v84 import VERSION as TRACKER_VERSION, tracking_stats
from calibration_guard_v78d import build_calibration_report, add_calibration_to_matches
from history_tracker import MODEL_VERSION, history_stats
from model_telemetry_v84c import build_report
from shadow_lab_v78e6 import build_shadow_stats
from signal_settlement import reconcile_settled, SIGNAL_LAYERS


def refresh(directory):
    directory = Path(directory)
    def read(name, default):
        path = directory / name
        return json.loads(path.read_text()) if path.exists() else default

    def write(name, data):
        path = directory / name
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
        temp.replace(path)

    before = read('history.json', [])
    history = reconcile_settled(before)
    changes = sum(a.get('result') != b.get('result')
                  for old, new in zip(before, history) for layer in SIGNAL_LAYERS
                  for a, b in zip(old.get(layer) or [], new.get(layer) or []))
    write('history.json', history)
    write('history_stats.json', history_stats(history))
    calibration = build_calibration_report(history, MODEL_VERSION)
    write('calibration_v78d.json', calibration)
    write('results.json', add_calibration_to_matches(read('results.json', []), calibration))
    write('model_telemetry_v84c.json', build_report(history))
    write('shadow_stats.json', build_shadow_stats(history))
    auto = read('autolearn_v84.json', {})
    if auto:
        auto['tracking'] = tracking_stats(history, tracker_version=TRACKER_VERSION)
        auto['tracking_all_versions'] = tracking_stats(history)
        auto['tracking_updated_at'] = datetime.now(timezone.utc).isoformat()
        write('autolearn_v84.json', auto)
    meta = read('meta.json', {})
    meta['settlement_reports_updated_at'] = datetime.now(timezone.utc).isoformat()
    meta['settlement_reports_policy'] = 'v8.8.4-single-snapshot'
    write('meta.json', meta)
    return {'reconciled_signals': changes, 'history_entries': len(history)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'frontend' / 'data')
    print(json.dumps(refresh(parser.parse_args().data_dir)))
