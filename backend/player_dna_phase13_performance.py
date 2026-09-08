from __future__ import annotations

"""Phase-13 observational performance audit for the canonical Player DNA pipeline.

This module does not implement a second profile, matchup, or simulation path.
It consumes measurements emitted by the canonical profile builder and benchmarks
the already-canonical Phase-3 matchup packet plus the existing Phase-6 Monte
Carlo primitive. Absolute latency is observed, never used as a promotion or CI
threshold.
"""

import gzip
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Callable

try:
    from backend.player_dna_matchup_engine import build_matchup_packet
    from backend.player_dna_tennis_simulator import monte_carlo_match_distribution
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_matchup_engine import build_matchup_packet
    from player_dna_tennis_simulator import monte_carlo_match_distribution

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_phase13_performance.json"
POINT_SUMMARY = ROOT / "frontend" / "data" / "player_dna_point_dataset_summary.json"
PROFILE_SUMMARY = ROOT / "frontend" / "data" / "player_dna_shadow_profile_summary.json"
SCORER_REPORT = ROOT / "frontend" / "data" / "player_dna_point_scorer.json"
PHASE12_REPORT = ROOT / "frontend" / "data" / "player_dna_phase12_master_regression.json"
CURRENT_SHADOW = ROOT / "frontend" / "data" / "player_dna_current_shadow.json"
PROFILE_SNAPSHOTS = ROOT / "data" / "derived" / "player_dna" / "profile_snapshots.jsonl.gz"

