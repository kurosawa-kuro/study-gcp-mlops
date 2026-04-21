FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AIP_HTTP_PORT=8080

WORKDIR /workspace

RUN pip install --no-cache-dir --upgrade pip

COPY common /workspace/common
COPY ml/embed /workspace/ml-embed

RUN pip install --no-cache-dir /workspace/common /workspace/ml-embed

# encoder_server.py imports `embed.e5_encoder` (installed above) — run as script.
COPY ml/embed/server/encoder_server.py /workspace/encoder_server.py
CMD ["python", "/workspace/encoder_server.py"]
