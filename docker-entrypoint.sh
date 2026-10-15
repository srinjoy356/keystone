#!/bin/sh
# FalkorDB (and its built-in Browser on :3000) via the base image's launcher; the app takes $PORT (default 8000).
APP_PORT="${PORT:-8000}"
PORT=3000 /var/lib/falkordb/bin/run.sh &
until redis-cli ping 2>/dev/null | grep -q PONG; do sleep 0.5; done
exec /venv/bin/python -m uvicorn keystone.api:app --host 0.0.0.0 --port "$APP_PORT"
