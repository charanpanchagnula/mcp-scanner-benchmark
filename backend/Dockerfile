# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
# Copy frontend dependencies
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
# Copy frontend source
COPY frontend/ .
# Build static site (output to out/)
RUN npm run build

# Stage 2: Final Backend Image
FROM python:3.12-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install npm scanners
RUN npm install -g typescript ts-node @types/node mcp-shield mcp-fortress

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
RUN ln -s /usr/bin/uv /usr/bin/uvx

WORKDIR /app

# Copy dependency files first
COPY backend/pyproject.toml backend/uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy backend source
COPY backend/ .

# Build mcp-watch tool (if needed)
RUN cd scanners/mcp_watch_tool && npm install && npm run build

# Copy Built Frontend from Stage 1 to '/static' folder (outside /app to avoid volume masking)
COPY --from=frontend-builder /app/frontend/out /static

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
