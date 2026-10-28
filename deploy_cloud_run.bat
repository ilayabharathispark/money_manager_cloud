@echo off
REM ============================================================================
REM One-Click Google Cloud Run Deployment Script for Money Manager Cloud
REM Configured for ZERO Idle Cost (Scale to Zero / Request-Based)
REM ============================================================================

setlocal enabledelayedexpansion

echo ============================================================================
echo   MONEY MANAGER CLOUD - GOOGLE CLOUD RUN DEPLOYMENT ($0 / Request-Based)
echo ============================================================================

REM Check if gcloud is installed
where gcloud >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Google Cloud SDK (gcloud) is not installed or not in PATH.
    echo Please install it from: https://cloud.google.com/sdk/docs/install
    pause
    exit /b 1
)

REM Set project and region defaults
set /p GCP_PROJECT="Enter your Google Cloud Project ID: "
if "%GCP_PROJECT%"=="" (
    echo [ERROR] Project ID cannot be empty.
    pause
    exit /b 1
)

set REGION=us-central1
set SERVICE_NAME=money-manager-cloud
set BUCKET_NAME=%GCP_PROJECT%-money-data

echo.
echo [1/4] Setting project configuration...
call gcloud config set project %GCP_PROJECT%

echo.
echo [2/4] Enabling required APIs (Cloud Run, Artifact Registry, Cloud Storage)...
call gcloud services enable run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com

echo.
echo [3/4] Ensuring Cloud Storage Bucket exists for database persistence: %BUCKET_NAME%...
call gcloud storage buckets create gs://%BUCKET_NAME% --location=%REGION% --uniform-bucket-level-access 2>nul

echo.
echo [4/4] Deploying to Cloud Run with scale-to-zero ($0 idle cost flags)...
call gcloud run deploy %SERVICE_NAME% ^
    --source . ^
    --region %REGION% ^
    --platform managed ^
    --allow-unauthenticated ^
    --min-instances 0 ^
    --max-instances 1 ^
    --concurrency 80 ^
    --memory 512Mi ^
    --cpu 1 ^
    --set-env-vars DATA_DIR=/data ^
    --add-volume name=money-data,type=cloud-storage,bucket=%BUCKET_NAME% ^
    --add-volume-mount volume=money-data,mount-path=/data

echo.
echo ============================================================================
echo   DEPLOYMENT FINISHED!
echo   Your app scales down to 0 instances when idle (0 cost).
echo ============================================================================
pause
