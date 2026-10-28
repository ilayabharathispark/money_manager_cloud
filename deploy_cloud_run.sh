#!/usr/bin/env bash
# ==============================================================================
# One-Click Google Cloud Run Deployment Script for Money Manager Cloud
# Configured for ZERO Idle Cost (Scale to Zero / Request-Based)
# ==============================================================================

set -e

echo "============================================================================"
echo "  MONEY MANAGER CLOUD - GOOGLE CLOUD RUN DEPLOYMENT ($0 / Request-Based)"
echo "============================================================================"

if ! command -v gcloud &> /dev/null; then
    echo "[ERROR] Google Cloud SDK (gcloud) is not installed."
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

read -p "Enter your Google Cloud Project ID: " GCP_PROJECT
if [ -z "$GCP_PROJECT" ]; then
    echo "[ERROR] Project ID cannot be empty."
    exit 1
fi

REGION="asia-south1"
SERVICE_NAME="money-manager-cloud"
BUCKET_NAME="${GCP_PROJECT}-money-data"

echo ""
echo "[1/4] Setting project configuration..."
gcloud config set project "$GCP_PROJECT"

echo ""
echo "[2/4] Enabling required APIs (Cloud Run, Artifact Registry, Cloud Storage)..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com

echo ""
echo "[3/4] Ensuring Cloud Storage Bucket exists for database persistence: ${BUCKET_NAME}..."
gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}" --uniform-bucket-level-access 2>/dev/null || true

echo ""
echo "[4/4] Deploying to Cloud Run with scale-to-zero ($0 idle cost flags)..."
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 1 \
    --concurrency 80 \
    --memory 512Mi \
    --cpu 1 \
    --set-env-vars DATA_DIR=/data \
    --add-volume name=money-data,type=cloud-storage,bucket="${BUCKET_NAME}" \
    --add-volume-mount volume=money-data,mount-path=/data

echo ""
echo "============================================================================"
echo "  DEPLOYMENT FINISHED!"
echo "  Your app scales down to 0 instances when idle (0 cost)."
echo "============================================================================"
