# syntax=docker/dockerfile:1

# --- Builder Stage ---
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install system tools for compiling wheel binary dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies in standard system paths
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Final Stage ---
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy python packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY admin_app.py .
COPY ingest_all_states.py .
COPY .kiro/ .kiro/

# Expose port for Streamlit
EXPOSE 8501

# Run the Streamlit admin dashboard
ENTRYPOINT ["streamlit", "run", "admin_app.py", "--server.port=8501", "--server.address=0.0.0.0"]

