from __future__ import annotations

"""Leakage-safe feature snapshots for the isolated NEURO SHADOW layer.

Only values already present before the match are copied. Final results, settled
labels and bookmaker prices are intentionally not accepted by this module.
"""

import math
import re
import unicodedata
from typing import Any

VERSION = "neuro-shadow-features-v9.3.5"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

MODEL_FEATURES = ("base", "current", "catboost", "tabpfn", "adaptive")


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(re.sub(r"[^a-z0-9:.+\-]+", " ", text).split())


def _name_key(value: Any) -> str:
    return " ".join(sorted(re.sub(r"[^a-z0-9]+", " ", _norm(value)).split()))


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _probability(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        return number
    if 0.0 <= number <= 100.0:
        return number / 100.0
    return None


def selection_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    line = _number(row.get("line"))
    return (
        _norm(row.get("market")).replace(" ", "_"),
        _norm(row.get("pick")),
        round(line, 6) if line is not None else None,
        int(_number(row.get("checkpoint")) or 0),
        _name_key(row.get("player")),
    )


def model_signal_index(market_context: dict[str, Any]) -> dict[tuple[Any, ...], dict[str, Any]]:
    """Index only pre-match existing model rows by exact canonical selection."""
    if not isinstance(market_context, dict):
        return {}
    out: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in market_context.get("model_signals") or []:
        if not isinstance(row, dict):
            continue
        out[selection_signature(row)] = row
    return out


def extract_feature_snapshot(
    match: dict[str, Any],
    selection: dict[str, Any],
    *,
    state_probability: float,
    model_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze numeric model evidence without reading any final/settled outcome."""
    signal = model_signal if isinstance(model_signal, dict) else {}
    scores = signal.get("model_scores") if isinstance(signal.get("model_scores"), dict) else {}
    adaptive = signal.get("adaptive_prod_v79") if isinstance(signal.get("adaptive_prod_v79"), dict) else {}

    values = {
        "state": _probability(state_probability),
        "base": _probability(signal.get("score")),
        "current": _probability(scores.get("current", signal.get("current"))),
        "catboost": _probability(scores.get("catboost", signal.get("catboost"))),
        "tabpfn": _probability(scores.get("tabpfn", signal.get("tabpfn"))),
        "adaptive": _probability(adaptive.get("final_score")),
    }
    surface = _norm(match.get("surface"))
    best_of = int(_number(match.get("best_of")) or 3)
    numeric = {
        "state_probability": values["state"],
        "base_probability": values["base"],
        "current_probability": values["current"],
        "catboost_probability": values["catboost"],
        "tabpfn_probability": values["tabpfn"],
        "adaptive_probability": values["adaptive"],
        "best_of_5": 1.0 if best_of >= 5 else 0.0,
        "surface_hard": 1.0 if "hard" in surface else 0.0,
        "surface_clay": 1.0 if "clay" in surface else 0.0,
        "surface_grass": 1.0 if "grass" in surface else 0.0,
    }
    evidence_count = sum(values[name] is not None for name in MODEL_FEATURES)
    return {
        "version": VERSION,
        "market": selection.get("market"),
        "numeric": numeric,
        "existing_model_evidence_count": evidence_count,
        "has_existing_model_signal": bool(signal),
        "source_model_signal_key": selection_signature(selection) if signal else None,
        "contains_final_result": False,
        "contains_bookmaker_price": False,
        "production_influence": False,
        "playable_influence": False,
    }
