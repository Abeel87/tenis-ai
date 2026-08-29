from __future__ import annotations

import json
from pathlib import Path

from backend import symphony_incremental_cache_v93r as cache_mod


class FakeCore:
    def __init__(self, tmp_path: Path, results: list[dict], shadow: dict):
        self.ROOT = tmp_path
        self.OUT = tmp_path / "frontend" / "data"
        self.RESULTS = tmp_path / "results.json"
        self.SHADOW = tmp_path / "shadow.json"
        self._memory = {
            self.RESULTS: results,
            self.SHADOW: shadow,
        }

    def _read(self, path, default=None):
        path = Path(path)
        if path in self._memory:
            return self._memory[path]
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return default

    def _write(self, path, payload):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _match_key(match):
        return str(match.get("id"))

    @staticmethod
    def _best_of(match):
        return int(match.get("best_of") or 3)

    @staticmethod
    def _shadow_index(shadow):
        return dict(shadow)


class FakeDeep:
    def __init__(self, core: FakeCore):
        self.core = core
        self.calls: list[str] = []

    def build_match_model_scenario(self, match, shadow_for_match, legs=4):
        key = self.core._match_key(match)
        self.calls.append(key)
        if match.get("returns_none"):
            return None
        return {
            "match_key": key,
            "symphony_score": float(match.get("score") or 0.0),
            "payload_marker": match.get("payload_marker"),
            "shadow_marker": shadow_for_match.get("marker"),
            "legs": int(legs),
        }

    def build_report(self, legs=4):
        results = self.core._read(self.core.RESULTS, [])
        shadow = self.core._read(self.core.SHADOW, {})
        shadow_idx = self.core._shadow_index(shadow)
        rows = []
        for match in results:
            if not isinstance(match, dict) or not match.get("model_ready"):
                continue
            key = self.core._match_key(match)
            row = self.build_match_model_scenario(match, shadow_idx.get(key, {}), legs=legs)
            if row:
                rows.append(row)
        rows.sort(key=lambda row: -float(row.get("symphony_score") or 0.0))
        return {
            "version": "fake-deep",
            "matches_count": len(rows),
            "matches": rows,
            "contract": {"legacy_report_builder_used": True},
        }


def _results():
    return [
        {
            "id": 1,
            "model_ready": True,
            "best_of": 3,
            "score": 91,
            "payload_marker": "bo3-heavy",
            "autolearn_v84": {"signals": [{"x": i} for i in range(9)]},
        },
        {
            "id": 2,
            "model_ready": True,
            "best_of": 5,
            "score": 88,
            "payload_marker": "bo5-compact",
            "autolearn_v84": {"signals": [{"x": i} for i in range(12)]},
        },
        {
            "id": 3,
            "model_ready": True,
            "best_of": 3,
            "score": 84,
            "payload_marker": "bo3-light",
            "autolearn_v84": {"signals": [{"x": i} for i in range(2)]},
        },
        {
            "id": 4,
            "model_ready": True,
            "best_of": 5,
            "score": 10,
            "returns_none": True,
            "autolearn_v84": {"signals": []},
        },
        {"id": 999, "model_ready": False},
    ]


def test_v93r_reuses_only_exact_fingerprint_rows_and_preserves_report(tmp_path):
    results = _results()
    shadow = {
        "1": {"marker": "s1"},
        "2": {"marker": "s2"},
        "3": {"marker": "s3"},
        "4": {"marker": "s4"},
    }
    core = FakeCore(tmp_path, results, shadow)
    deep = FakeDeep(core)
    adapter = cache_mod.install(deep, core, "engine-A")
    try:
        first = deep.build_report(legs=4)
        # Cheapest-first scheduling: compact BO5 rows first (including the None
        # row), then BO3 by candidate-signal count.
        assert deep.calls == ["4", "2", "3", "1"]
        assert [row["match_key"] for row in first["matches"]] == ["1", "2", "3"]
        assert first["contract"]["legacy_report_builder_used"] is True
        assert first["contract"]["deep_cache_changes_work_order_only"] is True

        deep.calls.clear()
        second = deep.build_report(legs=4)
        assert deep.calls == []
        assert second == first

        # Change one exact match input.  Only that row must be rebuilt; all other
        # fingerprints, including a cached None result, remain reusable.
        results[2]["payload_marker"] = "bo3-light-updated"
        deep.calls.clear()
        third = deep.build_report(legs=4)
        assert deep.calls == ["3"]
        row3 = next(row for row in third["matches"] if row["match_key"] == "3")
        assert row3["payload_marker"] == "bo3-light-updated"

        telemetry = json.loads(
            (core.OUT / cache_mod.TELEMETRY_FILENAME).read_text(encoding="utf-8")
        )
        assert telemetry["status"] == "COMPLETE"
        assert telemetry["pending_entries"] == 0
        assert telemetry["cache_entries"] == 4
        assert telemetry["production_influence"] is False
        assert telemetry["prices_used"] is False
    finally:
        adapter.uninstall()


def test_v93r_engine_token_invalidates_previous_rows(tmp_path):
    results = _results()[:2]
    core = FakeCore(tmp_path, results, {"1": {}, "2": {}})
    deep = FakeDeep(core)

    first = cache_mod.install(deep, core, "engine-A")
    try:
        deep.build_report(legs=4)
        assert deep.calls == ["2", "1"]
    finally:
        first.uninstall()

    deep.calls.clear()
    second = cache_mod.install(deep, core, "engine-B")
    try:
        deep.build_report(legs=4)
        assert deep.calls == ["2", "1"]
        cache = json.loads(
            (tmp_path / "data" / "cache" / cache_mod.CACHE_FILENAME).read_text(encoding="utf-8")
        )
        assert cache["engine_token"] == "engine-B"
    finally:
        second.uninstall()
