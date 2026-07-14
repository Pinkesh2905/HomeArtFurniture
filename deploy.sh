#!/bin/bash
set -e

echo "Updating system..."
sudo apt update && sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y

echo "Installing dependencies..."
sudo DEBIAN_FRONTEND=noninteractive apt install python3-pip python3-venv python3-dev nginx curl git libpq-dev postgresql-client -y

echo "Cloning repository..."
if [ -d "HomeArtFurniture" ]; then
    echo "Directory HomeArtFurniture already exists, pulling latest..."
    cd HomeArtFurniture
    git pull origin main
else
    git clone https://github.com/YOUR_USERNAME/HomeArtFurniture.git
    cd HomeArtFurniture
fi

echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "Copying .env file..."
cp /home/ubuntu/production.env /home/ubuntu/HomeArtFurniture/.env

echo "Running migrations and collectstatic..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "Configuring Gunicorn..."
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
cat << 'EOF' | sudo tee /etc/nginx/sites-available/homeartfurniture
server {
    listen 80;
    server_name YOUR_SERVER_IP_OR_DOMAIN;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /home/ubuntu/HomeArtFurniture;
    }

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

echo "Deployment complete!"
