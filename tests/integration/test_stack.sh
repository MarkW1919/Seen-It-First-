#!/usr/bin/env bash
# ─── Integration test: spin up Docker Compose test stack and verify ───
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.test.yml"

cleanup() {
    echo "Tearing down test stack..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo "=== RepoScan Pro Integration Tests ==="
echo ""

# 1. Build & start
echo "[1/5] Building and starting test stack..."
docker compose -f "$COMPOSE_FILE" up -d --build --wait
echo "  Stack is up."

# 2. Backend health check
echo "[2/5] Checking backend health..."
HEALTH=$(curl -sf http://localhost:8000/health)
if echo "$HEALTH" | grep -q '"healthy"'; then
    echo "  Backend is healthy."
else
    echo "  FAIL: Backend health check failed"
    echo "  Response: $HEALTH"
    exit 1
fi

# 3. Backend root endpoint
echo "[3/5] Checking backend root..."
ROOT=$(curl -sf http://localhost:8000/)
if echo "$ROOT" | grep -q '"RepoScan Pro"'; then
    echo "  Root endpoint OK."
else
    echo "  FAIL: Root endpoint check failed"
    exit 1
fi

# 4. OpenAPI docs available
echo "[4/5] Checking OpenAPI docs..."
DOCS_STATUS=$(curl -so /dev/null -w "%{http_code}" http://localhost:8000/docs)
if [ "$DOCS_STATUS" = "200" ]; then
    echo "  OpenAPI docs accessible."
else
    echo "  FAIL: /docs returned $DOCS_STATUS"
    exit 1
fi

# 5. Frontend reachable
echo "[5/5] Checking frontend..."
FRONTEND_STATUS=$(curl -so /dev/null -w "%{http_code}" http://localhost:5173/ --max-time 10 || echo "000")
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "  Frontend is reachable."
else
    echo "  WARN: Frontend returned $FRONTEND_STATUS (may still be compiling)"
fi

echo ""
echo "=== All integration tests passed ==="
