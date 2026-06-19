#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: sudo $0 <deploy_user> <repo_url> [branch]"
  exit 1
fi

DEPLOY_USER="$1"
REPO_URL="$2"
BRANCH="${3:-main}"
REPO_DIR="/opt/dns"
VENV_DIR="$REPO_DIR/venv"

echo "==> Installing system packages"
apt update
apt install -y git python3.11-venv python3-pip curl build-essential \
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 \
  libxdamage1 libxrandr2 libgbm-dev libasound2 libgtk-3-0 libxss1 fonts-liberation \
  libcups2 libdrm2 libexpat1 libxrender1

echo "==> Cloning or updating repository into $REPO_DIR"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch --all
  git -C "$REPO_DIR" checkout "$BRANCH"
  git -C "$REPO_DIR" pull origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
fi

echo "==> Setting ownership to $DEPLOY_USER"
chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$REPO_DIR"

echo "==> Creating virtualenv and installing Python dependencies"
sudo -u "$DEPLOY_USER" bash -lc "python3.11 -m venv $VENV_DIR"
sudo -u "$DEPLOY_USER" bash -lc "source $VENV_DIR/bin/activate && pip install --upgrade pip && pip install -r $REPO_DIR/requirements.txt"

echo "==> Installing Playwright browsers (chromium)"
sudo -u "$DEPLOY_USER" bash -lc "source $VENV_DIR/bin/activate && python -m playwright install chromium"

echo "==> Preparing log directory"
mkdir -p /var/log/dns
chown "$DEPLOY_USER":"$DEPLOY_USER" /var/log/dns

SERVICE_TEMPLATE="$REPO_DIR/deploy/dns.service.template"
if [ ! -f "$SERVICE_TEMPLATE" ]; then
  echo "Service template not found at $SERVICE_TEMPLATE"
  exit 1
fi

echo "==> Installing systemd service"
sed "s|__REPLACE_USER__|$DEPLOY_USER|g" "$SERVICE_TEMPLATE" > /etc/systemd/system/dns.service

systemctl daemon-reload
systemctl enable dns
systemctl restart dns

echo "==> Deployment complete. Check service status:"
echo "  sudo systemctl status dns --no-pager"
