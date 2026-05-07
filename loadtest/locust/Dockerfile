FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system .

COPY *.py ./

EXPOSE 8089 5557 5558

CMD ["locust", "--master", "--host", "https://profile.hcommons-test.org"]
