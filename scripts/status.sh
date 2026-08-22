#!/bin/bash
echo "=== Service Status ==="
sudo systemctl status cooperation-watcher --no-pager

echo ""
echo "=== Recent Logs ==="
sudo journalctl -u cooperation-watcher -n 30 --no-pager

echo ""
echo "=== Database ==="
if [ -f "data/cooperation.db" ]; then
    SIZE=$(du -sh data/cooperation.db | cut -f1)
    echo "Size: $SIZE"
else
    echo "Database not found."
fi
