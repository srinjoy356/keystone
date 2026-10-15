#!/bin/sh
# Start FalkorDB (the base image's own launcher), wait until it answers, then serve the app.
/var/lib/falkordb/bin/run.sh redis-server --loadmodule /var/lib/falkordb/bin/falkordb.so &
until redis-cli ping 2>/dev/null | grep -q PONG; do sleep 0.5; done
exec /venv/bin/python -m uvicorn keystone.api:app --host 0.0.0.0 --port "${PORT:-8000}"
