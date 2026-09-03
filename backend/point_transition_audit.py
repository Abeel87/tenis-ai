from __future__ import annotations

"""Empirical zero-network audit of cached point-state transition semantics.

This deliberately does NOT define the canonical training schema yet.  It inspects
real cached rows and measures whether provider states behave like pre-point or
post-point snapshots, how often server / winner are present, and what shapes the
score arrays actually have.
"""

from collections import Counter
import gzip
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "point_transition_audit.json"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _shape(value: Any) -> str:
    if isinstance(value, list):
        inner = ",".join(_shape(v) for v in value[:4])
        return f"list[{len(value)}]({inner})"
    if isinstance(value, dict):
        return "dict{" + ",".join(sorted(map(str, value.keys()))[:8]) + "}"
    return type(value).__name__


def _score_signature(row: dict[str, Any]) -> tuple[str, str, str]:
    return (repr(row.get("sets")), repr(row.get("games")), repr(row.get("points")))


def _winner(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value in (1, 2):
        return value
    return None


def audit_payload(payload: dict[str, Any], sample_limit: int = 12) -> dict[str, Any]:
    tape = payload.get("tape")
    rows = [r for r in tape if isinstance(r, dict)] if isinstance(tape, list) else []

    shapes = {k: Counter() for k in ("sets", "games", "points")}
    winner_values: Counter[str] = Counter()
    server_values: Counter[str] = Counter()
    transition_kinds: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []

    for row in rows:
        for key in shapes:
            shapes[key][_shape(row.get(key))] += 1
        winner_values[repr(row.get("point_winner"))] += 1
        server_values[repr(row.get("server"))] += 1

    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        prev_sig, cur_sig = _score_signature(prev), _score_signature(cur)
        score_changed = prev_sig != cur_sig
        winner_cur = _winner(cur.get("point_winner"))
        winner_prev = _winner(prev.get("point_winner"))
        server_same = prev.get("server") == cur.get("server")

        if not score_changed:
            kind = "same_score"
        elif prev.get("sets") != cur.get("sets"):
            kind = "set_score_changed"
        elif prev.get("games") != cur.get("games"):
            kind = "game_score_changed"
        else:
            kind = "point_score_changed"
        transition_kinds[kind] += 1

        if len(samples) < sample_limit and score_changed:
            samples.append({
                "row_index_prev": i - 1,
                "row_index_cur": i,
                "prev": {
                    "sets": prev.get("sets"),
                    "games": prev.get("games"),
                    "points": prev.get("points"),
                    "server": prev.get("server"),
                    "point_winner": prev.get("point_winner"),
                    "is_tiebreak": prev.get("is_tiebreak"),
                },
                "cur": {
                    "sets": cur.get("sets"),
                    "games": cur.get("games"),
                    "points": cur.get("points"),
                    "server": cur.get("server"),
                    "point_winner": cur.get("point_winner"),
                    "is_tiebreak": cur.get("is_tiebreak"),
                },
                "winner_present_prev": winner_prev is not None,
                "winner_present_cur": winner_cur is not None,
                "server_same": server_same,
                "kind": kind,
            })

    return {
        "rows": len(rows),
        "shapes": {k: dict(v.most_common()) for k, v in shapes.items()},
        "winner_values": dict(winner_values.most_common()),
        "server_values": dict(server_values.most_common()),
        "transition_kinds": dict(transition_kinds.most_common()),
        "samples": samples,
    }


def main() -> int:
    matches = 0
    rows = 0
    shape_counts = {k: Counter() for k in ("sets", "games", "points")}
    winner_values: Counter[str] = Counter()
    server_values: Counter[str] = Counter()
    transition_kinds: Counter[str] = Counter()
    sample_matches: list[dict[str, Any]] = []

    if CACHE.exists():
        for path in sorted(CACHE.glob("*.json.gz")):
            payload = _read(path)
            if payload is None:
                continue
            report = audit_payload(payload)
            if report["rows"] <= 0:
                continue
            matches += 1
            rows += int(report["rows"])
            for key in shape_counts:
                shape_counts[key].update(report["shapes"][key])
            winner_values.update(report["winner_values"])
            server_values.update(report["server_values"])
            transition_kinds.update(report["transition_kinds"])
            if len(sample_matches) < 6:
                sample_matches.append({"match_id": path.name.removesuffix(".json.gz"), **report})

    out = {
        "version": "point-transition-audit-v1",
        "source": "data/cache/pbp_v7/matches/*.json.gz",
        "network_calls": 0,
        "matches": matches,
        "rows": rows,
        "score_shapes": {k: dict(v.most_common()) for k, v in shape_counts.items()},
        "point_winner_values": dict(winner_values.most_common()),
        "server_values": dict(server_values.most_common()),
        "transition_kinds": dict(transition_kinds.most_common()),
        "sample_matches": sample_matches,
        "decision": "UNRESOLVED_UNTIL_REVIEWED",
        "note": "Samples are diagnostic only; no pre/post semantics are assumed by this script.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "matches": matches,
        "rows": rows,
        "score_shapes": out["score_shapes"],
        "transition_kinds": out["transition_kinds"],
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
