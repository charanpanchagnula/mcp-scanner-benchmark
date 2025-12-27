#!/bin/bash

# run_full_benchmark.sh
# 1. Tears down existing Docker environment
# 2. Rebuilds completely (--no-cache)
# 3. Waits for services to be ready
# 4. Triggers sequential scans for all golden repos

set -e

echo "🛑 Tearing down existing services..."
docker-compose down

echo "🧹 Clearing old scan data..."
# Use docker run to clear files to avoid permission issues
docker run --rm -v $(pwd)/backend:/app/backend alpine sh -c "rm -rf /app/backend/scan_results/* /app/backend/scan_index.json"

echo "🏗️  Rebuilding services (this may take a while)..."
docker-compose up -d --build --force-recreate

echo "⏳ Waiting for Backend API to be ready..."
until curl -s http://localhost:8000/docs > /dev/null; do
    echo "   ... Backend not ready yet. Retrying in 5s ..."
    sleep 5
done
echo "✅ Backend is ONLINE!"

echo "🚀 Starting Full Benchmark Suite..."
# Using the re-benchmark_golden.py script which waits for each scan
# We need to run this inside the container or using local python.
# Since local python environment might vary, let's try running it locally if we have dependencies,
# OR simpler: run it via docker compose exec.

# Check if we can run it inside the backend container to use its environment
docker-compose exec -T backend uv run python scripts/re-benchmark_golden.py

echo "🎉 All benchmarks completed!"
