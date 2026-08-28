from __future__ import annotations

"""Tenis AI v9.1.5 — lightweight Symphony operator reprojection.

The expensive Symphony path/scenario search is intentionally NOT rerun here.
A full build still owns that work. Hourly Superbet refreshes only re-gate the
already computed Symphony compositions against the newest verified Superbet
market catalogue and rebuild the compact match-card feed afterwards.

v9.1.5 also rewrites ``full_composition`` from the already filtered PLAYABLE
compositions. This prevents the match-detail UI from accidentally preferring an
older RAW six-leg composition containing a market/line that is not currently
available at Superbet.
"""

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

try:
    from .superbet_playable_v912 import (
        is_operator_playable_signal,
        operator_context_active,
        operator_model_signals,
        signal_signature,
    )
except ImportError:
    from superbet_playable_v912 import (
        is_operator_playable_signal,
        operator_context_active,
        operator_model_signals,
        signal_signature,
    )

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
RESULTS = DATA / "results.json"
REPORT = DATA / "symphony_v90.json"
VERSION = "v9.1.5"


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _match_key(row: dict) -> str:
    mid = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join(
        str(row.get(k) or "") for k in ("p1", "p2", "scheduled_time")
    )


def _results_index(results: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in results or []:
        if not isinstance(row, dict):
            continue
        out[_match_key(row)] = row
        mid = row.get("match_id") if row.get("match_id") is not None else row.get("id")
        if mid is not None:
            out[str(mid)] = row
    return out


def _score(comp: dict) -> float:
    try:
        return float(comp.get("symphony_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _refresh_leg(leg: dict, verified: dict) -> dict:
    out = dict(leg)
    row = verified.get(signal_signature(out))
    if isinstance(row, dict):
        for key in ("key", "label", "market", "pick", "line", "checkpoint", "player"):
            if row.get(key) is not None:
                out[key] = row.get(key)
        if row.get("score") is not None:
            out["operator_model_score"] = row.get("score")
        out.update({
            "operator": "superbet.pl",
            "operator_available": True,
            "operator_line_verified": True,
            "operator_projection_version": VERSION,
        })
    return out


def _playable_candidate(match: dict, raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    selection = [dict(x) for x in (raw.get("selection") or []) if isinstance(x, dict)]
    if not selection:
        return None
    if not all(is_operator_playable_signal(match, leg) for leg in selection):
        return None

    verified = operator_model_signals(match)
    out = deepcopy(raw)
    out["selection"] = [_refresh_leg(leg, verified) for leg in selection]
    out["operator_reprojected"] = True
    out["operator_projection_version"] = VERSION
    return out


def _best_valid_for_leg_count(match: dict, raw: dict, n: int) -> tuple[dict | None, int]:
    """Keep the original primary when still valid; otherwise promote best valid alt."""
    candidates = []
    primary = _playable_candidate(match, raw)
    if primary is not None:
        candidates.append((True, primary))

    for alt in (raw.get("alternatives") or []) if isinstance(raw, dict) else []:
        checked = _playable_candidate(match, alt)
        if checked is not None:
            candidates.append((False, checked))

    if not candidates:
        return None, 0

    if candidates[0][0]:
        chosen = candidates[0][1]
        rest = [x[1] for x in candidates[1:]]
    else:
        ordered = sorted((x[1] for x in candidates), key=_score, reverse=True)
        chosen, rest = ordered[0], ordered[1:]

    chosen = dict(chosen)
    chosen["legs"] = int(chosen.get("legs") or n)
    chosen["alternatives"] = rest
    return chosen, len(candidates)


def _playable_full_composition(new_comps: dict[str, dict]) -> dict | None:
    """Return the largest already-verified PLAYABLE composition for match detail."""
    for n in (6, 5, 4, 3, 2):
        comp = new_comps.get(str(n))
        if isinstance(comp, dict) and comp.get("selection"):
            out = deepcopy(comp)
            out["legs"] = n
            out["operator_reprojected"] = True
            out["operator_projection_version"] = VERSION
            return out
    return None


def reproject_match(report_match: dict, result_match: dict | None) -> tuple[dict, dict]:
    row = deepcopy(report_match)
    if not isinstance(result_match, dict) or not operator_context_active(result_match):
        row["operator_reprojection"] = {
            "version": VERSION,
            "active": False,
            "status": "NO_VERIFIED_OPERATOR_MATCH",
        }
        return row, {"active": False, "kept": 0, "dropped": 0}

    old_comps = row.get("compositions") or {}
    new_comps: dict[str, dict] = {}
    kept_candidates = 0
    dropped_leg_counts = 0

    for n in (2, 3, 4, 5, 6):
        raw = old_comps.get(str(n)) if isinstance(old_comps, dict) else None
        if not isinstance(raw, dict):
            continue
        chosen, candidate_count = _best_valid_for_leg_count(result_match, raw, n)
        if chosen is None:
            dropped_leg_counts += 1
            continue
        kept_candidates += candidate_count
        new_comps[str(n)] = chosen

    row["compositions"] = new_comps
    # Critical UI contract: match detail must never prefer stale RAW full_composition.
    # Rebuild it only from already gated Superbet PLAYABLE compositions.
    row["full_composition"] = _playable_full_composition(new_comps)

    try:
        old_recommended = int(row.get("recommended_leg_count"))
    except (TypeError, ValueError):
        old_recommended = 2

    if str(old_recommended) in new_comps:
        recommended = old_recommended
    elif new_comps:
        recommended = int(max(new_comps.items(), key=lambda item: _score(item[1]))[0])
    else:
        recommended = 0

    row["recommended_leg_count"] = recommended or None
    row["operator_reprojection"] = {
        "version": VERSION,
        "active": True,
        "status": "PLAYABLE_SUPERBET_ONLY" if new_comps else "NO_PLAYABLE_COMPOSITION",
        "verified_operator_match": True,
        "kept_leg_counts": sorted(int(x) for x in new_comps),
        "dropped_leg_counts": dropped_leg_counts,
        "full_scenario_search_rerun": False,
        "full_composition_source": "playable_compositions_only",
    }
    return row, {
        "active": True,
        "kept": len(new_comps),
        "dropped": dropped_leg_counts,
        "candidates": kept_candidates,
    }


def reproject_report(report: dict, results: list[dict]) -> tuple[dict, dict]:
    out = deepcopy(report) if isinstance(report, dict) else {}
    index = _results_index(results)
    rows = []
    active = kept = dropped = candidates = 0

    for raw in out.get("matches") or []:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("match_key") or _match_key(raw))
        result_match = index.get(key)
        if result_match is None and raw.get("id") is not None:
            result_match = index.get(str(raw.get("id")))
        row, info = reproject_match(raw, result_match)
        active += int(info.get("active", False))
        kept += int(info.get("kept", 0))
        dropped += int(info.get("dropped", 0))
        candidates += int(info.get("candidates", 0))
        rows.append(row)

    out["matches"] = rows
    out["operator_reprojection_version"] = VERSION
    out["operator_reprojected_at"] = datetime.now(timezone.utc).isoformat()
    out["operator_reprojection"] = {
        "mode": "LIGHTWEIGHT_EXISTING_SCENARIOS_ONLY",
        "full_scenario_search_rerun": False,
        "operator_context_matches": active,
        "playable_leg_count_compositions": kept,
        "dropped_leg_count_compositions": dropped,
        "playable_candidates_seen": candidates,
        "prices_used": False,
    }
    return out, out["operator_reprojection"]


def run() -> dict:
    results = _read(RESULTS, [])
    report = _read(REPORT, {})
    if not isinstance(results, list) or not results:
        raise RuntimeError("results.json missing/empty")
    if not isinstance(report, dict) or not isinstance(report.get("matches"), list):
        raise RuntimeError("symphony_v90.json missing/invalid")

    out, info = reproject_report(report, results)
    _write(REPORT, out)
    return {
        "status": "OK",
        "version": VERSION,
        **info,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
