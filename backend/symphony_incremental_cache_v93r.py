from __future__ import annotations

"""Persistent per-match cache for deep MODEL/RAW Symphony.

The v9.3Q beam is exact but a full slate can still exceed the parent 480-second
watchdog.  This adapter changes *scheduling only*: a match result is cached only
after the normal deep builder returns, keyed by an exact fingerprint of the
current match payload, its Shadow evidence, requested leg count and the complete
runtime-engine token.

A later FULL run may reuse that finished row byte-for-byte when the fingerprint
matches.  Cache misses are evaluated in a deterministic cheapest-first order so
a killed child can still leave useful completed rows behind for the next run.
The final report is still produced by the original build_report function and is
sorted by its original rules.

The cache lives under data/cache, which the existing FULL workflow already
restores/saves with Actions cache.  A tiny public telemetry file under
frontend/data exposes only progress counters, never cached scenario rows.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

VERSION = "v9.3R-incremental-exact-match-cache"
CACHE_FILENAME = "symphony_model_match_cache_v93r.json"
TELEMETRY_FILENAME = "symphony_model_incremental_v93r.json"


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _fingerprint(match: dict, shadow_for_match: dict, legs: int, engine_token: str) -> str:
    payload = {
        "engine_token": str(engine_token),
        "legs": int(legs),
        "match": match,
        "shadow_for_match": shadow_for_match,
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _signal_count(match: dict) -> int:
    auto = match.get("autolearn_v84") or {}
    signals = auto.get("signals") or []
    superbet = match.get("superbet_market_v91") or {}
    extra = superbet.get("coverage_shadow_signals") or []
    return len(signals) + len(extra)


def _priority(core, match: dict) -> tuple:
    # BO5 uses the compact exact state adapter and is normally much cheaper than
    # the 306k-state BO3 lattice.  Within the same format, fewer candidate
    # signals generally means fewer beam intersections.  This changes only work
    # order; the legacy report re-sorts completed rows before publication.
    best_of = int(core._best_of(match))
    format_rank = 0 if best_of == 5 else 1
    return (
        format_rank,
        _signal_count(match),
        str(match.get("scheduled_time") or ""),
        str(core._match_key(match) or ""),
    )


class InstalledIncrementalCache:
    def __init__(self, deep, core, engine_token: str) -> None:
        self.deep = deep
        self.core = core
        self.engine_token = str(engine_token)
        self.cache_path = Path(core.ROOT) / "data" / "cache" / CACHE_FILENAME
        self.telemetry_path = core.OUT / TELEMETRY_FILENAME
        self.original_build_report = None

    def _empty_cache(self) -> dict:
        return {
            "version": VERSION,
            "engine_token": self.engine_token,
            "entries": {},
        }

    def _load_cache(self) -> dict:
        raw = self.core._read(self.cache_path, {})
        if not isinstance(raw, dict):
            return self._empty_cache()
        if raw.get("version") != VERSION or raw.get("engine_token") != self.engine_token:
            return self._empty_cache()
        entries = raw.get("entries")
        if not isinstance(entries, dict):
            return self._empty_cache()
        return {
            "version": VERSION,
            "engine_token": self.engine_token,
            "entries": dict(entries),
        }

    def _write_state(self, cache: dict, **stats: Any) -> None:
        cache["version"] = VERSION
        cache["engine_token"] = self.engine_token
        cache.setdefault("entries", {})
        self.core._write(self.cache_path, cache)
        telemetry = {
            "version": VERSION,
            "engine_token": self.engine_token,
            "cache_entries": len(cache.get("entries") or {}),
            "production_influence": False,
            "playable_influence": False,
            "prices_used": False,
            "external_requests": 0,
        }
        telemetry.update(stats)
        self.core._write(self.telemetry_path, telemetry)

    def install(self):
        if self.original_build_report is not None:
            return self
        self.original_build_report = self.deep.build_report
        original_build_report = self.original_build_report
        core = self.core
        deep = self.deep

        def build_report(legs: int = 4) -> dict:
            results = core._read(core.RESULTS, [])
            shadow = core._read(core.SHADOW, {})
            results = results if isinstance(results, list) else []
            shadow = shadow if isinstance(shadow, dict) else {}
            shadow_idx = core._shadow_index(shadow)

            model_ready = [
                row for row in results
                if isinstance(row, dict) and row.get("model_ready")
            ]
            current_keys = {str(core._match_key(row) or "") for row in model_ready}
            cache = self._load_cache()
            entries = {
                key: value
                for key, value in (cache.get("entries") or {}).items()
                if key in current_keys and isinstance(value, dict)
            }
            cache["entries"] = entries

            fingerprints: dict[str, str] = {}
            hits: set[str] = set()
            misses: list[dict] = []
            for match in model_ready:
                key = str(core._match_key(match) or "")
                shadow_for_match = shadow_idx.get(key, {})
                fp = _fingerprint(match, shadow_for_match, int(legs), self.engine_token)
                fingerprints[key] = fp
                entry = entries.get(key)
                if isinstance(entry, dict) and entry.get("fingerprint") == fp and "row" in entry:
                    hits.add(key)
                else:
                    misses.append(match)

            misses.sort(key=lambda row: _priority(core, row))
            hit_rows = [row for row in model_ready if str(core._match_key(row) or "") in hits]
            ordered_model_ready = hit_rows + misses
            model_ready_ids = {id(row) for row in model_ready}
            non_model = [row for row in results if id(row) not in model_ready_ids]
            ordered_results = ordered_model_ready + non_model

            self._write_state(
                cache,
                status="RUNNING",
                cache_hits=len(hits),
                cache_misses=len(misses),
                total_model_ready_matches=len(model_ready),
                pending_entries=len(misses),
                last_attempt_key=None,
                last_completed_key=None,
            )

            original_read = core._read
            current_build_match = deep.build_match_model_scenario
            completed_this_run = 0
            last_completed_key = None

            def ordered_read(path, default=None):
                if path == core.RESULTS:
                    return ordered_results
                return original_read(path, default)

            def cached_build_match(match: dict, shadow_for_match: dict, legs: int = 4):
                nonlocal completed_this_run, last_completed_key
                key = str(core._match_key(match) or "")
                fp = fingerprints.get(key)
                if fp is None:
                    fp = _fingerprint(match, shadow_for_match, int(legs), self.engine_token)
                    fingerprints[key] = fp
                entry = entries.get(key)
                if isinstance(entry, dict) and entry.get("fingerprint") == fp and "row" in entry:
                    return deepcopy(entry.get("row"))

                self._write_state(
                    cache,
                    status="RUNNING",
                    cache_hits=len(hits),
                    cache_misses=len(misses),
                    total_model_ready_matches=len(model_ready),
                    pending_entries=max(0, len(misses) - completed_this_run),
                    completed_this_run=completed_this_run,
                    last_attempt_key=key,
                    last_completed_key=last_completed_key,
                )
                row = current_build_match(match, shadow_for_match, legs=legs)
                entries[key] = {
                    "fingerprint": fp,
                    "row": deepcopy(row),
                }
                completed_this_run += 1
                last_completed_key = key
                self._write_state(
                    cache,
                    status="RUNNING",
                    cache_hits=len(hits),
                    cache_misses=len(misses),
                    total_model_ready_matches=len(model_ready),
                    pending_entries=max(0, len(misses) - completed_this_run),
                    completed_this_run=completed_this_run,
                    last_attempt_key=key,
                    last_completed_key=last_completed_key,
                )
                return row

            core._read = ordered_read
            deep.build_match_model_scenario = cached_build_match
            try:
                report = original_build_report(legs=legs)
            finally:
                deep.build_match_model_scenario = current_build_match
                core._read = original_read

            self._write_state(
                cache,
                status="COMPLETE",
                cache_hits=len(hits),
                cache_misses=len(misses),
                total_model_ready_matches=len(model_ready),
                pending_entries=0,
                completed_this_run=completed_this_run,
                last_attempt_key=last_completed_key,
                last_completed_key=last_completed_key,
            )
            report = dict(report)
            report["incremental_cache_version"] = VERSION
            report["incremental_cache_engine_token"] = self.engine_token
            contract = dict(report.get("contract") or {})
            contract.update({
                "deep_per_match_cache_exact_fingerprint_only": True,
                "deep_cache_changes_work_order_only": True,
                "deep_cached_rows_reused_byte_for_byte": True,
                "deep_cache_actions_cache_only_not_model_input": True,
                "deep_incremental_cache_version": VERSION,
            })
            report["contract"] = contract
            return report

        self.deep.build_report = build_report
        return self

    def uninstall(self) -> None:
        if self.original_build_report is None:
            return
        self.deep.build_report = self.original_build_report
        self.original_build_report = None


def install(deep, core, engine_token: str) -> InstalledIncrementalCache:
    return InstalledIncrementalCache(deep, core, engine_token).install()
