"""Shared fixtures. Tests train a tiny model on SYNTHETIC data stored in a temp folder.
These numbers are only for testing the code - they are never real wine metrics."""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

# Must be set BEFORE the backend is imported (engine is created at import time)
_tmp = tempfile.mkdtemp(prefix="fg_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["MODEL_DIR"] = os.path.join(_tmp, "models")
os.environ["DRIFT_ENGINE"] = "ks"
os.environ["DRIFT_BATCH_SIZE"] = "30"
os.environ["DRIFT_REPORT_DIR"] = os.path.join(_tmp, "drift")

from featureguard.validation import FEATURES, FEATURE_RANGES  # noqa: E402

TYPICAL = {  # roughly the centre of the real dataset
    "fixed_acidity": 8.3, "volatile_acidity": 0.53, "citric_acid": 0.27, "residual_sugar": 2.5,
    "chlorides": 0.087, "free_sulfur_dioxide": 15.0, "total_sulfur_dioxide": 46.0,
    "density": 0.9967, "ph": 3.31, "sulphates": 0.66, "alcohol": 10.4,
}
SPREAD = {k: abs(v) * 0.15 for k, v in TYPICAL.items()}


def make_synthetic(n=400, seed=0, shift=None):
    rng = np.random.default_rng(seed)
    data = {}
    for c in FEATURES:
        mean = TYPICAL[c] + (shift or {}).get(c, 0.0)
        low, high = FEATURE_RANGES[c]
        data[c] = np.clip(rng.normal(mean, SPREAD[c], n), low + 1e-6, high - 1e-6)
    df = pd.DataFrame(data)
    df["quality"] = (5 + 0.4 * (df["alcohol"] - 10.4) - 1.0 * (df["volatile_acidity"] - 0.53)
                     + rng.normal(0, 0.3, n)).round().clip(3, 8)
    return df


@pytest.fixture(scope="session")
def synthetic_df():
    return make_synthetic()


@pytest.fixture(scope="session")
def trained_model_dir(synthetic_df):
    import json
    import joblib
    from ml.evaluate import evaluate
    from ml.preprocessing import build_pipeline, split_dataset

    X_train, X_test, y_train, y_test = split_dataset(synthetic_df, 0.2, 42)
    pipe = build_pipeline({"n_estimators": 20, "max_depth": 6, "random_state": 42})
    pipe.fit(X_train, y_train)
    mdir = os.environ["MODEL_DIR"]
    os.makedirs(mdir, exist_ok=True)
    joblib.dump(pipe, os.path.join(mdir, "model.joblib"))
    X_train.to_csv(os.path.join(mdir, "reference.csv"), index=False)
    with open(os.path.join(mdir, "metadata.json"), "w") as f:
        json.dump({"model_version": "test-1", "features": FEATURES, "metrics": evaluate(pipe, X_test, y_test),
                   "evaluated_on": "synthetic test data"}, f)
    return mdir


@pytest.fixture(scope="session")
def client(trained_model_dir):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as c:
        yield c
