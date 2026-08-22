#!/bin/bash
set -e

echo "=== cooperation-watcher-bot installer ==="

# 1. Python version check
PYTHON=$(which python3.12 2>/dev/null || which python3 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.12+ not found. Install with: sudo apt install python3.12"
    exit 1
fi

PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PY_VER — OK"

# 2. Virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi

source .venv/bin/activate

# 3. Install requirements
echo "Installing requirements..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "Dependencies installed."

# 4. Create directories
mkdir -p data logs
echo "Directories: data/ logs/ — OK"

# 5. Check .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env file created from .env.example"
    echo "    Edit it now: nano .env"
    echo "    Fill in: TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_USER_ID"
    echo ""
else
    echo ".env file found — OK"
fi

# 6. Initialize database
echo "Initializing database..."
python -c "from app.database import init_db; init_db(); print('Database ready.')"

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env:          nano .env"
echo "  2. Run manually:       source .venv/bin/activate && python -m app.main"
echo "  3. Install as service: sudo bash scripts/install-service.sh"
echo ""
