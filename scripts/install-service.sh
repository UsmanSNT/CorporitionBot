#!/bin/bash
set -e

echo "=== Installing systemd service ==="

SERVICE_NAME="cooperation-watcher"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CURRENT_USER="$(whoami)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Run with sudo: sudo bash scripts/install-service.sh"
    exit 1
fi

# Check venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment not found. Run scripts/install.sh first."
    exit 1
fi

# Check .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "ERROR: .env file not found. Copy .env.example and fill in the values."
    exit 1
fi

# Detect the real user (who ran sudo)
REAL_USER="${SUDO_USER:-$CURRENT_USER}"

echo "Project dir : $PROJECT_DIR"
echo "Service user: $REAL_USER"
echo "Python      : $VENV_PYTHON"

# Write service file
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Cooperation Watcher Telegram Bot
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$VENV_PYTHON -m app.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "Service file written: $SERVICE_FILE"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

sleep 2
systemctl status "$SERVICE_NAME" --no-pager

echo ""
echo "=== Service installed and started ==="
echo "Logs: sudo journalctl -u $SERVICE_NAME -f"
