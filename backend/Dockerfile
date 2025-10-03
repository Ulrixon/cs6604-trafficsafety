# Use an official lightweight Python image.
FROM python:3.13-slim

# Set environment variables.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (if any) and create a non‑root user.
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/* && \
    adduser --disabled-password --gecos "" appuser

# Set work directory.
WORKDIR /app

# Install Python dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY . .

# Change to non‑root user.
USER appuser

# Expose the port Fly.io expects (default $PORT, fallback 8080).
EXPOSE 8080

# Command to run the FastAPI app. Fly.io provides the PORT env variable.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 2"]
