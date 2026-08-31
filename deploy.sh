#!/bin/bash
set -e

# Configuration: allow overriding via environment variables or prompt interactively
REPO_URL="${REPO_URL:-https://github.com/Pinkesh2905/HomeArtFurniture.git}"

if [ -z "$SERVER_DOMAIN" ]; then
    read -p "Enter server domain or public IP (e.g. homeartfurniture.store or 1.2.3.4): " SERVER_DOMAIN
fi

if [ -z "$SERVER_DOMAIN" ]; then
    echo "ERROR: Server domain or IP is required for Nginx configuration."
    exit 1
fi

echo "====================================================="
echo " Deploying Home Art Furniture"
echo " Repository: ${REPO_URL}"
echo " Domain:     ${SERVER_DOMAIN}"
echo "====================================================="

echo "Updating system packages..."
sudo apt update && sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y

echo "Installing dependencies..."
sudo DEBIAN_FRONTEND=noninteractive apt install python3-pip python3-venv python3-dev nginx curl git libpq-dev postgresql-client nodejs npm -y

echo "Cloning / updating repository..."
if [ -d "HomeArtFurniture" ]; then
    echo "Directory HomeArtFurniture already exists, pulling latest..."
    cd HomeArtFurniture
    git pull origin main
else
    git clone "${REPO_URL}" HomeArtFurniture
    cd HomeArtFurniture
fi

echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "Building Tailwind CSS assets..."
npm install
npm run build:css

echo "Checking production environment configuration..."
if [ -f "/home/ubuntu/production.env" ]; then
    cp /home/ubuntu/production.env /home/ubuntu/HomeArtFurniture/.env
elif [ ! -f "/home/ubuntu/HomeArtFurniture/.env" ]; then
    echo "WARNING: No .env file found. Copying production.env.example as .env template."
    cp production.env.example .env
fi

echo "Running migrations and collectstatic (Whitenoise)..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "Configuring Gunicorn daemon..."
cat << 'EOF' | sudo tee /etc/systemd/system/gunicorn.service
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/HomeArtFurniture
ExecStart=/home/ubuntu/HomeArtFurniture/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/home/ubuntu/HomeArtFurniture/homeartfurniture.sock homeartfurniture.wsgi:application

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl restart gunicorn

echo "Configuring Nginx..."
cat << EOF | sudo tee /etc/nginx/sites-available/homeartfurniture
server {
    listen 80;
    server_name ${SERVER_DOMAIN};

    location = /favicon.ico { access_log off; log_not_found off; }

    # Whitenoise handles static file caching & compression through Gunicorn
    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/HomeArtFurniture/homeartfurniture.sock;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/homeartfurniture /etc/nginx/sites-enabled
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl restart nginx

echo "Deployment complete for ${SERVER_DOMAIN}!"
