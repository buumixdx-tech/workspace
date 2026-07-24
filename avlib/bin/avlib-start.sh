#!/bin/bash
# avlib WSL launcher — keeps the server running in foreground with retry on crash.
# Usage: ./bin/avlib-start.sh
# Stop: Ctrl-C (^C). Or: pkill -f 'node src/server.js'

set -e
cd "$(dirname "$0")/.."

# Use the n-managed node (24.x with node:sqlite built-in)
export PATH=/home/buumi/n/bin:$PATH
export NODE_OPTIONS="--disable-warning=ExperimentalWarning"

# Optional: pre-create data dir
mkdir -p data/covers data/hls data/scratch

echo "[avlib] starting on http://0.0.0.0:8123 (pid $$)"
exec node src/server.js
