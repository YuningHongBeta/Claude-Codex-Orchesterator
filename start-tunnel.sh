#!/bin/bash
# Start Cloudflare Tunnel to expose local orchestrator API over HTTPS
#
# This creates a public HTTPS URL for your local backend.
# The URL changes each time, so you'll need to update the frontend config.

set -e

LOCAL_PORT="${1:-8088}"
PROTOCOL="${2:-http2}"
EDGE_IP_VERSION="${3:-4}"

echo "🔗 Starting Cloudflare Tunnel..."
echo "   Local backend: http://localhost:$LOCAL_PORT"
echo "   Protocol: $PROTOCOL"
echo "   Edge IP: IPv$EDGE_IP_VERSION"
echo ""

exec cloudflared tunnel \
  --protocol "$PROTOCOL" \
  --edge-ip-version "$EDGE_IP_VERSION" \
  --url "http://localhost:$LOCAL_PORT" \
  --loglevel info
