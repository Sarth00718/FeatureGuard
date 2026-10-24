import pytest

from featureguard.drift_monitor import detect_drift
from featureguard.validation import FEATURES
from tests.conftest import make_synthetic

SHIFT = {"alcohol": 3.0, "total_sulfur_dioxide": 60.0, "volatile_acidity": 0.4,
         "ph": 0.4, "sulphates": 0.4, "chlorides": 0.1}


def test_no_drift_for_same_distribution():
    ref, cur = make_synthetic(500, seed=1), make_synthetic(60, seed=2)
    r = detect_drift(ref, cur, FEATURES, engine="ks")
    assert r.drift_detected is False


def test_drift_detected_for_shifted_batch():
    ref, cur = make_synthetic(500, seed=1), make_synthetic(60, seed=3, shift=SHIFT)
    r = detect_drift(ref, cur, FEATURES, engine="ks")
    assert r.drift_detected is True
    assert "alcohol" in r.drifted_features


def test_single_request_is_not_enough():
    ref = make_synthetic(500, seed=1)
    with pytest.raises(ValueError):
        detect_drift(ref, make_synthetic(1, seed=4), FEATURES, engine="ks")


def test_evidently_engine_detects_drift(tmp_path):
    pytest.importorskip("evidently")
    ref, cur = make_synthetic(500, seed=1), make_synthetic(60, seed=3, shift=SHIFT)
    r = detect_drift(ref, cur, FEATURES, engine="evidently", html_path=str(tmp_path / "r.html"))
    assert r.engine == "evidently" and r.drift_detected is True
    assert (tmp_path / "r.html").exists()
