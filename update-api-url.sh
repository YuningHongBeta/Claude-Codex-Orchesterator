#!/bin/bash
# Update the API URL in the deployed frontend on Lambda
#
# Usage: ./update-api-url.sh [https://your-tunnel-url.trycloudflare.com]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
URL_FILE="$SCRIPT_DIR/logs/tunnel.url"
LOG_FILE="$SCRIPT_DIR/logs/tunnel.log"

API_URL="$1"
if [ -z "$API_URL" ]; then
    if [ -f "$URL_FILE" ]; then
        API_URL="$(cat "$URL_FILE" | tail -n 1 | tr -d '\r\n')"
    elif [ -f "$LOG_FILE" ]; then
        API_URL="$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | tail -n 1)"
    fi
fi

if [ -z "$API_URL" ]; then
    echo "Usage: $0 <API_URL>"
    echo "Example: $0 https://abc-xyz.trycloudflare.com"
    echo "No tunnel URL found in $URL_FILE or $LOG_FILE"
    exit 1
fi

REMOTE_HOST="Lambda"
REMOTE_PATH="public_html/orchestrator/index.html"
LOCAL_DIST="$SCRIPT_DIR/web/dist/index.html"

echo "🔄 Updating API URL to: $API_URL"

# Update local dist if present
if [ -f "$LOCAL_DIST" ]; then
    API_URL="$API_URL" LOCAL_DIST="$LOCAL_DIST" python3 - <<'PY'
import re
import os
from pathlib import Path
path = Path(os.environ.get("LOCAL_DIST", ""))
text = path.read_text(encoding="utf-8")
api_url = os.environ.get("API_URL", "")
if not api_url:
    raise SystemExit("API_URL is empty")
new = re.sub(r'window\\.ORCHESTRATOR_API_BASE\\s*=\\s*\"[^\"]*\"',
             f'window.ORCHESTRATOR_API_BASE = "{api_url}"', text)
if text != new:
    path.write_text(new, encoding="utf-8")
PY
fi

# Update the API URL in the remote index.html
ssh "$REMOTE_HOST" "sed -i.bak 's|window.ORCHESTRATOR_API_BASE = \"[^\"]*\"|window.ORCHESTRATOR_API_BASE = \"$API_URL\"|' ~/$REMOTE_PATH"

echo "✅ Updated! The frontend will now use: $API_URL"
echo ""
echo "📍 Access at: https://YOUR_SERVER/~YOUR_USER/orchestrator/"
