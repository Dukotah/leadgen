#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Installing dependencies (first run only)..."
python3 -m pip install --quiet -r requirements.txt \
  || python3 -m pip install --quiet --break-system-packages -r requirements.txt
echo
echo "Starting Lead Engine (browser mode)..."
python3 app.py
