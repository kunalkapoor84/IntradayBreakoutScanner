# Deploying to Google Cloud Free Tier

Step-by-step guide to deploy the Intraday Breakout Scanner on Google Cloud Platform's free tier using a Compute Engine VM.

## Overview

GCP free tier gives you one `f1-micro` VM (0.2 vCPU, 0.6 GB RAM, 30 GB disk) — enough to run the scanner 24×7. We'll provision an Ubuntu VM, install the scanner as a systemd service, and optionally set up HTTPS with a domain.

---

## Prerequisites

- A Google Cloud Platform account (free tier eligible)
- Dhan API credentials
- Telegram bot token (optional)
- A domain name (optional, for HTTPS)

---

## Step 1: Create a GCP Account

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Accept the ToS and set up billing (credit card required for verification — you get $300 free credit + always free tier)
4. Make sure the free trial is activated

---

## Step 2: Create a Compute Engine VM

### 2.1 Enable Compute Engine API

1. Go to **APIs & Services** → **Library**
2. Search for "Compute Engine API" and enable it

### 2.2 Create the VM Instance

1. Go to **Compute Engine** → **VM Instances**
2. Click **Create Instance**

| Field | Value |
|-------|-------|
| Name | `scanner-vm` |
| Region | `us-west1` (Oregon), `us-central1` (Iowa), or `us-east1` (South Carolina) — free tier regions |
| Zone | Any within the region |
| Machine type | **f1-micro** (0.2 vCPU, 0.6 GB) — `g1-small` also works for slightly more resources |
| Boot disk | Click **Change** → **Ubuntu 22.04 LTS** → **30 GB standard persistent disk** |
| Firewall | ✅ Allow HTTP traffic, ✅ Allow HTTPS traffic |
| Advanced options → Networking | Leave defaults (default VPC network with external IP) |

3. Click **Create**

### 2.3 Reserve a Static External IP (Optional but Recommended)

1. Go to **VPC Network** → **External IP Addresses**
2. Click **Reserve Static Address**
3. Name it `scanner-static-ip`, attach it to `scanner-vm`
4. This prevents the IP from changing on every restart

---

## Step 3: Configure Firewall Rules

### 3.1 Verify Default Firewall

1. Go to **VPC Network** → **Firewall**
2. Ensure these rules exist (they are created by default when you enabled HTTP/HTTPS):
   - `default-allow-http` — TCP :80 (for Nginx/HTTPS redirect)
   - `default-allow-https` — TCP :443 (for HTTPS)
   - `default-allow-ssh` — TCP :22 (for SSH)

### 3.2 Add Scanner Dashboard Port (Optional)

If you want direct access to the FastAPI dashboard without Nginx:

1. Click **Create Firewall Rule**
2. Name: `allow-scanner-dashboard`
3. Target tags: `scanner`
4. Source IPv4 ranges: `0.0.0.0/0`
5. Protocols and ports: `tcp:8000`

Then edit your VM → **Network tags** → Add `scanner`

> **Security note**: Exposing port 8000 directly is not recommended. Use the Nginx reverse proxy (covered below) instead.

---

## Step 4: SSH Into the VM

### Option A: Browser SSH

Click the **SSH** button next to your VM in the Compute Engine dashboard.

### Option B: gcloud CLI

```bash
gcloud compute ssh scanner-vm --zone=us-west1-b
```

### Option C: External SSH Client

```bash
# Add your SSH public key to the VM metadata first
ssh -i ~/.ssh/google_compute_engine ubuntu@<EXTERNAL_IP>
```

---

## Step 5: Install Dependencies

Run these commands on the VM:

```bash
# Update system
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# Install Python and build tools
sudo apt-get install -y -qq python3 python3-pip python3-venv git curl wget sqlite3

# Install Nginx for reverse proxy (optional)
sudo apt-get install -y -qq nginx

# Install fail2ban for SSH protection
sudo apt-get install -y -qq fail2ban

# Clean up
sudo apt-get autoremove -y -qq
```

