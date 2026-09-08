from backend import player_dna_phase13_performance as phase13


def _complete_report():
    return {
        "prerequisite": {
            "phase12_complete": True,
            "phase13_ready": True,
        },
        "cache_and_join": {
            "strict_context_ready_point_rows": 100,
            "scorer_joined_rows": 100,
            "scorer_join_coverage": 1.0,
        },
        "profile_build": {
            "profile_snapshots": 20,
            "canonical_build_seconds": 1_000_000.0,
            "process_peak_rss_bytes_after_build": 1,
        },
        "matchup": {
            "real_profile_snapshot_pair": True,
            "iterations": 1,
            "total_seconds": 1_000_000.0,
        },
        "simulation": {
            "benchmarks": [
                {
                    "simulations": 10_000,
                    "seconds": 1_000_000.0,
                    "process_peak_rss_bytes_after_stage": 1,
                },
                {
                    "simulations": 50_000,
                    "seconds": 1_000_000.0,
                    "process_peak_rss_bytes_after_stage": 1,
                },
                {
                    "simulations": 100_000,
                    "seconds": 1_000_000.0,
                    "process_peak_rss_bytes_after_stage": 1,
                },
            ],
            "deterministic_seed_replay": True,
        },
        "ci_runtime_cost": {
            "phase13_step_wall_seconds": 1_000_000.0,
            "process_peak_rss_bytes_after_phase13": 1,
        },
        "performance_thresholds_enforced": False,
        "benchmark_results_observational_only": True,
        "production_influence": False,
        "runtime_prediction_change": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
    }


def test_phase13_completion_requires_measurements_but_never_a_speed_limit():
    report = _complete_report()

    # Deliberately absurdly slow observations still close the measurement gate:
    # Phase 13 measures the current system first and does not invent a latency
    # threshold just to make CI green or red.
    assert phase13.evaluate_phase13_completion(report) is True


def test_phase13_completion_preserves_full_real_join_coverage_gate():
    report = _complete_report()
    report["cache_and_join"]["scorer_joined_rows"] = 99
    report["cache_and_join"]["scorer_join_coverage"] = 0.99

    assert phase13.evaluate_phase13_completion(report) is False


def test_phase13_canonical_monte_carlo_replays_identically_for_fixed_seed():
    simulation_input = {
        "p1_serve_point_win": 0.63,
        "p2_serve_point_win": 0.59,
        "best_of": 3,
    }
    first, first_measurement = phase13.benchmark_simulation(
        simulation_input,
        simulations=64,
        seed=1313,
    )
    second, second_measurement = phase13.benchmark_simulation(
        simulation_input,
        simulations=64,
        seed=1313,
    )

    assert first == second
    assert (
        first_measurement["result_fingerprint_sha256"]
        == second_measurement["result_fingerprint_sha256"]
    )
    assert first_measurement["absolute_latency_gate_enabled"] is False
