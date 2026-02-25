#!/bin/bash
# RPD Meta Extractor - Server installation and run script for Linux/macOS
# Usage: ./install_and_run.sh [port]
# Bind to 0.0.0.0 for intranet access (accessible from other machines on the network)

set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)"

PORT="${1:-8000}"
HOST="${2:-0.0.0.0}"

echo "=== RPD Meta Extractor - Server Setup ==="
echo "Directory: $SCRIPT_DIR"
echo "Host: $HOST (0.0.0.0 = all interfaces / intranet)"
echo "Port: $PORT"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing/upgrading dependencies..."
pip install -q -U pip
pip install -q -r requirements.txt

echo ""
echo "=== Starting RPD Meta Extractor ==="
echo "  App UI:    http://localhost:$PORT"
echo "  Intranet:  http://$(hostname -f 2>/dev/null || hostname):$PORT"
echo "  API Docs:  http://localhost:$PORT/docs"
echo "  Health:    http://localhost:$PORT/health"
echo ""
echo "Press Ctrl+C to stop."
echo ""

RPD_HOST="$HOST" RPD_PORT="$PORT" python -m uvicorn rpd.main:app --host "$HOST" --port "$PORT"
