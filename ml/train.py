"""Training pipeline: validate -> split -> train -> evaluate -> quality gate -> save/register.

    python -m ml.train

Exit code 0 = model approved and saved. Exit code 1 = quality gate failed (nothing is
saved over the previous approved model, so CI/CD will not deploy it).

MLflow: set MLFLOW_TRACKING_URI (e.g. http://localhost:5000). Default is a local
SQLite file (mlflow.db) so the pipeline works even without the MLflow server.
"""
import json
import os
import sys
from datetime import datetime, timezone

import joblib
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

from featureguard.validation import FEATURES
from ml.evaluate import evaluate, passes_quality_gate
from ml.preprocessing import build_pipeline, load_dataset, load_params, split_dataset
from ml.validate_data import validate_dataset

MODEL_DIR = os.getenv("MODEL_DIR", "models")


def main() -> int:
    params = load_params()
    data_cfg, model_cfg = params["data"], params["model"]

    problems = validate_dataset(data_cfg["raw_path"])
    if problems:
        print("Data validation failed:", *problems, sep="\n - ")
        return 1

    df = load_dataset(data_cfg["raw_path"], data_cfg["drop_duplicates"])
    X_train, X_test, y_train, y_test = split_dataset(df, data_cfg["test_size"], data_cfg["random_state"])
    print(f"Rows: train={len(X_train)} test={len(X_test)}")

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    mlflow.set_experiment(params["mlflow"]["experiment_name"])

    with mlflow.start_run() as run:
        pipeline = build_pipeline(model_cfg)
        pipeline.fit(X_train, y_train)
        metrics = evaluate(pipeline, X_test, y_test)
        approved, reasons = passes_quality_gate(metrics, params["quality_gate"])

        mlflow.log_params({**{f"data_{k}": v for k, v in data_cfg.items()},
                           **{f"model_{k}": v for k, v in model_cfg.items()}})
        mlflow.log_metrics(metrics)
        mlflow.set_tag("quality_gate", "passed" if approved else "failed")
        print("Evaluation (test split):", json.dumps(metrics, indent=2))

        if not approved:
            print("QUALITY GATE FAILED - model NOT saved or registered:", *reasons, sep="\n - ")
            return 1

        model_version = "unregistered"
        mlflow.sklearn.log_model(pipeline, artifact_path="model")
        result = mlflow.register_model(f"runs:/{run.info.run_id}/model",
                                       params["mlflow"]["registered_model_name"])
        model_version = str(result.version)
        MlflowClient().set_registered_model_alias(
            params["mlflow"]["registered_model_name"], "approved", result.version)

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    joblib.dump(pipeline, os.path.join(MODEL_DIR, "model.joblib"))
    # Reference data for drift monitoring = the training split
    X_train.to_csv(os.path.join(MODEL_DIR, "reference.csv"), index=False)
    metadata = {
        "model_version": model_version,
        "mlflow_run_id": run.info.run_id,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": FEATURES,
        "metrics": metrics,
        "evaluated_on": f"held-out test split ({len(X_test)} rows)",
        "params": model_cfg,
        "quality_gate": params["quality_gate"],
    }
    with open(os.path.join(MODEL_DIR, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    with open("reports/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Model approved and saved. MLflow registered version: {model_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
