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

# Extract subdomain and base domain
IFS='.' read -ra PARTS <<< "$DOMAIN"
if [ ${#PARTS[@]} -eq 3 ]; then
    SUBDOMAIN="${PARTS[0]}"
    BASE_DOMAIN="${PARTS[1]}.${PARTS[2]}"
else
    SUBDOMAIN=""
    BASE_DOMAIN="$DOMAIN"
fi

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
echo "[2/6] Installing Nginx an$BASE_DOMAIN"
echo "    3. Go to 'Advanced DNS' tab"
echo "    4. Add 'A' Record for subdomain:"
if [ -n "$SUBDOMAIN" ]; then
    echo "       Host: $SUBDOMAIN"
else
    echo "       Host: @ (or leave blank)"
fi
echo "       Type: A"
echo "       Value: $INSTANCE_IP"
echo "       TTL: 30min"
echo ""
echo "    5. Wait 5-10 minutes for DNS to propagate"
echo "    6. Test with: nslookup $DOMAIN
echo "       Host: @ (or leave blank)"
echo "       Value: $INSTANCE_IP"
echo "       TTL: 30min (or lower for testing)"
echo ""
echo "    5. Also add 'www' record (for www.your-domain.com):"
echo "       Host: www"
echo "       Value: $INSTANCE_IP"
echo "       TTL: 30min"
echo ""
echo "    6. Wait 5-10 minutes for DNS to propagate"
echo "    7. Press ENTER when DNS is updated..."
read

# Update Nginx config
echo "[4/6] Configuring Nginx..."
sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null <<EOF
server {
    listen 80;;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name 
    server_name $DOMAIN www.$DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    location /api/v1/stream {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

# Get SSL certificate
echo "[5/6] Obtaining SSL certificate from Let's Encrypt..."
sudo certbot certonly --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email $EMAIL

# Start Nginx
echo "[6/6] Starting Nginx..."
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl reload nginx

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "  Your app is live at:"
echo "    https://$DOMAIN"
echo "    https://www.$DOMAIN"
echo ""
echo "  SSL certificate auto-renews every 90 days"
echo ""
echo "  Useful commands:"
echo "    View nginx logs:    sudo tail -f /var/log/nginx/error.log"
echo "    Check SSL:          sudo certbot renew --dry-run"
echo "    Restart nginx:      sudo systemctl restart nginx"
echo ""
