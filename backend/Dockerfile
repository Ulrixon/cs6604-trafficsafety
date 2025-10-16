FROM python:3.12-slim-bullseye
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app

WORKDIR /app

# Install curl and clean up
RUN apt update -y && \
    apt install -y curl && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*


RUN uv sync --locked




EXPOSE 8000
HEALTHCHECK --start-period=5s --interval=30s --timeout=3s \
    CMD curl --silent --show-error --fail \
    --user-agent "docker-healthcheck" \
    "http://localhost:8080/healthz" \
    || exit 1

CMD ["uv", "run", "uvicorn", "--host", "0.0.0.0", "--port", "8000", "api:app"]