"""Data validation step. Exits with code 1 if the dataset is not usable."""
import os
import sys

import pandas as pd

from featureguard.validation import CSV_RENAME, FEATURE_RANGES, TARGET
from ml.preprocessing import load_params


def validate_dataset(csv_path: str) -> list:
    problems = []
    if not os.path.exists(csv_path):
        return [f"Dataset not found: {csv_path} (run: python ml/download_data.py)"]
    df = pd.read_csv(csv_path, sep=";").rename(columns=CSV_RENAME)
    expected = list(FEATURE_RANGES) + [TARGET]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        return [f"Missing columns: {missing}"]
    if len(df) < 500:
        problems.append(f"Too few rows: {len(df)}")
    if df[expected].isnull().any().any():
        problems.append("Dataset contains missing values")
    for col in expected:
        if not pd.api.types.is_numeric_dtype(df[col]):
            problems.append(f"Column {col} is not numeric")
    for col, (low, high) in FEATURE_RANGES.items():
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            bad = int(((df[col] < low) | (df[col] > high)).sum())
            if bad:
                problems.append(f"{col}: {bad} rows outside hard range [{low}, {high}]")
    if pd.api.types.is_numeric_dtype(df[TARGET]) and not df[TARGET].between(0, 10).all():
        problems.append("quality must be between 0 and 10")
    return problems


def main() -> int:
    path = load_params()["data"]["raw_path"]
    problems = validate_dataset(path)
    if problems:
        print("DATA VALIDATION FAILED:")
        for p in problems:
            print(" -", p)
        return 1
    print(f"Data validation passed for {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
