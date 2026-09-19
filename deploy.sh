#!/bin/bash
set -e

# ==============================================================================
# GridKnowledge RAG — Production EC2 Deployment & Update Script
# ==============================================================================

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "====================================================="
echo "   Starting GridKnowledge RAG Production Deployment  "
echo "   Timestamp: $(date -u)"
echo "   Directory: $APP_DIR"
echo "====================================================="

# 1. Pull latest code from repository
echo "[1/4] Pulling latest code changes from Git..."
if [ -d ".git" ]; then
    git pull origin main
else
    echo "Notice: Not a git repo root, skipping git pull."
fi

# 2. Rebuild and restart containers
echo "[2/4] Building and updating Docker containers via Compose..."
docker compose down
docker compose up -d --build

# 3. Wait for container to be healthy
echo "[3/4] Validating application health..."
sleep 4

MAX_RETRIES=12
COUNT=0
HEALTHY=false

while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f http://localhost:8000/api/health > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    echo "Waiting for health endpoint... (Attempt $((COUNT+1))/$MAX_RETRIES)"
    sleep 3
    COUNT=$((COUNT+1))
done

if [ "$HEALTHY" = true ]; then
    echo "Healthcheck PASSED! Application is running normally."
else
    echo "ERROR: Application health check failed or timed out."
    docker compose logs --tail=60
    exit 1
fi

# 4. Clean up dangling images to preserve disk space
echo "[4/4] Cleaning unused Docker images..."
docker image prune -f

echo "====================================================="
echo "   Deployment completed successfully!               "
echo "====================================================="
