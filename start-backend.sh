#!/bin/bash
# Start the orchestrator backend with CORS enabled for remote access

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-8088}"

echo "🎼 Starting Orchestrator Backend..."
echo "   Port: $PORT"
echo "   CORS: enabled for all origins"
echo ""
echo "API endpoints:"
echo "   GET  /api/jobs         - List all jobs"
echo "   GET  /api/jobs/{id}    - Get job details"
echo "   POST /api/jobs         - Create new job"
echo "   GET  /api/jobs/{id}/score - Get performer assignments"
echo "   GET  /api/jobs/{id}/logs  - List log files"
echo ""
echo "Press Ctrl+C to stop."
echo ""

python3 web_server.py --host 0.0.0.0 --port "$PORT" --cors-origin '*'
