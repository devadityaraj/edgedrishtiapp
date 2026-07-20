#!/bin/bash
set -e

echo "======================================================================"
echo "               EDGE DRISHTI SECURITY PLATFORM LAUNCHER                "
echo "======================================================================"
echo ""

echo "[INFO] Cleaning up previous session..."
pkill -f "backend/run.py" 2>/dev/null || true
pkill -f "uvicorn"        2>/dev/null || true
pkill -f "next build"     2>/dev/null || true 
pkill -f "turbopack"      2>/dev/null || true  
sleep 1  
echo "[OK] Session clean."
echo ""

if [ ! -f "venv/bin/activate" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "[INFO] Installing Python dependencies..."
    REQ=""; [ -f "backend/requirements.txt" ] && REQ="backend/requirements.txt"
    [ -f "requirements.txt" ] && REQ="requirements.txt"
    [ -z "$REQ" ] && { echo "[ERROR] requirements.txt not found!"; exit 1; }
    pip install -r "$REQ"
else
    echo "[OK] Activating virtual environment..."
    source venv/bin/activate
fi
echo ""


echo "[INFO] Clearing previous build artifacts (/out and /.next)..."
rm -rf out .next

echo "[INFO] Building Next.js frontend..."
npm run build
echo "[OK] Frontend built."
echo ""

echo "[INFO] Starting EDGE Drishti backend server..."
python3 backend/run.py
