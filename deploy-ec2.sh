#!/bin/bash
# VECNA EC2 Deployment Script
# Run this on your EC2 instance after transferring files

set -e

echo "=========================================="
echo "  VECNA EC2 Deployment"
echo "=========================================="

# Update system
echo "[1/5] Updating system packages..."
sudo apt-get update -y

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "[2/5] Installing Docker..."
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to log out and back in for group changes."
else
    echo "[2/5] Docker already installed"
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "[3/5] Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    echo "[3/5] Docker Compose already installed"
fi

# Build and run
echo "[4/5] Building Docker image..."
sudo docker-compose build

echo "[5/5] Starting VECNA..."
sudo docker-compose up -d

echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "  VECNA is running at: http://$(curl -s ifconfig.me):5000"
echo ""
echo "  Useful commands:"
echo "    View logs:     sudo docker-compose logs -f"
echo "    Stop:          sudo docker-compose down"
echo "    Restart:       sudo docker-compose restart"
echo ""
