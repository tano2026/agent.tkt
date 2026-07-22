#!/bin/bash
# Deploy ABTrip backend to VPS — with venv
set -e

VPS_USER="ubuntu"
VPS_HOST="100.64.173.75"
REMOTE_DIR="/opt/abtrip-backend"
SERVICE_NAME="abtrip-backend"
BACKEND_DIR="/c/Users/Nguyen Ngoc Tan/agent.tkt/backend"

echo "=== 1. Stop old service ==="
ssh $VPS_USER@$VPS_HOST "sudo systemctl stop $SERVICE_NAME 2>/dev/null || true"

echo "=== 2. Create target dir ==="
ssh $VPS_USER@$VPS_HOST "sudo mkdir -p $REMOTE_DIR && sudo chown $VPS_USER:$VPS_USER $REMOTE_DIR"

echo "=== 3. Tar & scp ==="
cd "$BACKEND_DIR"
tar czf /tmp/abtrip-deploy.tar.gz \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.venv' \
  --exclude='deploy' \
  --exclude='.env' \
  --exclude='.rsyncignore' \
  --exclude='static' \
  .
scp /tmp/abtrip-deploy.tar.gz $VPS_USER@$VPS_HOST:/tmp/
ssh $VPS_USER@$VPS_HOST "cd $REMOTE_DIR && tar xzf /tmp/abtrip-deploy.tar.gz && rm /tmp/abtrip-deploy.tar.gz"

echo "=== 4. Setup venv + deps ==="
ssh $VPS_USER@$VPS_HOST "cd $REMOTE_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -q && pip install uvicorn fastapi pydantic pydantic-settings httpx python-dotenv -q"

echo "=== 5. Deploy .env ==="
scp "$BACKEND_DIR/.env.production" $VPS_USER@$VPS_HOST:$REMOTE_DIR/.env
ssh $VPS_USER@$VPS_HOST "chmod 600 $REMOTE_DIR/.env"

# Find venv python path
VENV_PYTHON="$REMOTE_DIR/.venv/bin/python"

echo "=== 6. Systemd service ==="
ssh $VPS_USER@$VPS_HOST "sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null" << SVC
[Unit]
Description=ABTrip Backend API
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$VPS_USER
WorkingDirectory=$REMOTE_DIR
EnvironmentFile=$REMOTE_DIR/.env
ExecStart=$VENV_PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8138 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVC

echo "=== 7. Enable & start ==="
ssh $VPS_USER@$VPS_HOST "sudo systemctl daemon-reload && sudo systemctl enable $SERVICE_NAME && sudo systemctl start $SERVICE_NAME"

echo "=== 8. Verify ==="
sleep 4
ssh $VPS_USER@$VPS_HOST "sudo systemctl status $SERVICE_NAME --no-pager | head -20"
echo "---"
ssh $VPS_USER@$VPS_HOST "curl -s http://localhost:8138/api/health"

echo ""
echo "=== DEPLOY DONE ==="
