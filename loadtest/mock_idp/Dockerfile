FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system .

COPY mock_cilogon.py ./

EXPOSE 8080

ENV MOCK_LATENCY_MS=150 \
    MOCK_DEFAULT_AUDIENCE=loadtest

CMD ["uvicorn", "mock_cilogon:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