VERSION = "player-dna-phase13-performance-benchmark"
MODE = "SHADOW_PHASE13_PERFORMANCE_AUDIT_ONLY"
SIMULATION_SIZES = (10_000, 50_000, 100_000)
MATCHUP_ITERATIONS = 2_000
BENCHMARK_SEED = 260913


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _fingerprint(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _process_peak_rss_bytes() -> int | None:
    """Best-effort process high-water RSS without adding a runtime dependency."""
    try:
        import resource
    except ImportError:
        return None
    try:
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (ValueError, OSError):
        return None
    # Linux reports KiB; macOS reports bytes.
    return value if sys.platform == "darwin" else value * 1024


def _timed(call: Callable[[], Any]) -> tuple[Any, float, int | None]:
    started = time.perf_counter()
    result = call()
    elapsed = time.perf_counter() - started
    return result, elapsed, _process_peak_rss_bytes()


def _actual_profile_pair(
    path: Path = PROFILE_SNAPSHOTS,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    if not path.exists():
        return None
    pending: dict[str, dict[str, dict[str, Any]]] = {}
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                match_id = str(row.get("target_match_id") or "").strip()
                side = str(row.get("player_side") or "").strip()
                if not match_id or side not in {"p1", "p2"}:
                    continue
                sides = pending.setdefault(match_id, {})
                sides[side] = row
                if "p1" not in sides or "p2" not in sides:
                    continue
                p1 = sides["p1"]
                p2 = sides["p2"]
                # Prefer a real matchup that actually carries prior profile
                # evidence rather than the earliest all-zero historical pair.
                p1_prior = p1.get("overall_prior") or {}
                p2_prior = p2.get("overall_prior") or {}
                if (
                    int(p1_prior.get("matches") or 0) <= 0
                    or int(p2_prior.get("matches") or 0) <= 0
                ):
                    continue
                fmt = str(p1.get("target_format") or "BO3").strip().upper()
                best_of = 5 if fmt == "BO5" else 3
                target = {
                    "id": match_id,
                    "surface": p1.get("target_surface"),
                    "tour": p1.get("target_tour"),
                    "best_of": best_of,
                }
                return target, p1, p2
    except OSError:
        return None
    return None


def benchmark_matchup(
    target: dict[str, Any],
    p1_profile: dict[str, Any],
    p2_profile: dict[str, Any],
    *,
    iterations: int = MATCHUP_ITERATIONS,
) -> dict[str, Any]:
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
        raise ValueError("iterations must be a positive integer")

    # One warm-up uses the exact same canonical function but is not timed.
    build_matchup_packet(target, p1_profile, p2_profile)

    last: dict[str, Any] | None = None

    def run() -> None:
        nonlocal last
        for _ in range(iterations):
            last = build_matchup_packet(target, p1_profile, p2_profile)

    _, elapsed, peak_rss = _timed(run)
    if last is None:
        raise AssertionError("canonical matchup benchmark produced no packet")
    return {
        "source": "CANONICAL_PHASE3_BUILD_MATCHUP_PACKET",
        "real_profile_snapshot_pair": True,
        "target_match_id": str(target.get("id")),
        "iterations": iterations,
        "total_seconds": elapsed,
        "mean_microseconds_per_matchup": (elapsed * 1_000_000.0) / iterations,
        "process_peak_rss_bytes_after_stage": peak_rss,
        "output_fingerprint_sha256": _fingerprint(last),
        "absolute_latency_gate_enabled": False,
    }


def _simulation_input(current: dict[str, Any]) -> dict[str, Any]:
    matches = current.get("matches") if isinstance(current, dict) else None
    for row in matches if isinstance(matches, list) else []:
        if not isinstance(row, dict) or row.get("status") != "SHADOW_SCORED":
            continue
        try:
            p1 = float(row.get("p1_serve_point_win_probability"))
            p2 = float(row.get("p2_serve_point_win_probability"))
        except (TypeError, ValueError):
            continue
        best_of = row.get("best_of")
        if best_of not in (3, 5):
            best_of = 3
        if 0.0 <= p1 <= 1.0 and 0.0 <= p2 <= 1.0:
            return {
                "source": "CURRENT_SHADOW_SCORED_MATCH",
                "match_id": row.get("match_id"),
                "p1_serve_point_win": p1,
                "p2_serve_point_win": p2,
                "best_of": int(best_of),
            }

    # Stable Phase-6 reference is only a benchmark input fallback when the
    # current card contains no SHADOW_SCORED row. It does not create a runtime
    # path and never changes model or operator output.
    return {
        "source": "CANONICAL_PHASE6_REFERENCE_FALLBACK_NO_CURRENT_SHADOW_MATCH",
        "match_id": None,
        "p1_serve_point_win": 0.63,
        "p2_serve_point_win": 0.59,
        "best_of": 3,
    }


def benchmark_simulation(
    simulation_input: dict[str, Any],
    *,
    simulations: int,
    seed: int = BENCHMARK_SEED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    p1 = float(simulation_input["p1_serve_point_win"])
    p2 = float(simulation_input["p2_serve_point_win"])
    best_of = int(simulation_input["best_of"])

    result, elapsed, peak_rss = _timed(
        lambda: monte_carlo_match_distribution(
            p1,
            p2,
            best_of=best_of,
            simulations=simulations,
            seed=seed,
        )
    )
    measurement = {
        "simulations": simulations,
        "seed": seed,
        "seconds": elapsed,
        "simulations_per_second": simulations / elapsed if elapsed > 0.0 else None,
        "process_peak_rss_bytes_after_stage": peak_rss,
        "result_fingerprint_sha256": _fingerprint(result),
        "absolute_latency_gate_enabled": False,
    }
    return result, measurement


def evaluate_phase13_completion(report: dict[str, Any]) -> bool:
    """Gate completeness of measurement, never the absolute speed observed."""
    prerequisite = report.get("prerequisite") or {}
    cache_join = report.get("cache_and_join") or {}
    profile = report.get("profile_build") or {}
    matchup = report.get("matchup") or {}
    simulation = report.get("simulation") or {}
    runtime = report.get("ci_runtime_cost") or {}

    rows = simulation.get("benchmarks") or []
    sizes = [int(row.get("simulations") or 0) for row in rows]
    times_measured = bool(
        rows
        and all(
            isinstance(row.get("seconds"), (int, float))
            and not isinstance(row.get("seconds"), bool)
            and float(row["seconds"]) > 0.0
            for row in rows
        )
    )

    return bool(
        prerequisite.get("phase12_complete") is True
        and prerequisite.get("phase13_ready") is True
        and int(cache_join.get("strict_context_ready_point_rows") or 0) > 0
        and int(cache_join.get("scorer_joined_rows") or 0)
        == int(cache_join.get("strict_context_ready_point_rows") or 0)
        and float(cache_join.get("scorer_join_coverage") or 0.0) == 1.0
        and int(profile.get("profile_snapshots") or 0) > 0
        and isinstance(profile.get("canonical_build_seconds"), (int, float))
        and float(profile.get("canonical_build_seconds") or 0.0) > 0.0
        and isinstance(profile.get("process_peak_rss_bytes_after_build"), (int, float))
        and int(profile.get("process_peak_rss_bytes_after_build") or 0) > 0
        and matchup.get("real_profile_snapshot_pair") is True
        and int(matchup.get("iterations") or 0) > 0
        and isinstance(matchup.get("total_seconds"), (int, float))
        and float(matchup.get("total_seconds") or 0.0) > 0.0
        and sizes == list(SIMULATION_SIZES)
        and times_measured
        and all(
            isinstance(row.get("process_peak_rss_bytes_after_stage"), (int, float))
            and int(row.get("process_peak_rss_bytes_after_stage") or 0) > 0
            for row in rows
        )
        and simulation.get("deterministic_seed_replay") is True
        and isinstance(runtime.get("phase13_step_wall_seconds"), (int, float))
        and float(runtime.get("phase13_step_wall_seconds") or 0.0) > 0.0
        and isinstance(runtime.get("process_peak_rss_bytes_after_phase13"), (int, float))
        and int(runtime.get("process_peak_rss_bytes_after_phase13") or 0) > 0
        and report.get("performance_thresholds_enforced") is False
        and report.get("benchmark_results_observational_only") is True
        and report.get("production_influence") is False
        and report.get("runtime_prediction_change") is False
        and report.get("symphony2_influence") is False
        and report.get("superbet_playable_influence") is False
        and report.get("auto_promote") is False
    )


def build() -> dict[str, Any]:
    phase_started = time.perf_counter()

    point_summary = _read_json(POINT_SUMMARY)
    profile_summary = _read_json(PROFILE_SUMMARY)
    scorer = _read_json(SCORER_REPORT)
    phase12 = _read_json(PHASE12_REPORT)
    current = _read_json(CURRENT_SHADOW)

    point_rows = int(point_summary.get("context_ready_player_point") or 0)
    join_counts = scorer.get("join_counts") or {}
    joined_rows = int(join_counts.get("joined_rows") or 0)
    scorer_join_coverage = float(scorer.get("join_coverage") or 0.0)

    source_counts = profile_summary.get("source_counts") or {}
    split_seen = int(source_counts.get("service_split_source_matches_seen") or 0)
    split_joined = int(source_counts.get("service_split_matches_joined") or 0)
    split_hit_rate = (
        split_joined / split_seen if split_seen > 0 else None
    )

    perf = profile_summary.get("phase13_performance_observation") or {}

    pair = _actual_profile_pair()
    if pair is None:
        matchup = {
            "source": "CANONICAL_PHASE3_BUILD_MATCHUP_PACKET",
            "real_profile_snapshot_pair": False,
            "status": "NO_RECIPROCAL_REAL_PROFILE_PAIR",
            "iterations": 0,
            "absolute_latency_gate_enabled": False,
        }
    else:
        target, p1_profile, p2_profile = pair
        matchup = benchmark_matchup(target, p1_profile, p2_profile)

    sim_input = _simulation_input(current)
    sim_rows: list[dict[str, Any]] = []
    first_result: dict[str, Any] | None = None
    for size in SIMULATION_SIZES:
        result, measurement = benchmark_simulation(
            sim_input,
            simulations=size,
            seed=BENCHMARK_SEED,
        )
        sim_rows.append(measurement)
        if size == SIMULATION_SIZES[0]:
            first_result = result

    replay, replay_measurement = benchmark_simulation(
        sim_input,
        simulations=SIMULATION_SIZES[0],
        seed=BENCHMARK_SEED,
    )
    deterministic = first_result is not None and replay == first_result

    phase_wall = time.perf_counter() - phase_started

    report: dict[str, Any] = {
        "version": VERSION,
        "mode": MODE,
        "status": "PHASE13_MEASUREMENTS_COMPLETE_NO_PERFORMANCE_THRESHOLDS",
        "phase": 13,
        "prerequisite": {
            "phase12_complete": phase12.get("phase12_complete") is True,
            "phase13_ready": phase12.get("phase13_ready") is True,
        },
        "cache_and_join": {
            "point_dataset_matches": int(point_summary.get("matches") or 0),
            "strict_context_ready_point_rows": point_rows,
            "scorer_joined_rows": joined_rows,
            "scorer_join_coverage": scorer_join_coverage,
            "context_match_rate": point_summary.get("context_match_rate"),
            "service_split_source_matches_seen": split_seen,
            "service_split_matches_exactly_joined": split_joined,
            "service_split_exact_join_hit_rate": split_hit_rate,
            "service_split_join_key": "match_id + scheduled_time + p1_id + p2_id + surface",
            "nearest_or_fuzzy_join_used": False,
        },
        "profile_build": {
            "source": "CANONICAL_PLAYER_DNA_SHADOW_PROFILES_BUILD",
            "strict_history_matches": int(profile_summary.get("strict_matches") or 0),
            "profile_snapshots": int(profile_summary.get("player_match_snapshots") or 0),
            "players": int(profile_summary.get("players") or 0),
            "canonical_build_seconds": perf.get("profile_build_seconds"),
            "canonical_write_seconds": perf.get("profile_write_seconds"),
            "canonical_total_seconds": perf.get("total_seconds"),
            "process_peak_rss_bytes_after_build": perf.get(
                "process_peak_rss_bytes_after_build"
            ),
            "process_peak_rss_bytes_after_write": perf.get(
                "process_peak_rss_bytes_after_write"
            ),
            "input_scan_included_in_build_time": True,
            "second_profile_builder_created": False,
        },
        "matchup": matchup,
        "simulation": {
            "source": "CANONICAL_PLAYER_DNA_MONTE_CARLO_MATCH_DISTRIBUTION",
            "input": sim_input,
            "benchmarks": sim_rows,
            "deterministic_seed_replay": deterministic,
            "deterministic_replay_seconds": replay_measurement["seconds"],
            "deterministic_replay_fingerprint_sha256": replay_measurement[
                "result_fingerprint_sha256"
            ],
            "same_seed_same_output_required": True,
            "monte_carlo_replacement_of_exact_dp": False,
        },
        "ci_runtime_cost": {
            "phase13_step_wall_seconds": phase_wall,
            "process_peak_rss_bytes_after_phase13": _process_peak_rss_bytes(),
            "runner_os": os.environ.get("RUNNER_OS") or platform.system(),
            "runner_arch": os.environ.get("RUNNER_ARCH") or platform.machine(),
            "python": platform.python_version(),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "github_sha": os.environ.get("GITHUB_SHA"),
            "currency_cost": None,
            "currency_cost_status": "NOT_ESTIMATED_WITHOUT_RUNNER_PRICE_CONTRACT",
        },
        "performance_thresholds_enforced": False,
        "benchmark_results_observational_only": True,
        "no_arbitrary_latency_or_memory_limit": True,
        "production_influence": False,
        "runtime_prediction_change": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "contract": {
            "canonical_profile_builder_measured_in_place": True,
            "canonical_matchup_builder_reused": True,
            "canonical_monte_carlo_reused": True,
            "current_cache_and_join_counters_reused": True,
            "absolute_performance_thresholds_require_future_data_driven_gate": True,
            "determinism_is_correctness_not_speed_threshold": True,
            "phase13_completion_is_measurement_completeness_not_promotion": True,
        },
    }
    report["phase13_complete"] = evaluate_phase13_completion(report)
    report["phase14_ready"] = report["phase13_complete"]
    if not report["phase13_complete"]:
        report["status"] = "PHASE13_MEASUREMENTS_INCOMPLETE"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "strict_rows": point_rows,
        "joined_rows": joined_rows,
        "join_coverage": scorer_join_coverage,
        "profiles": report["profile_build"]["profile_snapshots"],
        "profile_build_seconds": report["profile_build"]["canonical_build_seconds"],
        "matchup_us": matchup.get("mean_microseconds_per_matchup"),
        "simulation_seconds": {
            str(row["simulations"]): row["seconds"] for row in sim_rows
        },
        "deterministic": deterministic,
        "phase13_complete": report["phase13_complete"],
        "phase14_ready": report["phase14_ready"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
