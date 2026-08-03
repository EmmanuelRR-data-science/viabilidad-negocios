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

# Conservar layout relativo para path dep: ../geo-viabilidad-data
COPY geo-viabilidad-data /src/geo-viabilidad-data
COPY geo-viabilidad-api/pyproject.toml geo-viabilidad-api/uv.lock /src/geo-viabilidad-api/

WORKDIR /src/geo-viabilidad-api

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Path dep en lock es editable; en imagen se reinstala no-editable para que no dependa del path del builder.
RUN uv sync --frozen --no-dev --no-install-project \
    && uv pip install --python /opt/venv/bin/python --reinstall /src/geo-viabilidad-data

FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY geo-viabilidad-api/app/ app/
COPY geo-viabilidad-api/scripts/ scripts/
COPY geo-viabilidad-api/backups/ backups/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
