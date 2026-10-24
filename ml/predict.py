"""Inference logic - kept free of FastAPI/DB code so it can become its own service later."""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import joblib
import pandas as pd


class ModelService:
    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or os.getenv("MODEL_DIR", "models")
        self.model = None
        self.metadata: dict = {}
        self.reference: Optional[pd.DataFrame] = None

    def load(self) -> None:
        self.model = joblib.load(os.path.join(self.model_dir, "model.joblib"))
        with open(os.path.join(self.model_dir, "metadata.json"), encoding="utf-8") as f:
            self.metadata = json.load(f)
        ref_path = os.path.join(self.model_dir, "reference.csv")
        self.reference = pd.read_csv(ref_path) if os.path.exists(ref_path) else None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    @property
    def version(self) -> str:
        return str(self.metadata.get("model_version", "unknown"))

    @property
    def features(self) -> List[str]:
        return self.metadata.get("features", [])

    def predict(self, features: Dict[str, float]) -> float:
        if not self.loaded:
            raise RuntimeError("Model is not loaded. Run the training pipeline first (python -m ml.train).")
        row = pd.DataFrame([[features[c] for c in self.features]], columns=self.features)
        return float(self.model.predict(row)[0])
