FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create production .env file with backend API URL
RUN echo "API_URL=https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1" > .env && \
    echo "API_TIMEOUT=30" >> .env && \
    echo "API_MAX_RETRIES=3" >> .env && \
    echo "API_CACHE_TTL=300" >> .env && \
    echo "DEFAULT_LATITUDE=38.86" >> .env && \
    echo "DEFAULT_LONGITUDE=-77.055" >> .env && \
    echo "DEFAULT_ZOOM=13" >> .env && \
    echo "MAP_HEIGHT=650" >> .env && \
    echo "MIN_RADIUS_PX=6" >> .env && \
    echo "MAX_RADIUS_PX=30" >> .env && \
    echo "COLOR_LOW_THRESHOLD=60" >> .env && \
    echo "COLOR_HIGH_THRESHOLD=75" >> .env

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:${PORT}/_stcore/health || exit 1

# Run Streamlit with new multipage app structure
CMD streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=true
