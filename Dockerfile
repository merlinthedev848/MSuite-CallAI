FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (audio codecs, networking, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency specifications and install packages into system Python
COPY pyproject.toml requirements.txt ./
RUN uv pip install --system -r requirements.txt

# Copy application source code and scripts
COPY . .

# Ensure entrypoint script is executable
RUN chmod +x /app/entrypoint.sh

# Expose HTTP dashboard and WebSocket port
EXPOSE 8000

# Run both the web dashboard and voice agent worker cleanly
ENTRYPOINT ["/app/entrypoint.sh"]
