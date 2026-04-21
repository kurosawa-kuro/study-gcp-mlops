# Vertex AI Custom Training Job: LightGBM LambdaRank reranker trainer.
# Build context: repository root. Entry point: ml.training.trainer.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml /workspace/pyproject.toml
COPY ml /workspace/ml

RUN pip install --no-cache-dir /workspace

CMD ["python", "-m", "ml.training.trainer", "--mode", "kfp"]
