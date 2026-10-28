# Production Dockerfile for Google Cloud Run (Scale to Zero / Request-based)
FROM python:3.11-slim

# Prevent python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    DATA_DIR=/data

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ app/
COPY .streamlit/ .streamlit/
COPY scripts/ scripts/

# Create persistent storage directory
RUN mkdir -p /data/users

EXPOSE 8080

# Run Streamlit on Cloud Run's dynamic $PORT with exec
ENTRYPOINT ["sh", "-c", "exec streamlit run app/dashboard.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false"]
