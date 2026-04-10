FROM python:3.11-slim

LABEL maintainer="Astrology App Team"
LABEL description="Celestial Arc - Astrology Web Application"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p instance uploads logs

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/config')" || exit 1

# Expose port
EXPOSE 5000

# Run with gunicorn
CMD ["gunicorn", "-c", "gunicorn_config.py", "app:app"]
