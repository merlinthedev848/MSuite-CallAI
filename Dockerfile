FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for audio codecs & networking)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project definition and install dependencies
COPY pyproject.toml requirements.txt ./
RUN uv pip install --system -r requirements.txt

# Copy application source code
COPY . .

# Expose web dashboard port
EXPOSE 8000

# Default command: run FastAPI dashboard and agent
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
