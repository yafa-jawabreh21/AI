#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
$PY -m pip install -r requirements.txt --quiet
exec $PY -m uvicorn app:app --host 0.0.0.0 --port 8010
