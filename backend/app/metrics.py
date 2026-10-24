"""Prometheus APPLICATION metrics (traffic, errors, latency, alerts).

These are not model-quality metrics. Model quality (MAE/RMSE/R2) comes from the
offline evaluation stored in models/metadata.json and is shown separately.
"""
from prometheus_client import Counter, Gauge, Histogram

PREDICTION_REQUESTS = Counter("featureguard_prediction_requests_total", "Total /predict requests")
PREDICTION_FAILURES = Counter("featureguard_prediction_failures_total", "Prediction requests that failed with a server error")
VALIDATION_REJECTIONS = Counter("featureguard_validation_rejections_total", "Requests rejected by feature validation")
DRIFT_CHECKS = Counter("featureguard_drift_checks_total", "Drift checks executed on batches")
DRIFT_ALERTS = Counter("featureguard_drift_alerts_total", "Drift checks that detected drift")
APP_UP = Gauge("featureguard_app_up", "1 if the API process is running")
MODEL_LOADED = Gauge("featureguard_model_loaded", "1 if a model is loaded")
REQUEST_LATENCY = Histogram(
    "featureguard_request_latency_seconds", "HTTP request latency",
    ["method", "path"], buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
HTTP_REQUESTS = Counter("featureguard_http_requests_total", "HTTP requests", ["method", "path", "status"])
