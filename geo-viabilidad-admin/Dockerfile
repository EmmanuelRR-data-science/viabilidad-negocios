# syntax=docker/dockerfile:1
# Build context: raíz del monorepo (geo-viabilidad-negocios/)

FROM python:3.11-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv

WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY geo-viabilidad-data /src/geo-viabilidad-data
COPY geo-viabilidad-admin/pyproject.toml geo-viabilidad-admin/uv.lock /src/geo-viabilidad-admin/

WORKDIR /src/geo-viabilidad-admin

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

COPY geo-viabilidad-admin/admin/ admin/

EXPOSE 8501

CMD ["flask", "--app", "admin.app:app", "run", "--host", "0.0.0.0", "--port", "8501"]
