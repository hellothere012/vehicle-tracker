#!/usr/bin/env bash
set -e

docker build -t vehicle-tracker "$@" .

echo "Image built as vehicle-tracker. Run with:"
echo "  docker run --env-file .env -p 8000:8000 vehicle-tracker"
