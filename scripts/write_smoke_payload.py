"""Write the smoke test JSON payload to a file.
Called by the Jenkinsfile to avoid Windows bat JSON escaping issues.
Usage: python scripts/write_smoke_payload.py
"""
import json, os

payload = {
    "fixed_acidity": 7.4,
    "volatile_acidity": 0.7,
    "citric_acid": 0.0,
    "residual_sugar": 1.9,
    "chlorides": 0.076,
    "free_sulfur_dioxide": 11,
    "total_sulfur_dioxide": 34,
    "density": 0.9978,
    "ph": 3.51,
    "sulphates": 0.56,
    "alcohol": 9.4,
}

with open("smoke_payload.json", "w") as f:
    json.dump(payload, f)

print("smoke_payload.json written:", json.dumps(payload))
