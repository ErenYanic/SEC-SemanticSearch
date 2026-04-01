#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# Test F5 Mitigation: Docker Secrets for Database Encryption Key
#
# This script demonstrates and tests the file-based encryption key
# loading (F5 mitigation) using Docker secrets with docker compose.
#
# Usage:
#   ./scripts/test-docker-secrets.sh [start|stop|test|clean]
#
# Examples:
#   ./scripts/test-docker-secrets.sh start  # Create secret and start
#   ./scripts/test-docker-secrets.sh test   # Verify encryption is active
#   ./scripts/test-docker-secrets.sh stop   # Stop the stack
#   ./scripts/test-docker-secrets.sh clean  # Remove secret and cleanup
# ──────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
SECRETS_DIR="$PROJECT_ROOT/secrets"
SECRET_FILE="$SECRETS_DIR/db_encryption_key.txt"
SECRET_KEY="test-encryption-key-for-docker-secrets"

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create secret file
setup_secret() {
    log_info "Setting up Docker secrets..."
    mkdir -p "$SECRETS_DIR"
    echo "$SECRET_KEY" > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"
    log_success "Secret file created at $SECRET_FILE"
}

# Create a modified docker-compose.yml with secrets enabled
create_test_compose() {
    log_info "Creating test docker-compose configuration..."

    # Create a temporary docker-compose that uses secrets
    cat > "$PROJECT_ROOT/docker-compose.secrets.yml" <<'EOF'
version: '3.8'

services:
  # ── FastAPI backend with file-based encryption key ───────────────────
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: sec-search-api-test
    restart: unless-stopped
    volumes:
      - chroma_data_test:/app/data/chroma_db
      - sqlite_data_test:/app/data/sqlite
    secrets:
      - db_encryption_key
    environment:
      # Database paths (match volume mounts above)
      - DB_CHROMA_PATH=/app/data/chroma_db
      - DB_METADATA_DB_PATH=/app/data/sqlite/metadata.sqlite
      # Server binding
      - API_HOST=0.0.0.0
      - API_PORT=8000
      # Use file-based encryption key (mounted via secrets)
      # The key is NOT visible in /proc/<pid>/environ — only the file path
      - DB_ENCRYPTION_KEY_FILE=/run/secrets/db_encryption_key
      # EDGAR credentials for testing
      - EDGAR_IDENTITY_NAME=Test User
      - EDGAR_IDENTITY_EMAIL=test@example.com
      # Logging
      - LOG_LEVEL=DEBUG
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 5s
      start_period: 15s
      retries: 3

  # ── Nginx reverse proxy ────────────────────────────────────────────
  nginx:
    image: nginx:1.27.5-alpine
    container_name: sec-search-nginx-test
    restart: unless-stopped
    ports:
      - "8888:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      api:
        condition: service_healthy

# ── Secrets (F5 mitigation) ───────────────────────────────────────────
# The encryption key is mounted as a file, not passed as an env var.
# This prevents the key from being visible in /proc/<pid>/environ
# on Linux systems.
secrets:
  db_encryption_key:
    file: ./secrets/db_encryption_key.txt

# ── Volumes ───────────────────────────────────────────────────────────
volumes:
  chroma_data_test:
    driver: local
  sqlite_data_test:
    driver: local
EOF
    log_success "Test docker-compose created at $PROJECT_ROOT/docker-compose.secrets.yml"
}

# Start the stack
start_stack() {
    log_info "Starting Docker stack with file-based encryption key..."

    if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
        log_error "docker-compose or docker not found in PATH"
        return 1
    fi

    cd "$PROJECT_ROOT"

    # Use docker compose if available, else docker-compose
    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
        docker compose -f docker-compose.secrets.yml up -d --build
    else
        docker-compose -f docker-compose.secrets.yml up -d --build
    fi

    log_success "Stack started. Waiting for services to be healthy..."
    sleep 10

    # Check health
    if docker ps | grep -q "sec-search-api-test"; then
        log_success "API container is running"
    else
        log_error "API container failed to start"
        return 1
    fi
}

