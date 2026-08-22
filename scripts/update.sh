#!/bin/bash
set -e

echo "=== Updating cooperation-watcher-bot ==="

git pull

source .venv/bin/activate
pip install -r requirements.txt -q

echo "Restarting service..."
sudo systemctl restart cooperation-watcher

sleep 2
sudo systemctl status cooperation-watcher --no-pager

echo "=== Update complete ==="
