FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    lightgbm \
    pandas \
    numpy \
    scikit-learn \
    wandb \
    "pydantic-settings[yaml]" \
    "psycopg[binary]" \
    sqlalchemy

COPY common/src/ common/src/
COPY jobs/src/ jobs/src/
COPY pipelines/src/ pipelines/src/
COPY env/config/ env/config/

ENV PYTHONPATH=/app/common/src:/app/jobs/src:/app/pipelines/src
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "pipelines.housing_prices.main"]
