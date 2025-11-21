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

# Create startup script that fetches secrets and starts the app
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Run the application with entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]
