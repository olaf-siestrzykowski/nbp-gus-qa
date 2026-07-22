#!/bin/sh
set -e

echo "=== Running ingestion ==="
python -m ingestion.ingest

echo "=== Starting server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"
