"""SQLAlchemy engine, tables and a tiny init routine."""
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.app import config

logger = logging.getLogger("featureguard.db")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    features: Mapped[dict] = mapped_column(JSON)
    predicted_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    validation_status: Mapped[str] = mapped_column(String(16))  # accepted | rejected
    validation_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)


class DriftAlert(Base):
    """One row per drift CHECK on a batch (drift_detected tells if it is an alert)."""
    __tablename__ = "drift_alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    batch_size: Mapped[int] = mapped_column(Integer)
    drift_detected: Mapped[bool] = mapped_column(Boolean)
    share_drifted: Mapped[float] = mapped_column(Float)
    drifted_features: Mapped[list] = mapped_column(JSON)
    engine: Mapped[str] = mapped_column(String(32))
    last_prediction_id: Mapped[int] = mapped_column(Integer)  # batch covers ids up to this one


engine = create_engine(config.database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(retries: int = 30, delay: float = 2.0) -> None:
    """Create tables if missing; waits for PostgreSQL to come up."""
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(engine)
            logger.info("Database ready")
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Database not ready (%s/%s): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError("Database did not become ready in time")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
