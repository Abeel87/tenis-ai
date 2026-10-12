"""Read-only local evaluation; never writes history or influences runtime."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.signal_settlement import reconcile_settled, SIGNAL_LAYERS
from backend.symphony2_learning import build_training_rows, train_operator_line_model, FEATURES, _entry_capture_ts, _entry_settled_ts
from backend.symphony2_engine import _cohere_exclusive_probabilities


def metrics(ps, ys):
    import math
    return {"rows": len(ps), "brier": sum((p-y)**2 for p, y in zip(ps, ys))/len(ps),
            "log_loss": -sum(y*math.log(max(p, 1e-9))+(1-y)*math.log(max(1-p, 1e-9)) for p,y in zip(ps,ys))/len(ps),
            "mean_probability": sum(ps)/len(ps), "observed_rate": sum(ys)/len(ys)}


def replay(history_path, as_of):
    source = Path(history_path).read_bytes()
    history = json.loads(source)
    repaired = reconcile_settled(history)
    changes = Counter()
    for entry in repaired:
        for layer in SIGNAL_LAYERS:
            for row in entry.get(layer) or []:
                if row.get('settlement_corrections'):
                    changes[f"{layer}:{row.get('market')}"] += 1
    cutoff = datetime.fromisoformat(as_of.replace('Z', '+00:00')).timestamp()
    def prefix(entries):
        return [e for e in entries if 0 < _entry_capture_ts(e) < cutoff
                and 0 < _entry_settled_ts(e) < cutoff]
    before = train_operator_line_model(prefix(history))
    after = train_operator_line_model(prefix(repaired))
    if not before.ready or not after.ready:
        raise ValueError('Both fixed-as-of models must be ready')
    rows = build_training_rows(repaired)
    historical_matches = {r['signature'][0] for r in rows if r['captured_ts'] <= cutoff}
    groups = defaultdict(list)
    for r in rows:
        if (r['market'] == 'match_winner' and r['captured_ts'] > cutoff
                and r['signature'][0] not in historical_matches and r['settled_ts'] > 0):
            groups[r['signature'][0]].append(r)
    pairs = [g for g in groups.values() if len(g) == 2 and sum(r['target'] for r in g) == 1]
    if not pairs:
        raise ValueError('No complete independent holdout pairs')
    flat = [r for pair in pairs for r in pair]
    targets = [r['target'] for r in flat]
    result = {"source_sha256": hashlib.sha256(source).hexdigest(), "mode": "READ_ONLY_RETROSPECTIVE_AUDIT",
              "history_entries": len(history), "corrections": dict(changes),
              "cutoff": cutoff, "as_of": as_of,
              "train_and_calibration_labels_strictly_before_cutoff": True, "independent_holdout_pairs": len(pairs),
              "excluded_incomplete_or_conflicting_pairs": len(groups)-len(pairs),
              "production_influence": False, "bankroll_mutation": False,
              "caveat": "Corrected archived terminal truth, selected frozen operator history; no prospective ROI claim."}
    for name, model in [('before', before), ('after', after)]:
        raw = [float(v[1]) for v in model.model.predict_proba([[r.get(k) for k in FEATURES] for r in flat])]
        cal = model.market_calibrators.get('match_winner')
        calibrated = [cal.predict(p) if cal else p for p in raw]
        normalized = []
        for i in range(0, len(calibrated), 2):
            a,b = calibrated[i:i+2]
            pair = _cohere_exclusive_probabilities([
                {'market': 'match_winner', 'pick': flat[i]['pick'], 'operator_model_probability': round(a*100, 2)},
                {'market': 'match_winner', 'pick': flat[i+1]['pick'], 'operator_model_probability': round(b*100, 2)},
            ])
            normalized.extend(r['operator_model_probability']/100 for r in pair)
        result[name] = {"raw": metrics(raw, targets), "calibrated": metrics(calibrated, targets),
                        "final_pair_normalized": metrics(normalized, targets)}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', required=True)
    parser.add_argument('--as-of', required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.history, args.as_of), indent=2))
