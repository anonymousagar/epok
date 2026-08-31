#!/usr/bin/env bash
set -e

MODE="${MODE:-api}"

if [ "$MODE" = "worker" ]; then
    echo "Starting Epok Temporal Worker Daemon..."
    exec python /app/src/worker/worker.py
else
    echo "Starting Epok FastAPI Webhook Gateway on port ${PORT:-8080}..."
    exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
fi

