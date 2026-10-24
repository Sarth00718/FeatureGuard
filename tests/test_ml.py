import pytest

from ml.evaluate import evaluate, passes_quality_gate
from ml.predict import ModelService
from ml.preprocessing import split_dataset
from tests.conftest import TYPICAL


def test_split_is_reproducible(synthetic_df):
    a = split_dataset(synthetic_df, 0.2, 42)
    b = split_dataset(synthetic_df, 0.2, 42)
    assert a[0].index.equals(b[0].index) and a[1].index.equals(b[1].index)


def test_metrics_have_expected_keys(trained_model_dir, synthetic_df):
    svc = ModelService(trained_model_dir)
    svc.load()
    _, X_test, _, y_test = split_dataset(synthetic_df, 0.2, 42)
    m = evaluate(svc.model, X_test, y_test)
    assert set(m) == {"mae", "rmse", "r2"}


def test_quality_gate_logic():
    gate = {"min_r2": 0.4, "max_rmse": 0.7}
    assert passes_quality_gate({"r2": 0.5, "rmse": 0.6, "mae": 0.4}, gate)[0] is True
    ok, reasons = passes_quality_gate({"r2": 0.1, "rmse": 0.9, "mae": 0.7}, gate)
    assert ok is False and len(reasons) == 2


def test_model_service_predicts(trained_model_dir):
    svc = ModelService(trained_model_dir)
    svc.load()
    assert 0 <= svc.predict(TYPICAL) <= 10


def test_unloaded_model_raises():
    with pytest.raises(RuntimeError):
        ModelService("does-not-exist").predict(TYPICAL)
