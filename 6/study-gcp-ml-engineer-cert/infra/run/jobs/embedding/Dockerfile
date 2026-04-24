# Batch embedding job container (Cloud Run Job / Vertex Custom Job).
# Build context: repository root. Entry point: ml.data.datasets.embedding_batch.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml /workspace/pyproject.toml
COPY ml /workspace/ml
COPY pipeline /workspace/pipeline

RUN pip install --no-cache-dir /workspace

CMD ["python", "-m", "pipeline.data_job.main", "submit"]
