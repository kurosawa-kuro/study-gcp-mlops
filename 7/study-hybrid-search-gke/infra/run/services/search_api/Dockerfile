# Cloud Run Service: search-api (FastAPI proxy to Vertex AI endpoints).
# Build context: repository root.

FROM ghcr.io/astral-sh/uv:0.5.4-python3.12-bookworm-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /src

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --extra app --no-install-project || \
    uv sync --frozen --no-dev --no-install-project

COPY app/ app/
COPY ml/  ml/
COPY scripts/ scripts/
RUN uv sync --frozen --no-dev --extra app --no-editable || \
    uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim-bookworm AS runtime

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /src/app /home/app/app
COPY --from=builder /src/ml /home/app/ml
COPY --from=builder /src/scripts /home/app/scripts
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    LOG_AS_JSON=1 \
    GCP_LOGGING_ENABLED=1

RUN useradd --system --uid 1001 --home-dir /home/app app \
    && mkdir -p /home/app \
    && chown -R app:app /home/app
USER app
WORKDIR /home/app

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
