#!/bin/sh
# ──────────────────────────────────────────────────────────────────────────────
# docker-entrypoint.sh — SEC Semantic Search API container entrypoint
#
# Runs as root briefly to fix volume directory ownership (Docker Desktop mounts
# named volumes as root), then drops to the non-root 'app' user via gosu before
# exec-ing the CMD (uvicorn).
# ──────────────────────────────────────────────────────────────────────────────
set -e

# Fix ownership of volume mount points so the 'app' user can write to them.
# This is necessary because Docker initialises named volume directories as root.
chown app:app /app/data/chroma_db /app/data/sqlite /app/logs

# Drop to non-root user and exec the application (replaces this shell process).
exec gosu app "$@"