---

## Step 6: Clone the Repository

```bash
cd /opt
sudo mkdir -p scanner
sudo chown ubuntu:ubuntu scanner
cd scanner

git clone https://github.com/yourusername/intraday-breakout-scanner.git .
```

---

## Step 7: Set Up Python Virtual Environment

```bash
cd /opt/scanner
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

---

## Step 8: Configure Environment

```bash
cd /opt/scanner
cp .env.example .env
nano .env
```

Fill in at minimum:

```ini
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DATABASE_PATH=/opt/scanner/data/scanner.db
LOG_DIR=/opt/scanner/logs
REPORT_DIR=/opt/scanner/reports
CHART_DIR=/opt/scanner/charts
OUTPUT_DIR=/opt/scanner/output
SCAN_INTERVAL_MINUTES=15
```

---

## Step 9: Create Directories

```bash
cd /opt/scanner
mkdir -p logs reports charts output/reports output/charts data
```

---

## Step 10: Initialize the Database

```bash
cd /opt/scanner
source venv/bin/activate
python -c "from app.database.db import Database; Database()"
echo "Database initialized"
```

---

## Step 11: Test the Scanner

```bash
cd /opt/scanner
source venv/bin/activate
python main.py
```

This will scan all NSE F&O stocks and generate reports. If successful, you'll see the console output with stock scores.

---

## Step 12: Set Up systemd Service

### 12.1 Create the Service File

```bash
sudo nano /etc/systemd/system/scanner.service
```

Paste the following:

```ini
[Unit]
Description=Intraday Breakout Scanner Service
Documentation=https://github.com/yourusername/intraday-breakout-scanner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/scanner
Environment=PYTHONPATH=/opt/scanner
Environment=TZ=Asia/Kolkata
ExecStart=/opt/scanner/venv/bin/python /opt/scanner/main.py --mode schedule
ExecStop=/bin/kill -SIGTERM $MAINPID
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5
TimeoutStopSec=30
StandardOutput=append:/opt/scanner/logs/scanner.log
StandardError=append:/opt/scanner/logs/error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full
ReadWritePaths=/opt/scanner/data /opt/scanner/logs /opt/scanner/reports /opt/scanner/charts /opt/scanner/output

[Install]
WantedBy=multi-user.target
```

### 12.2 Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable scanner
sudo systemctl start scanner
```

### 12.3 Verify the Service

```bash
sudo systemctl status scanner
# Should show "active (running)"

# View logs
tail -f /opt/scanner/logs/scanner.log
```

---

## Step 13: Set Up the Dashboard (FastAPI + Nginx)

### 13.1 Configure Nginx as a Reverse Proxy

Create the Nginx config:

```bash
sudo nano /etc/nginx/sites-available/scanner
```

```
server {
    listen 80;
    server_name _;  # Replace with your domain if you have one

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/scanner/reports/;
    }

    location /charts/ {
        alias /opt/scanner/charts/;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/scanner /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 13.2 Set Up HTTPS with Let's Encrypt (Optional, requires a domain)

```bash
sudo apt-get install -y -qq certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
# Follow the interactive prompts
```

### 13.3 Create a systemd Service for the Dashboard

```bash
sudo nano /etc/systemd/system/scanner-dashboard.service
```

```ini
[Unit]
Description=Scanner FastAPI Dashboard
After=network.target scanner.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/scanner
Environment=PYTHONPATH=/opt/scanner
ExecStart=/opt/scanner/venv/bin/uvicorn app.dashboard.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/opt/scanner/logs/dashboard.log
StandardError=append:/opt/scanner/logs/dashboard.log

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable scanner-dashboard
sudo systemctl start scanner-dashboard
```

---

## Step 14: Set Up Firewall (UFW)

```bash
sudo apt-get install -y -qq ufw

