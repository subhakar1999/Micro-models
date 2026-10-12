#!/usr/bin/env bash
# Deploy an EXISTING container image; this script never builds or enables GPUs.
set -euo pipefail
TASK="${1:?Usage: cloud-run.sh text|asr|tts|document IMAGE PROJECT_ID}"
IMAGE="${2:?Container image URI required}"
PROJECT_ID="${3:?Google Cloud project ID required}"
case "$TASK" in
  text) MEMORY=1Gi; EXTRA_ENV=",MICRO_TEXT_BACKEND=gguf" ;;
  asr) MEMORY=1Gi; EXTRA_ENV="" ;;
  tts) MEMORY=512Mi; EXTRA_ENV="" ;;
  document) MEMORY=512Mi; EXTRA_ENV="" ;;
  *) echo "This free-tier recipe excludes image/video GPU workers." >&2; exit 2 ;;
esac
gcloud run deploy "micro-$TASK" --project "$PROJECT_ID" --region us-central1 \
  --image "$IMAGE" --cpu 1 --memory "$MEMORY" --concurrency 1 \
  --min-instances 0 --max-instances 1 --timeout 120 --cpu-throttling \
  --no-allow-unauthenticated \
  --set-env-vars "MICRO_TASK=$TASK,MICRO_PROFILE_PATH=/app/profiles/$TASK.json,MICRO_THREADS=1$EXTRA_ENV"
