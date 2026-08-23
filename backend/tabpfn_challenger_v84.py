from __future__ import annotations

import json
import sys
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def frame(rows, numeric, categorical, categories=None):
    import pandas as pd
    raw = []
    for r in rows or []:
        row = {}
        for c in numeric:
            try: row[c] = float(r.get(c) if r.get(c) is not None else 0.0)
            except (TypeError, ValueError): row[c] = 0.0
        for c in categorical:
            row[c] = str(r.get(c) or "N/D")
        raw.append(row)
    df = pd.DataFrame(raw, columns=[*numeric, *categorical])
    if df.empty:
        return df, categories or []
    encoded = pd.get_dummies(df, columns=categorical, dtype=float)
    if categories is None:
        categories = list(encoded.columns)
    encoded = encoded.reindex(columns=categories, fill_value=0.0)
    return encoded, categories


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: tabpfn_challenger_v84.py input.json output.json")
    inp, out = sys.argv[1], sys.argv[2]
    try:
        payload = read(inp)
        from tabpfn import TabPFNClassifier
        from tabpfn.constants import ModelVersion

        train = payload.get("train") or []
        cal = payload.get("cal") or []
        val = payload.get("val") or []
        current = payload.get("current") or []
        numeric = payload.get("numeric_features") or []
        categorical = payload.get("categorical_features") or []
        if len(train) < 20 or len({int(r.get("target")) for r in train}) < 2:
            write(out, {"status": "unavailable", "reason": "insufficient_training_data"}); return

        all_for_schema = [*train, *cal, *val, *current]
        _, columns = frame(all_for_schema, numeric, categorical)
        X_train, _ = frame(train, numeric, categorical, columns)
        X_cal, _ = frame(cal, numeric, categorical, columns)
        X_val, _ = frame(val, numeric, categorical, columns)
        X_current, _ = frame(current, numeric, categorical, columns)
        y_train = [int(r.get("target")) for r in train]

        # IMPORTANT: explicit V2. Never use the package default (V2.5/V2.6/V3).
        clf = TabPFNClassifier.create_default_for_version(
            ModelVersion.V2,
            n_estimators=1,
            device="cpu",
            show_progress_bar=False,
            random_state=42,
        )
        clf.fit(X_train, y_train)
        prob = lambda X: [] if len(X) == 0 else [float(x[1]) for x in clf.predict_proba(X)]
        write(out, {
            "status": "ok",
            "model_version": "V2",
            "train_rows": len(train),
            "features": len(columns),
            "cal_probs": prob(X_cal),
            "val_probs": prob(X_val),
            "current_probs": prob(X_current),
            "current_indices": payload.get("current_indices") or [],
        })
    except ModuleNotFoundError as exc:
        write(out, {"status": "unavailable", "reason": f"missing_package:{exc.name}"})
    except Exception as exc:
        write(out, {"status": "unavailable", "reason": type(exc).__name__, "detail": str(exc)[:300]})


if __name__ == "__main__":
    main()
