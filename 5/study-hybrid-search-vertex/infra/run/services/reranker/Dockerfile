# Vertex AI Custom Prediction Routine: LightGBM reranker.
# Build context: repository root. Entry point: ml.serving.reranker.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AIP_HTTP_PORT=8080

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml /workspace/pyproject.toml
COPY ml /workspace/ml

RUN pip install --no-cache-dir /workspace

EXPOSE 8080
CMD ["python", "-m", "ml.serving.reranker"]
