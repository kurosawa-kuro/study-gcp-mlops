FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends libgomp1 \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/src ./app/src
COPY common/src ./common/src
COPY jobs/src ./jobs/src
COPY pipelines/src ./pipelines/src
COPY definitions ./definitions

ENV PYTHONPATH=/app/app/src:/app/common/src:/app/jobs/src:/app/pipelines/src

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
