"""FeatureGuard - hard feature validation (request-level rules).

This module answers ONE question for a SINGLE request:
    "Is this input structurally and physically sensible?"

It does NOT detect statistical drift. Drift needs many rows, see drift_monitor.py.
It is also the single source of truth for the feature list and allowed ranges, so
the training pipeline, the API and the tests all agree on the same schema.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

# Ordered: this order is the column order the model is trained with.
# (min, max) are *hard* limits - wider than the real dataset range on purpose.
FEATURE_RANGES: Dict[str, tuple] = {
    "fixed_acidity": (3.0, 20.0),
    "volatile_acidity": (0.05, 2.5),
    "citric_acid": (0.0, 1.5),
    "residual_sugar": (0.5, 30.0),
    "chlorides": (0.005, 1.0),
    "free_sulfur_dioxide": (0.0, 150.0),
    "total_sulfur_dioxide": (0.0, 400.0),
    "density": (0.985, 1.010),
    "ph": (2.5, 4.5),
    "sulphates": (0.1, 3.0),
    "alcohol": (5.0, 20.0),
}
FEATURES: List[str] = list(FEATURE_RANGES.keys())

# Raw CSV header -> internal snake_case name
CSV_RENAME = {
    "fixed acidity": "fixed_acidity",
    "volatile acidity": "volatile_acidity",
    "citric acid": "citric_acid",
    "residual sugar": "residual_sugar",
    "chlorides": "chlorides",
    "free sulfur dioxide": "free_sulfur_dioxide",
    "total sulfur dioxide": "total_sulfur_dioxide",
    "density": "density",
    "pH": "ph",
    "sulphates": "sulphates",
    "alcohol": "alcohol",
    "quality": "quality",
}
TARGET = "quality"


def validate_features(
    features: Mapping[str, Any],
    expected_columns: Optional[Sequence[str]] = None,
) -> List[str]:
    """Return a list of human-readable problems (empty list == valid)."""
    expected = list(expected_columns) if expected_columns else FEATURES
    errors: List[str] = []

    # 1. Required fields / unexpected fields
    missing = [c for c in expected if c not in features]
    if missing:
        errors.append(f"Missing required field(s): {', '.join(missing)}")
    extra = [c for c in features if c not in expected]
    if extra:
        errors.append(f"Unexpected field(s): {', '.join(extra)}")

    # 2. Types and 3. ranges
    for name in expected:
        if name not in features:
            continue
        value = features[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{name}: must be a number, got {type(value).__name__}")
            continue
        if math.isnan(value) or math.isinf(value):
            errors.append(f"{name}: must be a finite number")
            continue
        low, high = FEATURE_RANGES.get(name, (-math.inf, math.inf))
        if not (low <= value <= high):
            errors.append(f"{name}: {value} is outside the allowed range [{low}, {high}]")

    # 4. Preprocessing consistency: the model must be fed the same columns it was trained on
    if expected != FEATURES:
        errors.append(
            "Model feature list does not match the FeatureGuard schema "
            "(training and serving are out of sync) - retrain the model."
        )
    return errors
