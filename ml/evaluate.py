"""Model evaluation: MAE, RMSE, R2 on the held-out test set.

As a script it re-computes the metrics from the saved model (no numbers are hard-coded):
    python -m ml.evaluate
"""
import json
import math
import sys

import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.preprocessing import load_dataset, load_params, split_dataset


def evaluate(model, X_test, y_test) -> dict:
    pred = model.predict(X_test)
    return {
        "mae": float(mean_absolute_error(y_test, pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_test, pred))),
        "r2": float(r2_score(y_test, pred)),
    }


def passes_quality_gate(metrics: dict, gate: dict) -> tuple:
    """Return (passed, list_of_reasons_for_failure)."""
    reasons = []
    if metrics["r2"] < gate["min_r2"]:
        reasons.append(f"R2 {metrics['r2']:.3f} < required {gate['min_r2']}")
    if metrics["rmse"] > gate["max_rmse"]:
        reasons.append(f"RMSE {metrics['rmse']:.3f} > allowed {gate['max_rmse']}")
    return (not reasons), reasons


def main() -> int:
    params = load_params()
    df = load_dataset(params["data"]["raw_path"], params["data"]["drop_duplicates"])
    _, X_test, _, y_test = split_dataset(df, params["data"]["test_size"], params["data"]["random_state"])
    model = joblib.load("models/model.joblib")
    print(json.dumps(evaluate(model, X_test, y_test), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
