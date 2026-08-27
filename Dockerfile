FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FIXTRACE_ALLOW_LOCAL_EXECUTION=0

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "fixtrace.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
