FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Google Cloud SDK
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create .env file placeholder (will be populated at runtime)
RUN touch .env

# Expose port (Cloud Run uses PORT env var, defaults to 8080)
EXPOSE 8080

# Set default environment variables
ENV PORT=8080 \
    VTTI_DB_NAME=vtsi \
    VTTI_DB_USER=postgres \
    VTTI_DB_HOST=34.140.49.230 \
    VTTI_DB_PORT=5432

# Run the application directly with uvicorn
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
