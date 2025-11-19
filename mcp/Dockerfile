FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code to mcp/ subdirectory to preserve package structure
COPY . mcp/

# Copy entrypoint script to /app root for ENTRYPOINT command
RUN cp mcp/entrypoint.sh /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8080

# Health check (only applies when running as web service)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || true

# Use entrypoint script to handle web/worker roles
# Role is determined by SERVICE_ROLE env var (default: web)
ENTRYPOINT ["/app/entrypoint.sh"]
