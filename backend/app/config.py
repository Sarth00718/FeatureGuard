"""All configuration comes from environment variables (see .env.example)."""
import os


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "featureguard")
    password = os.getenv("POSTGRES_PASSWORD", "change-me")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    name = os.getenv("POSTGRES_DB", "featureguard")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


MODEL_DIR = os.getenv("MODEL_DIR", "models")
DRIFT_ENGINE = os.getenv("DRIFT_ENGINE", "evidently")        # "evidently" or "ks"
DRIFT_BATCH_SIZE = int(os.getenv("DRIFT_BATCH_SIZE", "30"))  # accepted requests per drift check
DRIFT_SHARE_THRESHOLD = float(os.getenv("DRIFT_SHARE_THRESHOLD", "0.3"))
DRIFT_REPORT_DIR = os.getenv("DRIFT_REPORT_DIR", "reports/drift")
