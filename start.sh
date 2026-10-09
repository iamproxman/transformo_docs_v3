#!/bin/bash
set -e

# Change to project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "🚀 Starting TransformoDocs System..."
echo "=================================================="

# Check or create python virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing/verifying backend dependencies..."
pip install --quiet -r backend/requirements.txt

echo "Installing/verifying Telegram bot dependencies..."
pip install --quiet -r telegram_bot/requirements.txt

echo "=================================================="
echo "✅ Environment Ready!"
echo "Starting FastAPI Server on http://localhost:8000 ..."
echo "=================================================="

cd backend
python3 -m uvicorn app.main:app --reload --port 8000
