#!/usr/bin/env bash
# RepoScan Pro - Installation Script
set -euo pipefail

APP_DIR="/opt/reposcan"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "═══════════════════════════════════════════"
echo "  RepoScan Pro - Install"
echo "═══════════════════════════════════════════"

# Copy project files
echo "Copying project files to $APP_DIR..."
sudo mkdir -p "$APP_DIR"
sudo rsync -av --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
    "$PROJECT_DIR/" "$APP_DIR/"
sudo chown -R "$USER:$USER" "$APP_DIR"

# Setup environment
cd "$APP_DIR"
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate a random secret key
    SECRET=$(openssl rand -hex 32)
    sed -i "s/change-this-to-a-random-secret-key/$SECRET/" .env
    echo "Generated random SECRET_KEY in .env"
    echo "IMPORTANT: Review and customize .env before starting"
fi

# Build containers
echo "Building Docker images..."
docker compose build

# Install systemd services
echo "Installing systemd services..."
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable reposcan.service

echo ""
echo "═══════════════════════════════════════════"
echo "  Installation complete!"
echo ""
echo "  Start:   sudo systemctl start reposcan"
echo "  Status:  sudo systemctl status reposcan"
echo "  Logs:    docker compose logs -f"
echo "  UI:      http://localhost"
echo "═══════════════════════════════════════════"
