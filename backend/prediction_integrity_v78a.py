from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS = OUT / "results.json"
REPORT = OUT / "integrity_report_v78a.json"
META = OUT / "meta.json"

PAIR_TOL = 0.35
SUM_TOL = 0.65


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _prob(x):
    v = _num(x)
    return v is not None and 0.0 <= v <= 100.0


def _near(a, b, tol):
    return abs(float(a) - float(b)) <= float(tol)


def apply_pre_output_guards(match: dict) -> dict:
    """Fail-safe output guard. First-set data remains valid for BO5; full-match BO3 does not."""
    m = dict(match)
    try:
        best_of = 5 if int(m.get("best_of") or 3) == 5 else 3
    except (TypeError, ValueError):
        best_of = 3
    m["best_of"] = best_of
    if best_of == 5:
        for key in ("match_win", "match_over_under", "expected_match_games", "total_sets", "exact_match_score"):
            m[key] = None
        m["bo5_guard_v78a"] = True
    return m


def _sum100(name, obj, errors, tag):
    if not obj:
        return
    vals = []
    for key, value in obj.items():
        if not _prob(value):
            errors.append(f"{tag}: {name}.{key} poza zakresem 0..100")
            return
        vals.append(float(value))
    if not _near(sum(vals), 100.0, SUM_TOL):
        errors.append(f"{tag}: {name} suma={sum(vals):.2f}, oczekiwano 100")


def _check_ou(name, obj, errors, tag):
    if not obj:
        return
    points = []
    for line, row in obj.items():
        over = _num((row or {}).get("over"))
        under = _num((row or {}).get("under"))
        if over is None or under is None or not _prob(over) or not _prob(under):
            errors.append(f"{tag}: {name} {line} ma błędne O/U")
            continue
        if not _near(over + under, 100.0, PAIR_TOL):
            errors.append(f"{tag}: {name} {line}: O+U={over+under:.2f}")
        try:
            points.append((float(line), float(over)))
        except (TypeError, ValueError):
            errors.append(f"{tag}: {name} ma błędną linię {line}")
    points.sort()
    for i in range(len(points) - 1):
        a_line, a_over = points[i]
        b_line, b_over = points[i + 1]
        if b_over > a_over + 0.25:
            errors.append(
                f"{tag}: {name} niemonotoniczne OVER: {a_line}={a_over:.1f}% -> {b_line}={b_over:.1f}%"
            )


def check_match(match: dict):
    errors, warnings = [], []
    tag = f"{match.get('p1','?')} vs {match.get('p2','?')} [{match.get('id','?')}]"

    for name in (
        "match_win", "first_set_win", "second_set_win", "third_set_win",
        "total_sets", "exact_match_score", "exact_first_set",
    ):
        _sum100(name, match.get(name), errors, tag)

    _check_ou("over_under", match.get("over_under"), errors, tag)
    _check_ou("match_over_under", match.get("match_over_under"), errors, tag)

    for checkpoint, states in (match.get("game_states") or {}).items():
        _sum100(f"game_states.{checkpoint}", states, errors, tag)

    for checkpoint, row in ((match.get("early_hold_v7") or {}).get("checkpoint_breakdown") or {}).items():
        total = _num((row or {}).get("total"))
        clean = _num((row or {}).get("clean_holds"))
        breaks = _num((row or {}).get("with_breaks"))
        if None in (total, clean, breaks):
            errors.append(f"{tag}: PBP checkpoint {checkpoint} uszkodzony")
            continue
        if clean > total + 0.25:
            errors.append(f"{tag}: PBP checkpoint {checkpoint}: clean_holds > total")
        if not _near(clean + breaks, total, 0.35):
            errors.append(f"{tag}: PBP checkpoint {checkpoint}: clean + breaks != total")

    try:
        best_of = 5 if int(match.get("best_of") or 3) == 5 else 3
    except (TypeError, ValueError):
        best_of = 3
    if best_of == 5:
        for key in ("match_win", "match_over_under", "expected_match_games", "total_sets", "exact_match_score"):
            if match.get(key) not in (None, {}, []):
                errors.append(f"{tag}: BO5 guard — {key} powinno być N/D")
        serve = match.get("serve_props_v72") or {}
        if serve.get("ready"):
            errors.append(f"{tag}: BO5 guard — Serve Props BO3 nie może być READY")
        lab = match.get("market_lab_v741") or {}
        if lab and lab.get("status") not in ("LAB_SET1_ONLY",):
            errors.append(f"{tag}: BO5 guard — pełny Market Lab BO3 nie może być publikowany")
    elif match.get("model_ready") and not match.get("best_of"):
        warnings.append(f"{tag}: best_of brak — fallback BO3")

    return errors, warnings


def validate(results):
    rows = results if isinstance(results, list) else []
    errors, warnings = [], []
    for match in rows:
        e, w = check_match(match)
        errors.extend(e)
        warnings.extend(w)
    return {
        "version": "v7.8A",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "matches": len(rows),
        "hard_errors": len(errors),
        "warnings": len(warnings),
        "status": "PASS" if not errors else "FAIL",
        "errors": errors[:250],
        "warning_messages": warnings[:250],
        "rules": [
            "probability sums",
            "OVER/UNDER complements",
            "OVER monotonic by line",
            "game-state mass",
            "PBP clean-hold decomposition",
            "BO5 fail-safe",
        ],
    }


def main():
    rows = _read(RESULTS, [])
    report = validate(rows)
    _write(REPORT, report)

    meta = _read(META, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "integrity_v78a_status": report["status"],
        "integrity_v78a_errors": report["hard_errors"],
        "integrity_v78a_warnings": report["warnings"],
        "integrity_v78a_updated_at": report["updated_at"],
    })
    _write(META, meta)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["hard_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