# Allow only what's needed
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# If you skipped Nginx and want direct dashboard access:
# sudo ufw allow 8000/tcp

sudo ufw --force enable
sudo ufw status verbose
```

---

## Step 15: Set Up Fail2Ban

```bash
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
sudo fail2ban-client status
```

---

## Step 16: Set Up Automatic Backups

### 16.1 Create the Backup Cron Job

```bash
sudo crontab -e
```

Add:

```cron
# Daily backup at 4:00 AM
0 4 * * * /opt/scanner/deployment/backup.sh /opt/scanner /opt/scanner-backups 30 >> /opt/scanner/logs/backup.log 2>&1
```

### 16.2 Test the Backup

```bash
bash /opt/scanner/deployment/backup.sh /opt/scanner /tmp/test-backup 30
ls -la /tmp/test-backup/
rm -rf /tmp/test-backup
```

---

## Step 17: Verify Everything

### 17.1 Service Status

```bash
sudo systemctl status scanner
sudo systemctl status scanner-dashboard
```

### 17.2 Health Check

```bash
curl -sf http://localhost:8000/health
# Expected: {"status":"healthy","checks":{...}}
```

### 17.3 Dashboard (via Nginx)

Open `http://<EXTERNAL_IP>/dashboard` in a browser.

### 17.4 Run the Health Check Script

```bash
bash /opt/scanner/deployment/health_check.sh /opt/scanner
```

---

## Step 18: Test Auto-Recovery

### 18.1 Simulate a Crash

```bash
# Find the scanner process
ps aux | grep main.py

# Kill it
sudo pkill -f "python.*main.py"

# Wait 10 seconds, then check if it restarted
sleep 10
sudo systemctl status scanner
```

### 18.2 Simulate a Reboot

```bash
sudo reboot
# Wait 60 seconds, then SSH back in
sudo systemctl status scanner
# Should show "active (running)" and uptime matching the reboot time
```

---

## Step 19: Cost Confirmation

These resources should remain within GCP's **Always Free** tier:

| Resource | Free Tier Limit | Our Usage |
|----------|----------------|-----------|
| Compute Engine | 1 f1-micro VM/month (us-west1, us-central1, us-east1) | ✅ 1 f1-micro |
| Persistent Disk | 30 GB/month | ✅ 30 GB standard |
| Networking | 1 GB/month egress | ✅ Under 1 GB |
| HTTP/HTTPS Load Balancing | Not used | ✅ Not needed |

> **Warning**: Running the VM in a **non-free tier region** (e.g., us-east4) will incur costs even on the free trial. Stick to `us-west1`, `us-central1`, or `us-east1`.

---

## Step 20: Set Up SSH Key Authentication (Optional but Recommended)

### 20.1 Generate a Key Pair

```bash
# On your local machine
ssh-keygen -t ed25519 -f ~/.ssh/gcp-scanner -C "scanner-deploy"
```

### 20.2 Add the Public Key to GCP

1. Go to **Compute Engine** → **Settings** → **Metadata**
2. Go to the **SSH Keys** tab
3. Click **Add SSH Key**
4. Paste the contents of `~/.ssh/gcp-scanner.pub`
5. Save

### 20.3 Add Key to the VM Directly

```bash
# SSH via browser first, then:
echo "ssh-ed25519 AAAAC3... scanner-deploy" >> ~/.ssh/authorized_keys
```

---

## Updating the Scanner

### Via SSH

```bash
ssh -i ~/.ssh/gcp-scanner ubuntu@<EXTERNAL_IP>
cd /opt/scanner
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart scanner
sudo systemctl restart scanner-dashboard
```

### Via GitHub Actions CI/CD

The `.github/workflows/deploy.yml` file handles automated deployment. Configure these **GitHub Secrets**:

