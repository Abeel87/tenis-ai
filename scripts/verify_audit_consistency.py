"""Fail publishing when settlement, report or RAW/FINAL contracts diverge."""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from signal_settlement import SIGNAL_LAYERS


def check(directory):
    def read(name):
        return json.loads((directory / name).read_text())
    errors = []
    history = read('history.json')
    results = read('results.json')
    for entry in history:
        if entry.get('status') in ('settled', 'void'):
            for layer in SIGNAL_LAYERS:
                if any(s.get('result') == 'pending' for s in entry.get(layer) or []):
                    errors.append(f"{entry.get('match_key')}: closed match has pending {layer}")
    checked = 0
    for match in results:
        seen = set()
        for signal in (match.get('autolearn_v84') or {}).get('signals') or []:
            key = signal.get('key')
            if not key or key in seen:
                errors.append(f"{match.get('id')}: duplicate/missing candidate key {key}")
            seen.add(key)
            prod = signal.get('adaptive_prod_v79') or {}
            if not prod:
                continue
            checked += 1
            try:
                raw, final, delta, cap = [float(prod[k]) for k in ('raw_score','final_score','delta_pp','cap_pp')]
                assert all(math.isfinite(x) for x in (raw,final,delta,cap))
                assert 0 <= raw <= 100 and 0 <= final <= 100 and 0 <= cap <= 8
                assert abs(final - raw) <= cap + .11
                assert abs((final - raw) - delta) <= .11
                assert abs(float(signal['ensemble']) - raw) <= .11
                assert abs(float(signal['final_score']) - final) <= .11
            except (KeyError, TypeError, ValueError, AssertionError):
                errors.append(f"{match.get('id')} {key}: invalid RAW/FINAL/cap contract")
    stats = read('history_stats.json')['overall']
    calibration = read('calibration_v78d.json')['current']['overall']
    for key in ('settled', 'hits', 'misses', 'accuracy'):
        if stats[key] != calibration[key]:
            errors.append(f'calibration/history mismatch: {key}')
    return errors, checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'frontend' / 'data')
    errors, checked = check(parser.parse_args().data_dir)
    if errors:
        print('\n'.join(errors))
        raise SystemExit(1)
    print(f'Audit consistency: PASS ({checked} RAW/FINAL candidates; all closed layers; same-snapshot calibration)')
