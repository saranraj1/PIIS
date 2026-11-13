# Production-ready multi-stage Docker build for PIIS M6 API service
FROM python:3.11-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[api,observability]" && \
    pip install --no-cache-dir .

# Runtime Stage
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-privileged service user
RUN groupadd -g 1001 piis && \
    useradd -u 1001 -g piis -s /bin/bash -m piis

# Copy python site-packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY pyproject.toml README.md ./
COPY schemas/ ./schemas/
COPY src/ ./src/
COPY configs/ ./configs/

# Runtime environment settings
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIIS_ENVIRONMENT=development \
    PIIS_PORT=8000 \
    PIIS_HOST=0.0.0.0

USER piis

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "piis.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
