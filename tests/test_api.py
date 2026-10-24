from tests.conftest import TYPICAL, make_synthetic


def test_health_and_ready(client):
    h = client.get("/health").json()
    assert h["api"] == "ok" and h["database"] == "ok" and h["model"] == "loaded"
    assert client.get("/ready").status_code == 200


def test_predict_ok_and_saved(client):
    r = client.post("/predict", json=TYPICAL)
    assert r.status_code == 200
    body = r.json()
    assert body["validation_status"] == "accepted" and body["model_version"] == "test-1"
    rows = client.get("/predictions").json()
    assert any(p["id"] == body["id"] for p in rows)


def test_invalid_input_rejected_with_explanation(client):
    r = client.post("/predict", json={**TYPICAL, "alcohol": 99})
    assert r.status_code == 422
    assert "alcohol" in r.json()["detail"]["errors"][0]
    rejected = [p for p in client.get("/predictions").json() if p["validation_status"] == "rejected"]
    assert rejected and rejected[0]["predicted_quality"] is None


def test_missing_field_rejected(client):
    bad = dict(TYPICAL)
    bad.pop("ph")
    assert client.post("/predict", json=bad).status_code == 422


def test_metrics_endpoint_has_app_metrics(client):
    client.post("/predict", json=TYPICAL)
    text = client.get("/metrics").text
    for name in ("featureguard_prediction_requests_total", "featureguard_validation_rejections_total",
                 "featureguard_request_latency_seconds", "featureguard_drift_alerts_total"):
        assert name in text


def test_model_metrics_endpoint(client):
    body = client.get("/model/metrics").json()
    assert set(body["metrics"]) == {"mae", "rmse", "r2"}


def test_drift_alert_after_shifted_batch(client):
    shift = {"alcohol": 3.0, "total_sulfur_dioxide": 60.0, "volatile_acidity": 0.4,
             "ph": 0.4, "sulphates": 0.4, "chlorides": 0.1}
    for _, row in make_synthetic(35, seed=9, shift=shift).drop(columns="quality").iterrows():
        assert client.post("/predict", json=row.to_dict()).status_code == 200
    alerts = client.get("/drift/alerts", params={"only_drift": True}).json()
    assert alerts and alerts[0]["drift_detected"] is True
    assert client.get("/summary").json()["drift_alerts"] >= 1
