"""FeatureGuard - statistical data drift monitoring (batch-level).

Drift is a property of a DISTRIBUTION, so we never judge a single request.
The API collects accepted requests into a batch (default 30 rows) and then
compares that batch with the reference (training) data.

Two engines are available:
  * "evidently" - Evidently's DataDriftPreset (default, also gives an HTML report)
  * "ks"        - plain per-feature Kolmogorov-Smirnov test with scipy (fallback)
A drift alert is only RECORDED and shown on the dashboard. It never blocks requests.
"""
from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from typing import List, Optional

import pandas as pd

logger = logging.getLogger("featureguard.drift")


@dataclass
class DriftResult:
    engine: str
    batch_size: int
    drift_detected: bool
    share_drifted: float
    drifted_features: List[str] = field(default_factory=list)
    p_values: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _ks_drift(reference: pd.DataFrame, current: pd.DataFrame, features, p_threshold: float):
    from scipy.stats import ks_2samp

    p_values = {}
    for col in features:
        _, p = ks_2samp(reference[col].to_numpy(), current[col].to_numpy())
        p_values[col] = float(p)
    drifted = [c for c, p in p_values.items() if p < p_threshold]
    return drifted, p_values


def _evidently_drift(reference: pd.DataFrame, current: pd.DataFrame, features, html_path: Optional[str]):
    from evidently.metric_preset import DataDriftPreset
    from evidently.report import Report

    report = Report(metrics=[DataDriftPreset(drift_share=0.5)])
    report.run(reference_data=reference[features], current_data=current[features])
    # Find the DataDriftTable result by key (do not rely on metric order)
    result = next(m["result"] for m in report.as_dict()["metrics"] if "drift_by_columns" in m["result"])
    by_col = result["drift_by_columns"]
    drifted = [c for c, info in by_col.items() if info["drift_detected"]]
    p_values = {c: float(info.get("drift_score", float("nan"))) for c, info in by_col.items()}
    if html_path:
        os.makedirs(os.path.dirname(html_path) or ".", exist_ok=True)
        report.save_html(html_path)
    return drifted, p_values


def detect_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    features: List[str],
    engine: str = "evidently",
    share_threshold: float = 0.3,
    p_threshold: float = 0.01,
    min_batch_size: int = 30,
    html_path: Optional[str] = None,
) -> DriftResult:
    """Compare a batch with the reference data.

    drift_detected is True when the share of drifted features >= share_threshold.
    Raises ValueError if the batch is too small to be statistically meaningful.
    """
    if len(current) < min_batch_size:
        raise ValueError(
            f"Batch of {len(current)} rows is too small for drift detection (minimum {min_batch_size})."
        )
    used = engine
    try:
        if engine == "evidently":
            drifted, p_values = _evidently_drift(reference, current, features, html_path)
        else:
            drifted, p_values = _ks_drift(reference, current, features, p_threshold)
    except ImportError:
        logger.warning("Evidently not installed - falling back to the KS test engine")
        used = "ks"
        drifted, p_values = _ks_drift(reference, current, features, p_threshold)

    share = len(drifted) / len(features)
    return DriftResult(
        engine=used,
        batch_size=len(current),
        drift_detected=share >= share_threshold,
        share_drifted=round(share, 4),
        drifted_features=drifted,
        p_values=p_values,
    )
