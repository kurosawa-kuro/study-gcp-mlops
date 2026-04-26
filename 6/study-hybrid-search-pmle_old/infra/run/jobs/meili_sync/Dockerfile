# One-shot Cloud Run Job container to sync properties_cleaned -> Meilisearch.
# Build context: repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        "google-cloud-bigquery>=3.25" \
        "google-auth>=2.36" \
        "httpx>=0.27"

COPY infra/run/jobs/meili_sync/sync_meili_job.py /app/sync_meili_job.py

ENTRYPOINT ["python"]
CMD ["/app/sync_meili_job.py"]
