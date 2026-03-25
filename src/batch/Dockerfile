FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from sklearn.datasets import fetch_california_housing; fetch_california_housing()"
ENV GIT_PYTHON_REFRESH=quiet
COPY *.py ./
CMD ["python", "main.py"]
