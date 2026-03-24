#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# RCB Ticket Monitor — Oracle Cloud VM deployment script
# Run this ON the VM after cloning the repo.
# Usage:  chmod +x deploy.sh && ./deploy.sh
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="$HOME/RCB_Ticket_AI_Agent"
SERVICE_NAME="rcb-monitor"

echo "▶ [1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git

echo "▶ [2/5] Setting up Python virtual environment..."
cd "$APP_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "▶ [3/5] Creating environment file..."
if [ ! -f "$APP_DIR/.env" ]; then
    read -rp "Enter TELEGRAM_BOT_TOKEN: " BOT_TOKEN
    read -rp "Enter TELEGRAM_CHAT_ID:   " CHAT_ID
    cat > "$APP_DIR/.env" <<EOF
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
EOF
    echo "   ✅ .env created"
else
    echo "   ⏩ .env already exists — skipping"
fi

echo "▶ [4/5] Installing systemd service..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=RCB Ticket Page Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python -u monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

echo "▶ [5/5] Done! Checking status..."
sleep 2
sudo systemctl status ${SERVICE_NAME} --no-pager

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ RCB Monitor is running as a service!"
echo ""
echo "  Useful commands:"
echo "    View logs:    sudo journalctl -u ${SERVICE_NAME} -f"
echo "    Stop:         sudo systemctl stop ${SERVICE_NAME}"
echo "    Restart:      sudo systemctl restart ${SERVICE_NAME}"
echo "    Status:       sudo systemctl status ${SERVICE_NAME}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
