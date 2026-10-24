# FeatureGuard backend - FastAPI served by uvicorn (build context = repository root)
# Train the model first (python -m ml.train) so ./models exists before the build.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt

RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY ml/ ml/
COPY featureguard/ featureguard/
COPY models/ models/

RUN useradd -m appuser && mkdir -p reports/drift && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MODEL_DIR=/app/models

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