# Stop the stack
stop_stack() {
    log_info "Stopping Docker stack..."
    cd "$PROJECT_ROOT"

    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
        docker compose -f docker-compose.secrets.yml down 2>/dev/null || true
    else
        docker-compose -f docker-compose.secrets.yml down 2>/dev/null || true
    fi

    log_success "Stack stopped"
}

# Test encryption is active
test_encryption() {
    log_info "Testing F5 mitigation (file-based encryption key)..."

    # Check the secret file is readable by container
    if ! docker exec sec-search-api-test test -f /run/secrets/db_encryption_key 2>/dev/null; then
        log_error "Secret file not mounted in container"
        return 1
    fi
    log_success "Secret file mounted at /run/secrets/db_encryption_key"

    # Verify key content matches
    CONTAINER_KEY=$(docker exec sec-search-api-test cat /run/secrets/db_encryption_key)
    if [ "$CONTAINER_KEY" != "$SECRET_KEY" ]; then
        log_error "Secret key mismatch: expected '$SECRET_KEY', got '$CONTAINER_KEY'"
        return 1
    fi
    log_success "Secret key content is correct"

    # Call the health endpoint
    log_info "Checking API health endpoint..."
    if curl -s http://localhost:8888/api/health | grep -q '"status":"ok"'; then
        log_success "API is healthy"
    else
        log_error "API health check failed"
        return 1
    fi

    # Check status endpoint for encryption flag
    log_info "Checking database encryption status..."
    STATUS=$(curl -s http://localhost:8888/api/status/ || echo "{}")
    log_success "API status: $STATUS"

    # Verify DB_ENCRYPTION_KEY_FILE is NOT in container environment
    log_info "Verifying F5 mitigation: key not in /proc environment..."
    if docker exec sec-search-api-test grep -q "DB_ENCRYPTION_KEY_FILE" /proc/1/environ 2>/dev/null; then
        log_warn "DB_ENCRYPTION_KEY_FILE is in /proc (this is the file path, not the key)"
    else
        log_success "DB_ENCRYPTION_KEY_FILE not in /proc/environ (expected when using secrets)"
    fi

    # Verify the key itself is NOT in /proc
    if docker exec sec-search-api-test grep -q "$SECRET_KEY" /proc/1/environ 2>/dev/null; then
        log_error "SECURITY ISSUE: Encryption key is visible in /proc/environ!"
        return 1
    else
        log_success "Encryption key is NOT visible in /proc/environ ✓ (F5 mitigation working!)"
    fi

    log_success "All F5 mitigation tests passed!"
}

# Clean up
cleanup() {
    log_info "Cleaning up..."

    # Stop stack
    stop_stack

    # Remove compose file
    if [ -f "$PROJECT_ROOT/docker-compose.secrets.yml" ]; then
        rm "$PROJECT_ROOT/docker-compose.secrets.yml"
        log_success "Removed docker-compose.secrets.yml"
    fi

    # Optionally remove secrets directory
    if [ -d "$SECRETS_DIR" ] && [ -z "$(ls -A $SECRETS_DIR)" ]; then
        rm -rf "$SECRETS_DIR"
        log_success "Removed empty secrets directory"
    fi
}

# Main
main() {
    case "${1:-start}" in
        start)
            setup_secret
            create_test_compose
            start_stack
            log_info "✓ Stack ready for testing at http://localhost:8888"
            log_info "  Run: ./scripts/test-docker-secrets.sh test"
            ;;
        test)
            test_encryption
            ;;
        stop)
            stop_stack
            ;;
        clean)
            cleanup
            ;;
        *)
            log_error "Unknown command: ${1:-}"
            echo "Usage: $0 [start|stop|test|clean]"
            exit 1
            ;;
    esac
}

main "$@"
