#!/bin/bash
# VECNA EC2 Setup with Namecheap Domain & SSL
# Run this on your EC2 instance

set -e

DOMAIN="$1"
EMAIL="$2"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: ./setup-domain.sh vecna.saffronzen.me your-email@example.com"
    exit 1
fi

# Simple subdomain extraction
SUBDOMAIN=$(echo "$DOMAIN" | cut -d. -f1)
BASE_DOMAIN=$(echo "$DOMAIN" | cut -d. -f2-)

echo "=========================================="
echo "  VECNA Domain & SSL Setup"
echo "=========================================="
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Update system
echo "[1/6] Updating system..."
sudo apt-get update -y

# Install Nginx and Certbot
echo "[2/6] Installing Nginx and Certbot..."
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Get EC2 public IP
INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "[3/6] EC2 Public IP: $INSTANCE_IP"
echo ""
echo "    ACTION REQUIRED: Update your Namecheap DNS settings"
echo "    =================================================="
echo "    1. Go to: https://www.namecheap.com/domains/mydomains/"
echo "    2. Click 'Manage' on $BASE_DOMAIN"
echo "    3. Go to 'Advanced DNS' tab"
echo "    4. Add 'A' Record for subdomain:"
echo "       Host: $SUBDOMAIN"
echo "       Type: A"
echo "       Value: $INSTANCE_IP"
echo "       TTL: 30min"
echo ""
echo "    5. Wait 5-10 minutes for DNS to propagate"
echo "    6. Test with: nslookup $DOMAIN"
echo "    7. Press ENTER when DNS is updated..."
read

# Update Nginx config (HTTP only first for certificate)
echo "[4/6] Configuring Nginx (HTTP for cert validation)..."
sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
echo "[5/6] Obtaining SSL certificate from Let's Encrypt..."
sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL --redirect

# Start Nginx
echo "[6/6] Restarting Nginx..."
sudo systemctl restart nginx

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "  Your app is live at:"
echo "    https://$DOMAIN"
echo ""
echo "  SSL certificate auto-renews every 90 days"
echo ""
echo "  Useful commands:"
echo "    View nginx logs:    sudo tail -f /var/log/nginx/error.log"
echo "    Check SSL:          sudo certbot renew --dry-run"
echo "    Restart nginx:      sudo systemctl restart nginx"
echo ""
