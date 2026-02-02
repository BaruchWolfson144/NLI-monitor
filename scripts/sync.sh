#!/bin/bash
# Sync readings from Cloud Storage to local SQLite database
# Usage: ./scripts/sync.sh [--status]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/legacy_credentials/baruch1448@gmail.com/adc.json
export GOOGLE_CLOUD_PROJECT=megilot-480213

# Run sync
"$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/local/sync.py" "$@"
