from __future__ import annotations

"""Zero-influence progress telemetry for deep MODEL/RAW Symphony.

The deep process is intentionally killed by the parent watchdog when it exceeds
its wall-clock budget.  Until now a timeout only said *that* it was slow, not
*where* the child spent the time.  This adapter writes a tiny atomic JSON marker
at major stages of every MODEL/RAW match so a killed child leaves behind its last
known stage.

It never changes candidates, outcomes, predicates, probability, score, ordering,
POOL_LIMIT, BEAM_WIDTH, training, settlement, operator availability or requests.
"""

import os
import time
from typing import Any

VERSION = "v9.3M-deep-progress-telemetry"
FILENAME = "symphony_model_progress_v93m.json"


class InstalledProgress:
    def __init__(self, deep, fast, core) -> None:
        self.deep = deep
        self.fast = fast
        self.core = core
        self.path = core.OUT / FILENAME
        self.run_token = os.getenv("SYMPHONY_DEEP_RUN_TOKEN") or "standalone"
        self.started = time.monotonic()
        self.completed_matches = 0
        self.current_match_key = None
        self.current_best_of = None
        self.original_build_match = None
        self.original_augment = None
        self.original_outcomes = None
        self.original_compositions = None
        source = core._read(core.RESULTS, [])
        source = source if isinstance(source, list) else []
        self.total_matches = sum(
            1 for row in source
            if isinstance(row, dict) and row.get("model_ready")
        )

    def _write(self, stage: str, **extra: Any) -> None:
        payload = {
            "version": VERSION,
            "run_token": self.run_token,
            "stage": stage,
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
            "completed_matches": int(self.completed_matches),
            "total_model_ready_matches": int(self.total_matches),
            "current_match_key": self.current_match_key,
            "current_best_of": self.current_best_of,
            "production_influence": False,
            "playable_influence": False,
            "prices_used": False,
            "external_requests": 0,
        }
        payload.update(extra)
        self.core._write(self.path, payload)

    def install(self):
        if self.original_build_match is not None:
            return self

        self.original_build_match = self.deep.build_match_model_scenario
        self.original_augment = self.deep._augment_model_raw
        self.original_outcomes = self.deep._build_deep_outcomes
        self.original_compositions = self.fast._fast_one_pass_compositions

        original_build_match = self.original_build_match
        original_augment = self.original_augment
        original_outcomes = self.original_outcomes
        original_compositions = self.original_compositions

        def build_match(match: dict, shadow_for_match: dict, legs: int = 4):
            self.current_match_key = self.core._match_key(match)
            self.current_best_of = self.core._best_of(match)
            self._write("MATCH_START")
            try:
                row = original_build_match(match, shadow_for_match, legs=legs)
            except Exception as exc:
                self._write("MATCH_ERROR", error_type=type(exc).__name__)
                raise
            self.completed_matches += 1
            self._write("MATCH_DONE", row_built=bool(row))
            return row

        def augment(match: dict):
            self._write("AUGMENT_MODEL_RAW")
            return original_augment(match)

        def outcomes(match: dict):
            self._write("BUILD_OUTCOME_LATTICE")
            rows = original_outcomes(match)
            self._write("OUTCOME_LATTICE_DONE", outcome_states=len(rows or []))
            return rows

        def compositions(match: dict, candidates: list, outcomes_rows: list[dict]):
            self._write(
                "BEAM_COMPOSITIONS",
                candidate_count=len(candidates or []),
                outcome_states=len(outcomes_rows or []),
            )
            result = original_compositions(match, candidates, outcomes_rows)
            self._write("BEAM_COMPOSITIONS_DONE", composition_depths=len(result or {}))
            return result

        self.deep.build_match_model_scenario = build_match
        self.deep._augment_model_raw = augment
        self.deep._build_deep_outcomes = outcomes
        self.fast._fast_one_pass_compositions = compositions
        self._write("RUN_START")
        return self

    def finish(self, result: dict | None = None) -> None:
        result = result if isinstance(result, dict) else {}
        self._write("RUN_DONE", result_status=result.get("status"))

    def fail(self, exc: BaseException) -> None:
        self._write("RUN_ERROR", error_type=type(exc).__name__)

    def uninstall(self) -> None:
        if self.original_build_match is None:
            return
        self.deep.build_match_model_scenario = self.original_build_match
        self.deep._augment_model_raw = self.original_augment
        self.deep._build_deep_outcomes = self.original_outcomes
        self.fast._fast_one_pass_compositions = self.original_compositions
        self.original_build_match = None
        self.original_augment = None
        self.original_outcomes = None
        self.original_compositions = None


def install(deep, fast, core) -> InstalledProgress:
    return InstalledProgress(deep, fast, core).install()
