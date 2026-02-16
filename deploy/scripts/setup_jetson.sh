#!/usr/bin/env bash
# RepoScan Pro - Jetson Orin Nano Super Setup Script
set -euo pipefail

echo "═══════════════════════════════════════════"
echo "  RepoScan Pro - Jetson Setup"
echo "═══════════════════════════════════════════"

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "WARNING: This does not appear to be a Jetson device."
    echo "Some hardware-specific features may not work."
fi

# Set Jetson to 15W performance mode
echo "Setting Jetson power mode to 15W..."
if command -v nvpmodel &> /dev/null; then
    sudo nvpmodel -m 0
    sudo jetson_clocks
    echo "Power mode set to MAXN (15W)"
else
    echo "nvpmodel not found, skipping power configuration"
fi

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "Docker installed. You may need to log out and back in."
fi

# Install Docker Compose plugin
if ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
fi

# Install NVIDIA Container Toolkit
if ! dpkg -l | grep -q nvidia-container-toolkit; then
    echo "Installing NVIDIA Container Toolkit..."
    distribution=$(. /etc/os-release; echo "$ID$VERSION_ID")
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L "https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list" | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
fi

# Create application directory
APP_DIR="/opt/reposcan"
echo "Setting up application directory at $APP_DIR..."
sudo mkdir -p "$APP_DIR"
sudo chown "$USER:$USER" "$APP_DIR"

# Create data directories
sudo mkdir -p /data/captures
sudo chown "$USER:$USER" /data/captures

echo ""
echo "═══════════════════════════════════════════"
echo "  Jetson setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Copy project files to $APP_DIR"
echo "  2. cp .env.example .env && edit .env"
echo "  3. docker compose up -d"
echo "═══════════════════════════════════════════"
