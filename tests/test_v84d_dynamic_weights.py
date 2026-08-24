from backend.dynamic_weights_v84d import (
    TABPFN_CAP,
    resolve_weights,
    weighted_probability,
)


def telemetry(n=60):
    return {
        "version": "v8.4C",
        "segments_30d": {
            "tour": {
                "ATP": {
                    "current": {"selected_n": n, "brier": 0.12},
                    "catboost": {"selected_n": n, "brier": 0.22},
                    "tabpfn": {"selected_n": max(18, min(n, 30)), "brier": 0.10},
                }
            },
            "surface": {
                "HARD": {
                    "current": {"selected_n": n, "brier": 0.14},
                    "catboost": {"selected_n": n, "brier": 0.20},
                    "tabpfn": {"selected_n": max(18, min(n, 30)), "brier": 0.11},
                }
            },
            "market": {
                "set1_total": {
                    "current": {"selected_n": n, "brier": 0.13},
                    "catboost": {"selected_n": n, "brier": 0.21},
                    "tabpfn": {"selected_n": max(18, min(n, 30)), "brier": 0.10},
                }
            },
        },
    }


ROW = {"tour": "ATP", "surface": "HARD", "market": "set1_total"}


def test_dynamic_weights_shift_toward_better_segment_model_but_stay_bounded():
    base = {"current": 0.35, "catboost": 0.55, "tabpfn": 0.10}
    out, policy = resolve_weights(base, ROW, telemetry())
    assert policy["active"] is True
    assert out["current"] > base["current"]
    assert out["catboost"] < base["catboost"]
    assert out["tabpfn"] <= TABPFN_CAP
    assert abs(sum(out.values()) - 1.0) < 1e-9


def test_dynamic_weights_never_reenable_globally_disabled_tabpfn():
    base = {"current": 0.40, "catboost": 0.60, "tabpfn": 0.0}
    out, _ = resolve_weights(base, ROW, telemetry())
    assert "tabpfn" not in out


def test_small_segment_sample_is_safe_fallback():
    base = {"current": 0.40, "catboost": 0.60}
    out, policy = resolve_weights(base, ROW, telemetry(n=5))
    assert out == base
    assert policy["active"] is False


def test_missing_telemetry_is_safe_fallback():
    base = {"current": 0.40, "catboost": 0.60}
    out, policy = resolve_weights(base, ROW, {})
    assert out == base
    assert policy["status"] == "SAFE_FALLBACK"


def test_weighted_probability_renormalizes_available_models():
    p = weighted_probability(
        {"current": 0.70, "catboost": 0.80, "tabpfn": None},
        {"current": 0.25, "catboost": 0.50, "tabpfn": 0.25},
    )
    assert abs(p - ((0.70 * 0.25 + 0.80 * 0.50) / 0.75)) < 1e-12
