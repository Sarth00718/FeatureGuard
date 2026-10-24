"""Data loading, splitting and the sklearn Pipeline (preprocessing + model)."""
from __future__ import annotations

from typing import Tuple

import pandas as pd
import yaml
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from featureguard.validation import CSV_RENAME, FEATURES, TARGET


def load_params(path: str = "params.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_dataset(csv_path: str, drop_duplicates: bool = False) -> pd.DataFrame:
    """Load the UCI red wine CSV (semicolon separated) and use snake_case column names."""
    df = pd.read_csv(csv_path, sep=";")
    df = df.rename(columns=CSV_RENAME)
    if drop_duplicates:
        df = df.drop_duplicates().reset_index(drop=True)
    return df


def split_dataset(df: pd.DataFrame, test_size: float, random_state: int
                  ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Reproducible train/test split (fixed random_state)."""
    X, y = df[FEATURES], df[TARGET]
    return train_test_split(X, y, test_size=test_size, random_state=random_state)


def build_pipeline(model_params: dict) -> Pipeline:
    """Scaler + Random Forest. Only sklearn classes, so the saved file loads anywhere."""
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("model", RandomForestRegressor(**model_params)),
        ]
    )
