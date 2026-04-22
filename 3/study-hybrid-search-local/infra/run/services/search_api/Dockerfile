FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends libgomp1 \
	&& rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir uv \
	&& uv export --no-dev --format requirements-txt --no-hashes -o /tmp/requirements.txt \
	&& pip install --no-cache-dir -r /tmp/requirements.txt

COPY app ./app
COPY common/src ./common/src
COPY pipeline ./pipeline
COPY ml ./ml
COPY definitions ./definitions

ENV PYTHONPATH=/app:/app/common/src:/app/pipeline/batch:/app/pipeline

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
