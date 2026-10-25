"""All configuration comes from environment variables (see .env.example).
The backend always uses PostgreSQL in production - start it with Docker Compose:
    docker compose --env-file .env -f deployment/docker-compose.yml up -d postgres

DATABASE_URL env var overrides the individual POSTGRES_* vars (used by tests).
"""
import os


def database_url() -> str:
    # DATABASE_URL override — used by the test suite (SQLite in-memory)
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("POSTGRES_USER", "featureguard")
    password = os.getenv("POSTGRES_PASSWORD", "mlopsfeatureguard")
    host = os.getenv("POSTGRES_HOST", "localhost")
    name = os.getenv("POSTGRES_DB", "featureguard")

    # POSTGRES_PORT is injected by Kubernetes as "tcp://10.x.x.x:5432"
    # We always use 5432 — extract only the numeric port if needed.
    raw_port = os.getenv("POSTGRES_PORT", "5432")
    if raw_port.startswith("tcp://"):
        port = "5432"
    else:
        port = raw_port

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


MODEL_DIR = os.getenv("MODEL_DIR", "models")
DRIFT_ENGINE = os.getenv("DRIFT_ENGINE", "evidently")        # "evidently" or "ks"
DRIFT_BATCH_SIZE = int(os.getenv("DRIFT_BATCH_SIZE", "30"))  # accepted requests per drift check
DRIFT_SHARE_THRESHOLD = float(os.getenv("DRIFT_SHARE_THRESHOLD", "0.3"))
DRIFT_REPORT_DIR = os.getenv("DRIFT_REPORT_DIR", "reports/drift")
