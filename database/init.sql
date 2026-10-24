-- Reference schema. The API also creates these tables at startup (idempotent),
-- so this file is mounted into PostgreSQL only as an explicit, readable schema.
CREATE TABLE IF NOT EXISTS predictions (
    id                SERIAL PRIMARY KEY,
    features          JSON        NOT NULL,
    predicted_quality DOUBLE PRECISION,
    model_version     VARCHAR(64) NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    validation_status VARCHAR(16) NOT NULL,   -- accepted | rejected
    validation_errors JSON
);
CREATE TABLE IF NOT EXISTS drift_alerts (
    id                 SERIAL PRIMARY KEY,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    batch_size         INTEGER     NOT NULL,
    drift_detected     BOOLEAN     NOT NULL,
    share_drifted      DOUBLE PRECISION NOT NULL,
    drifted_features   JSON        NOT NULL,
    engine             VARCHAR(32) NOT NULL,
    last_prediction_id INTEGER     NOT NULL
);
