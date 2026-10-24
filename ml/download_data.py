"""Download winequality-red.csv from the UCI repository into data/raw/.

Usage:  python ml/download_data.py
If the automatic download is blocked on your network, download the file manually from
https://archive.ics.uci.edu/dataset/186/wine+quality and place winequality-red.csv in data/raw/.
"""
import io
import os
import sys
import urllib.request
import zipfile

ZIP_URL = "https://archive.ics.uci.edu/static/public/186/wine+quality.zip"
DIRECT_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-red.csv"
OUT = os.path.join("data", "raw", "winequality-red.csv")


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.exists(OUT):
        print(f"{OUT} already exists - nothing to do.")
        return 0
    try:
        print(f"Downloading {DIRECT_URL}")
        with urllib.request.urlopen(DIRECT_URL, timeout=60) as r:
            data = r.read()
    except Exception as exc:  # fall back to the zip bundle
        print(f"Direct download failed ({exc}); trying zip bundle {ZIP_URL}")
        with urllib.request.urlopen(ZIP_URL, timeout=60) as r:
            zf = zipfile.ZipFile(io.BytesIO(r.read()))
        data = zf.read("winequality-red.csv")
    with open(OUT, "wb") as f:
        f.write(data)
    print(f"Saved {OUT} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
