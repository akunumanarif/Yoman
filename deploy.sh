#!/bin/bash
set -e

# === CONFIG ===
REPO_URL="https://github.com/akunumanarif/Yoman.git"
DEPLOY_DIR="/root/Yoman"
SUBDOMAIN="yoman.numanarif.dev"
VAST_API_KEY="${1:?Usage: ./deploy.sh <VAST_API_KEY> [nginx_network]}"
NGINX_NETWORK="${2:-}"

echo "=== Yoman Deploy ==="

# Step 1: Clone repo
if [ -d "$DEPLOY_DIR" ]; then
    echo "Directory exists, pulling latest..."
    cd "$DEPLOY_DIR" && git pull
else
    echo "Cloning repo..."
    git clone "$REPO_URL" "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi

# Step 2: Auto-detect nginx network if not provided
if [ -z "$NGINX_NETWORK" ]; then
    NGINX_NETWORK=$(docker inspect $(docker ps -q --filter "ancestor=nginx" --filter "ancestor=nginx:1.27-alpine" | head -1) --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null || echo "")
    if [ -z "$NGINX_NETWORK" ]; then
        # Fallback: find network with nginx container
        NGINX_NETWORK=$(docker network ls --format '{{.Name}}' | grep -i "youtube\|proxy\|nginx" | head -1)
    fi
    if [ -z "$NGINX_NETWORK" ]; then
        echo "ERROR: Could not auto-detect nginx network. Pass it as 2nd argument."
        echo "Run: docker network ls"
        exit 1
    fi
fi
echo "Using nginx network: $NGINX_NETWORK"

# Step 3: Create .env
cat > "$DEPLOY_DIR/.env" << EOF
VAST_API_KEY=$VAST_API_KEY
UPLOAD_DIR=/app/uploads
OUTPUT_DIR=/app/outputs
DB_PATH=/app/data/yoman.db
GPU_MIN_VRAM=24
GPU_MAX_BID_PRICE=0.30
GPU_PREFERRED_MODELS=RTX_4090,A100,H100
VAST_DOCKER_IMAGE=pytorch/pytorch:2.4.0-cuda12.4-cudnn9-devel
WORKER_POLL_INTERVAL=10
MAX_RETRIES=3
NEXT_PUBLIC_API_URL=/api
EOF
echo ".env created"

# Step 4: Update docker-compose network name
sed -i "s/proxy_network/$NGINX_NETWORK/g" "$DEPLOY_DIR/docker-compose.yml"
echo "docker-compose.yml updated with network: $NGINX_NETWORK"

# Step 5: Add nginx config for subdomain
NGINX_CONTAINER=$(docker ps --format '{{.Names}}' | grep -i nginx | head -1)
if [ -z "$NGINX_CONTAINER" ]; then
    echo "ERROR: No nginx container found"
    exit 1
fi
echo "Found nginx container: $NGINX_CONTAINER"

# Write nginx config
docker exec "$NGINX_CONTAINER" sh -c "cat > /etc/nginx/conf.d/${SUBDOMAIN}.conf << 'NGINX_EOF'
server {
    listen 80;
    server_name ${SUBDOMAIN};

    client_max_body_size 500M;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;

    location / {
        proxy_pass http://yoman-frontend:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /api/ {
        proxy_pass http://yoman-backend:8000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX_EOF"
echo "Nginx config added for $SUBDOMAIN"

# Step 6: Build and run
cd "$DEPLOY_DIR"
docker compose up -d --build
echo "Containers started"

# Step 7: Reload nginx
docker exec "$NGINX_CONTAINER" nginx -s reload
echo "Nginx reloaded"

echo ""
echo "=== Deploy complete ==="
echo "App is live at: http://$SUBDOMAIN"
echo ""
echo "To enable SSL, run certbot in your certbot container."
