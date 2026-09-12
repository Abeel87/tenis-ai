from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from prune_results_payload import prune_results

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'frontend' / 'data'
TARGETS = (
    DATA / 'results.json',
    DATA / 'history.json',
    DATA / 'symphony2_current.json',
    DATA / 'symphony2_history.json',
    DATA / 'symphony2_stats.json',
)

# These fields are prediction-time diagnostics duplicated beside the canonical
# frozen values. Once a match is settled, downstream learning uses score,
# model_scores, result, market identity and adaptive_prod_v79.final_score;
# Model Telemetry only needs dynamic_weighting.active for the historical
# Dynamic Ensemble track. Keeping the full per-segment explanation forever
# made history.json grow without adding training information.
SETTLED_AUTOLEARN_REDUNDANT_FIELDS = {
    'raw_score', 'uncapped_score', 'learned_score', 'final_score', 'delta',
    'cap_pp', 'applied', 'action', 'lesson', 'similar_n',
    'historical_accuracy', 'evidence', 'components', 'ensemble_raw',
    'adaptive_delta_pp', 'local_weights',
}
# Historical telemetry consumes only ``active`` from dynamic_weighting and only
# ``final_score`` from adaptive_prod_v79. Version/status/reason/max_shift and
# adaptive version/status are explanatory duplicates once the frozen signal is
# settled; canonical signal identity, source, scores and result remain intact.
DYNAMIC_HISTORY_KEYS = ('active',)
ADAPTIVE_PROD_HISTORY_KEYS = ('final_score',)


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


def _compact_dynamic_history(policy):
    if not isinstance(policy, dict):
        return policy
    return {
        key: policy.get(key)
        for key in DYNAMIC_HISTORY_KEYS
        if policy.get(key) is not None
    }


def _compact_adaptive_prod_history(policy):
    if not isinstance(policy, dict):
        return policy
    return {
        key: policy.get(key)
        for key in ADAPTIVE_PROD_HISTORY_KEYS
        if policy.get(key) is not None
    }


def prune_history_payload(path: Path) -> dict:
    """Bound settled AutoLearn history without removing learning evidence.

    Pending/upcoming forecasts remain byte-for-byte structurally complete so the
    frozen prediction-time evidence is available until settlement. For settled
    rows we remove only duplicated explanatory fields and retain exactly the
    Dynamic Ensemble and Adaptive PROD state consumed by historical telemetry.

    Preserved canonical learning/settlement inputs include:
    - market/pick/line/checkpoint/key/label/source/score/result;
    - model_scores and generator_selected;
    - adaptive_prod_v79.final_score;
    - dynamic_weighting.active;
    - all non-AutoLearn history layers, including Player Intelligence and
      exact Superbet/Symphony training evidence.
    """
    if not path.exists():
        return {'path': _path_label(path), 'status': 'missing'}

    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        return {'path': _path_label(path), 'status': 'skipped-non-list'}

    removed_fields = 0
    compacted_dynamic = 0
    compacted_adaptive_prod = 0
    settled_signals = 0

    for entry in data:
        if not isinstance(entry, dict) or entry.get('status') not in ('settled', 'void'):
            continue
        rows = entry.get('autolearn_signals_v84')
        if not isinstance(rows, list):
            continue
        compacted_rows = []
        for raw in rows:
            if not isinstance(raw, dict):
                compacted_rows.append(raw)
                continue
            signal = dict(raw)
            settled_signals += 1

            policy = signal.get('dynamic_weighting')
            if isinstance(policy, dict):
                compact = _compact_dynamic_history(policy)
                if compact != policy:
                    compacted_dynamic += 1
                signal['dynamic_weighting'] = compact

            adaptive_prod = signal.get('adaptive_prod_v79')
            if isinstance(adaptive_prod, dict):
                compact_prod = _compact_adaptive_prod_history(adaptive_prod)
                if compact_prod != adaptive_prod:
                    compacted_adaptive_prod += 1
                signal['adaptive_prod_v79'] = compact_prod

            for key in SETTLED_AUTOLEARN_REDUNDANT_FIELDS:
                if key in signal:
                    signal.pop(key, None)
                    removed_fields += 1

            compacted_rows.append(signal)
        entry['autolearn_signals_v84'] = compacted_rows

    report = _compact_json(path, data)
    report.update({
        'policy': 'SETTLED_AUTOLEARN_TELEMETRY_MINIMUM_KEEP_TRAINING_AND_SETTLEMENT',
        'settled_autolearn_signals': settled_signals,
        'compacted_dynamic_policies': compacted_dynamic,
        'compacted_adaptive_prod_policies': compacted_adaptive_prod,
        'removed_redundant_fields': removed_fields,
        'training_evidence_removed': False,
        'pending_forecasts_changed': False,
    })
    return report


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
    if path.name == 'history.json':
        return prune_history_payload(path)
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
