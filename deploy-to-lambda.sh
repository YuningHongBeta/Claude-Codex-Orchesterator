#!/bin/bash
#!/bin/bash
# Deploy orchestrator web UI to Lambda server

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIST="$SCRIPT_DIR/web/dist"
REMOTE_HOST="Lambda"
REMOTE_PATH="public_html/orchestrator"

echo "🚀 Deploying to $REMOTE_HOST:~/$REMOTE_PATH..."

# Create remote directory if it doesn't exist
ssh "$REMOTE_HOST" "mkdir -p ~/$REMOTE_PATH"

# Sync files
rsync -avz --delete "$WEB_DIST/" "$REMOTE_HOST:~/$REMOTE_PATH/"

echo "✅ Deployment complete!"
echo ""
echo "📍 Access at: https://YOUR_SERVER/~YOUR_USER/orchestrator/"
echo ""
echo "⚠️  Don't forget to start the backend and tunnel (see README)"
