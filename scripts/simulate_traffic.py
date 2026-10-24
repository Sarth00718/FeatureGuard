"""Send demo traffic to the API (uses rows from the REAL dataset, so nothing is invented).

    python scripts/simulate_traffic.py --mode normal  --count 35
    python scripts/simulate_traffic.py --mode invalid --count 3
    python scripts/simulate_traffic.py --mode drift   --count 35

normal  : random rows from winequality-red.csv  -> should NOT raise a drift alert
invalid : one value pushed out of range         -> rejected with HTTP 422
drift   : rows shifted (more alcohol, more sulfur dioxide, ...) but still valid
          -> accepted one by one; once a batch is full the drift check raises an alert
"""
import argparse
import sys

import pandas as pd
import requests

from featureguard.validation import CSV_RENAME, FEATURE_RANGES, FEATURES

SHIFT = {"alcohol": 3.0, "total_sulfur_dioxide": 60.0, "volatile_acidity": 0.4,
         "ph": 0.4, "sulphates": 0.4, "chlorides": 0.1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["normal", "invalid", "drift"], default="normal")
    ap.add_argument("--count", type=int, default=35)
    ap.add_argument("--url", default="http://localhost/api")
    ap.add_argument("--csv", default="data/raw/winequality-red.csv")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, sep=";").rename(columns=CSV_RENAME)[FEATURES]
    sample = df.sample(args.count, replace=len(df) < args.count, random_state=None)
    ok = bad = 0
    for _, row in sample.iterrows():
        payload = {k: float(v) for k, v in row.items()}
        if args.mode == "drift":
            for k, delta in SHIFT.items():
                lo, hi = FEATURE_RANGES[k]
                payload[k] = min(payload[k] + delta, hi - 1e-6)
        if args.mode == "invalid":
            payload["alcohol"] = 99.0
        r = requests.post(f"{args.url}/predict", json=payload, timeout=30)
        if r.ok:
            ok += 1
        else:
            bad += 1
            if bad == 1:
                print("First rejection:", r.status_code, r.json())
    print(f"Sent {args.count} requests: {ok} accepted, {bad} rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
