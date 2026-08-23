#!/bin/bash
# Full deploy: pull latest code, install deps, restart service
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="cooperation-watcher"

echo "=== Deploying $SERVICE_NAME ==="
echo "Project: $PROJECT_DIR"
cd "$PROJECT_DIR"

# 1. Pull latest code
echo ""
echo "[1/4] Pulling latest code..."
git pull origin "$(git rev-parse --abbrev-ref HEAD)"

# 2. Activate venv and update dependencies
echo ""
echo "[2/4] Updating dependencies..."
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Run scripts/install.sh first."
    exit 1
fi
source .venv/bin/activate
pip install -r requirements.txt -q
echo "Dependencies up to date."

# 3. Initialize / migrate database
echo ""
echo "[3/4] Initializing database..."
python -c "from app.database import init_db; init_db(); print('Database ready.')"

# 4. Restart service
echo ""
echo "[4/4] Restarting service..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    sudo systemctl restart "$SERVICE_NAME"
    sleep 2
    sudo systemctl status "$SERVICE_NAME" --no-pager
else
    echo "Service not active. Run: sudo bash scripts/install-service.sh"
fi

echo ""
echo "=== Deploy complete ==="
echo "Logs: sudo journalctl -u $SERVICE_NAME -f"
