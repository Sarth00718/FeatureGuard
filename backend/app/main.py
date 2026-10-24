"""FastAPI service: validation -> prediction -> PostgreSQL -> metrics."""
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

import pandas as pd
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.app import config, metrics
from backend.app.db import DriftAlert, Prediction, SessionLocal, get_db, init_db
from featureguard.drift_monitor import detect_drift
from featureguard.validation import validate_features
from ml.predict import ModelService

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("featureguard.api")

model_service = ModelService(config.MODEL_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        model_service.load()
        metrics.MODEL_LOADED.set(1)
        logger.info("Model version %s loaded", model_service.version)
    except Exception as exc:  # noqa: BLE001
        metrics.MODEL_LOADED.set(0)
        logger.error("Could not load model from %s: %s (run: python -m ml.train)", config.MODEL_DIR, exc)
    metrics.APP_UP.set(1)
    yield
    metrics.APP_UP.set(0)


app = FastAPI(title="FeatureGuard API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def record_http_metrics(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        if path != "/metrics":
            metrics.REQUEST_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
            metrics.HTTP_REQUESTS.labels(request.method, path, str(status)).inc()


# ---------------------------------------------------------------- health / metrics
@app.get("/health")
def health():
    """Liveness + component status (always 200 while the process is alive)."""
    db_ok = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if (db_ok and model_service.loaded) else "degraded",
        "api": "ok",
        "database": "ok" if db_ok else "down",
        "model": "loaded" if model_service.loaded else "not_loaded",
        "model_version": model_service.version if model_service.loaded else None,
    }


@app.get("/ready")
def ready(response: Response):
    """Readiness: 503 until the database and the model are available."""
    info = health()
    if info["status"] != "ok":
        response.status_code = 503
    return info


@app.get("/metrics")
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------- prediction
EXAMPLE = {
    "fixed_acidity": 7.4, "volatile_acidity": 0.7, "citric_acid": 0.0, "residual_sugar": 1.9,
    "chlorides": 0.076, "free_sulfur_dioxide": 11.0, "total_sulfur_dioxide": 34.0,
    "density": 0.9978, "ph": 3.51, "sulphates": 0.56, "alcohol": 9.4,
}


@app.post("/predict")
def predict(payload: Dict[str, Any] = Body(..., examples=[EXAMPLE]), db: Session = Depends(get_db)):
    metrics.PREDICTION_REQUESTS.inc()
    version = model_service.version if model_service.loaded else "none"

    # 1) Hard validation: a single bad request is rejected with a clear explanation
    errors = validate_features(payload, model_service.features or None)
    if errors:
        metrics.VALIDATION_REJECTIONS.inc()
        db.add(Prediction(features=payload, predicted_quality=None, model_version=version,
                          validation_status="rejected", validation_errors=errors))
        db.commit()
        raise HTTPException(status_code=422, detail={"message": "Input rejected by feature validation", "errors": errors})

    # 2) Prediction
    try:
        if not model_service.loaded:
            raise RuntimeError("Model is not loaded")
        quality = model_service.predict(payload)
        row = Prediction(features=payload, predicted_quality=quality, model_version=version,
                         validation_status="accepted")
        db.add(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        metrics.PREDICTION_FAILURES.inc()
        logger.exception("Prediction failed")
        status = 503 if not model_service.loaded else 500
        raise HTTPException(status_code=status, detail=f"Prediction failed: {exc}")

    # 3) Batch-level drift check (never blocks the request, never fails it)
    try:
        run_drift_check_if_batch_ready(db)
    except Exception:  # noqa: BLE001
        logger.exception("Drift check failed (prediction was still served)")

    return {"id": row.id, "predicted_quality": round(quality, 3), "rounded_quality": round(quality),
            "model_version": version, "validation_status": "accepted"}


def _serialize_prediction(p: Prediction) -> dict:
    return {"id": p.id, "features": p.features, "predicted_quality": p.predicted_quality,
            "model_version": p.model_version, "created_at": p.created_at.isoformat(),
            "validation_status": p.validation_status, "validation_errors": p.validation_errors}


@app.get("/predictions")
def list_predictions(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    rows = db.scalars(select(Prediction).order_by(Prediction.id.desc()).limit(limit)).all()
    return [_serialize_prediction(r) for r in rows]


# ---------------------------------------------------------------- model quality
@app.get("/model/metrics")
def model_metrics():
    """OFFLINE evaluation of the deployed model on the held-out test split."""
    if not model_service.loaded:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    md = model_service.metadata
    return {"model_version": md.get("model_version"), "metrics": md.get("metrics"),
            "evaluated_on": md.get("evaluated_on"), "trained_at": md.get("trained_at"),
            "quality_gate": md.get("quality_gate"), "mlflow_run_id": md.get("mlflow_run_id")}


# ---------------------------------------------------------------- drift
def run_drift_check_if_batch_ready(db: Session, force: bool = False):
    """Check drift on the accepted requests received since the last check."""
    last_checked = db.scalar(select(func.max(DriftAlert.last_prediction_id))) or 0
    rows = db.scalars(
        select(Prediction).where(Prediction.validation_status == "accepted", Prediction.id > last_checked)
        .order_by(Prediction.id)
    ).all()
    if model_service.reference is None:
        return None
    if len(rows) < (1 if force else config.DRIFT_BATCH_SIZE):
        return None
    current = pd.DataFrame([r.features for r in rows])[model_service.features]
    result = detect_drift(
        model_service.reference, current, model_service.features,
        engine=config.DRIFT_ENGINE, share_threshold=config.DRIFT_SHARE_THRESHOLD,
        min_batch_size=1 if force else config.DRIFT_BATCH_SIZE,
        html_path=os.path.join(config.DRIFT_REPORT_DIR, "latest.html"),
    )
    alert = DriftAlert(batch_size=result.batch_size, drift_detected=result.drift_detected,
                       share_drifted=result.share_drifted, drifted_features=result.drifted_features,
                       engine=result.engine, last_prediction_id=rows[-1].id)
    db.add(alert)
    db.commit()
    metrics.DRIFT_CHECKS.inc()
    if result.drift_detected:
        metrics.DRIFT_ALERTS.inc()
        logger.warning("DRIFT ALERT: %s of features drifted (%s)", result.share_drifted, result.drifted_features)
    return alert


def _serialize_alert(a: DriftAlert) -> dict:
    return {"id": a.id, "created_at": a.created_at.isoformat(), "batch_size": a.batch_size,
            "drift_detected": a.drift_detected, "share_drifted": a.share_drifted,
            "drifted_features": a.drifted_features, "engine": a.engine}


@app.get("/drift/alerts")
def drift_alerts(only_drift: bool = False, limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    q = select(DriftAlert).order_by(DriftAlert.id.desc()).limit(limit)
    if only_drift:
        q = q.where(DriftAlert.drift_detected.is_(True))
    return [_serialize_alert(a) for a in db.scalars(q).all()]


@app.post("/drift/check")
def drift_check_now(db: Session = Depends(get_db)):
    """Manual trigger (demo): check all accepted requests not yet checked, even if the batch is small."""
    try:
        alert = run_drift_check_if_batch_ready(db, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if alert is None:
        raise HTTPException(status_code=400, detail="No new accepted requests to check (or no reference data).")
    return _serialize_alert(alert)


@app.get("/summary")
def summary(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Prediction.id))) or 0
    accepted = db.scalar(select(func.count(Prediction.id)).where(Prediction.validation_status == "accepted")) or 0
    drift = db.scalar(select(func.count(DriftAlert.id)).where(DriftAlert.drift_detected.is_(True))) or 0
    return {"total_requests": total, "accepted": accepted, "rejected": total - accepted,
            "drift_alerts": drift, "drift_batch_size": config.DRIFT_BATCH_SIZE}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