| Secret | Value |
|--------|-------|
| `GCP_HOST` | External IP of your VM |
| `GCP_USERNAME` | `ubuntu` |
| `GCP_SSH_KEY` | Contents of your private key (`~/.ssh/gcp-scanner`) |
| `GCP_PORT` | `22` |

---

## Monitoring

### GCP Monitoring Console

- **Compute Engine** → **VM Instances** → click the VM name → **Monitoring** tab
- View CPU, memory, disk, network usage

### Cloud Monitoring (Optional)

1. Go to **Monitoring** → **Uptime Checks**
2. Create a check for `http://<EXTERNAL_IP>/health`
3. Set alert if check fails for 2+ minutes

### Custom Metrics via `/metrics`

The `/metrics` endpoint exposes Prometheus-compatible metrics. To scrape them:

```bash
# Install the Google Cloud Ops Agent
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

---

## Troubleshooting

### VM feels slow (f1-micro only has 0.6 GB RAM)

```bash
# Check memory usage
free -h

# If memory is exhausted, add swap:
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Scanner won't start

```bash
# Check service logs
sudo journalctl -u scanner -n 50 --no-pager

# Check scanner logs
tail -f /opt/scanner/logs/scanner.log

# Test manually
cd /opt/scanner && source venv/bin/activate && python main.py
```

### Port 80/443 not accessible

1. Check firewall: `sudo ufw status`
2. Check GCP firewall rules in console
3. Verify the VM has the `http-server` and `https-server` tags

### Out of disk space

```bash
# Check usage
df -h

# Clean old reports
rm -rf /opt/scanner/reports/*.xlsx /opt/scanner/reports/*.csv

# Clean old charts
rm -rf /opt/scanner/charts/*.png

# Clean package cache
sudo apt-get clean

# Check what's using space
du -sh /opt/scanner/* | sort -h
```

---

## Quick Reference

### SSH Commands

```bash
# Connect
gcloud compute ssh scanner-vm --zone=us-west1-b

# Or with external client
ssh -i ~/.ssh/gcp-scanner ubuntu@<EXTERNAL_IP>

# Copy files
gcloud compute scp local-file ubuntu@scanner-vm:~/ --zone=us-west1-b
```

### Service Commands

```bash
sudo systemctl status scanner
sudo systemctl start scanner
sudo systemctl stop scanner
sudo systemctl restart scanner
sudo systemctl enable scanner
sudo journalctl -u scanner -f
```

### GCP CLI Commands

```bash
# List instances
gcloud compute instances list

# Stop/Start instance
gcloud compute instances stop scanner-vm --zone=us-west1-b
gcloud compute instances start scanner-vm --zone=us-west1-b

# SSH
gcloud compute ssh scanner-vm --zone=us-west1-b

# Copy files
gcloud compute scp /opt/scanner/reports/report.xlsx ubuntu@scanner-vm:~/ --zone=us-west1-b
```

### URLs

```
Dashboard: http://<EXTERNAL_IP>/dashboard
Health:    http://<EXTERNAL_IP>/health
Metrics:   http://<EXTERNAL_IP>/metrics
Status:    http://<EXTERNAL_IP>/status
API:       http://<EXTERNAL_IP>/api/signals
```

---

## Comparison: GCP vs Oracle Cloud

| Aspect | GCP Free Tier | Oracle Cloud Always Free |
|--------|---------------|-------------------------|
| VM Specs | 1 f1-micro (0.2 vCPU, 0.6 GB) | 2 AMD (1 GB each) or 4 ARM (24 GB) |
| Disk | 30 GB | 200 GB |
| Network | 1 GB egress/month | 10 TB egress/month |
| Always Free | Yes (indefinite) | Yes (indefinite) |
| Setup Complexity | Medium | Medium |
| Dashboard | Easy with Nginx | Same |

**Oracle Cloud provides significantly more resources for free**, but GCP's infrastructure is more polished and reliable. Use GCP if you prefer Google's ecosystem or already use GCP services.
