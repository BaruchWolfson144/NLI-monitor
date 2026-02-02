#!/bin/bash

# Deployment script for NLI Monitor Cloud Function
# Usage: ./scripts/deploy.sh

set -e

# Configuration - UPDATE THESE VALUES
PROJECT_ID="${GCP_PROJECT:-your-project-id}"
REGION="${GCP_REGION:-me-west1}"
BUCKET_NAME="${BUCKET_NAME:-nli-monitor-data}"
FUNCTION_NAME="monitor-crowds"

echo "=== NLI Monitor Deployment ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Bucket: $BUCKET_NAME"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI is not installed"
    exit 1
fi

# Set project
gcloud config set project "$PROJECT_ID"

# Step 1: Create Cloud Storage bucket (if not exists)
echo ">>> Creating Cloud Storage bucket..."
gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://$BUCKET_NAME" 2>/dev/null || echo "Bucket already exists"

# Step 2: Create secrets (if not already created)
echo ">>> Setting up secrets..."
echo "Make sure you have created the following secrets in Secret Manager:"
echo "  - GOOGLE_API_KEY"
echo "  - TELEGRAM_BOT_TOKEN"
echo "  - TELEGRAM_CHAT_ID"
echo "  - PLACE_ID"
echo ""

# Step 3: Deploy Cloud Function
echo ">>> Deploying Cloud Function..."
cd "$(dirname "$0")/../functions/collector"

gcloud functions deploy "$FUNCTION_NAME" \
    --gen2 \
    --runtime=python311 \
    --region="$REGION" \
    --source=. \
    --entry-point=monitor_crowds \
    --trigger-http \
    --allow-unauthenticated \
    --memory=256MB \
    --timeout=60s \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,BUCKET_NAME=$BUCKET_NAME"

# Get the function URL
FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(serviceConfig.uri)')
echo ""
echo "Function deployed at: $FUNCTION_URL"

# Step 4: Create Cloud Scheduler job
echo ""
echo ">>> Creating Cloud Scheduler job..."

# Delete existing job if exists
gcloud scheduler jobs delete "trigger-$FUNCTION_NAME" --location="$REGION" --quiet 2>/dev/null || true

# Create new job - runs every 30 minutes during operating hours (9:00-20:00, Sun-Thu)
# Cron: minute hour day-of-month month day-of-week
# 0,30 9-19 * * 0-4 = every 30 min, 9:00-19:30, Sunday(0) to Thursday(4)
gcloud scheduler jobs create http "trigger-$FUNCTION_NAME" \
    --location="$REGION" \
    --schedule="0,30 9-19 * * 0-4" \
    --time-zone="Asia/Jerusalem" \
    --uri="$FUNCTION_URL" \
    --http-method=GET \
    --attempt-deadline=120s

# Also add Friday morning (9:00-12:30)
gcloud scheduler jobs delete "trigger-$FUNCTION_NAME-friday" --location="$REGION" --quiet 2>/dev/null || true

gcloud scheduler jobs create http "trigger-$FUNCTION_NAME-friday" \
    --location="$REGION" \
    --schedule="0,30 9-12 * * 5" \
    --time-zone="Asia/Jerusalem" \
    --uri="$FUNCTION_URL" \
    --http-method=GET \
    --attempt-deadline=120s

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Cloud Function: $FUNCTION_URL"
echo "Scheduler jobs created for:"
echo "  - Sunday-Thursday: 9:00-19:30 (every 30 min)"
echo "  - Friday: 9:00-12:30 (every 30 min)"
echo ""
echo "To test manually:"
echo "  curl $FUNCTION_URL"
echo ""
echo "To view logs:"
echo "  gcloud functions logs read $FUNCTION_NAME --region=$REGION --gen2"
