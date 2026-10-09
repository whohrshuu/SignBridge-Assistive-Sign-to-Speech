#!/usr/bin/env sh
cd "$(dirname "$0")"
echo "Open http://localhost:8000"
exec python3 server.py
