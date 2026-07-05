# Intraday Breakout Scanner

Production-grade AI-powered stock scanner for NSE F&O stocks, connecting to the Dhan API. Continuously scans for intraday and swing trading opportunities with automated scheduling, notifications, and reporting.

## Architecture

```
                      ┌─────────────────────────┐
                      │    Dhan API (NSE F&O)    │
                      └──────────┬──────────────┘
                                 │
                      ┌──────────▼──────────────┐
                      │    Data Collector        │
                      │  (Historical, Quotes,    │
                      │   Options, Futures)      │
                      └──────────┬──────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
     ┌────────▼──────┐  ┌───────▼───────┐  ┌───────▼──────┐
     │   Analysis    │  │   AI Scorer   │  │    Risk      │
     │  (Patterns,   │  │  (Weighted     │  │  (Position   │
     │  Momentum,    │  │   Scoring)     │  │   Sizing)    │
     │  Volume, etc) │  └───────┬───────┘  └───────┬──────┘
     └───────────────┘          │                  │
                                └──────┬───────────┘
                                       │
                          ┌────────────▼────────────┐
                          │   Scanner Engine         │
                          │  (Results, Signals,      │
                          │   Trade Plans)           │
                          └────────────┬────────────┘
                                       │
              ┌────────────────────────┼────────────────────┐
              │                        │                    │
     ┌────────▼──────┐      ┌─────────▼───────┐  ┌─────────▼──────┐
     │   Database    │      │   Notification  │  │    Reports     │
     │  (SQLite)     │      │  (Telegram/     │  │  (Excel/CSV/   │
     │               │      │   Email/Discord)│  │   JSON/HTML)   │
     └───────────────┘      └─────────────────┘  └────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Dhan API credentials (client ID + access token)
- Telegram bot (optional, for notifications)

### Local Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/intraday-breakout-scanner.git
cd intraday-breakout-scanner

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Run Scanner

```bash
# Single scan
python main.py

# Continuous live mode (scans every 5 minutes)
python main.py --mode live

# Scheduler mode (APScheduler or threading)
python main.py --mode schedule

# Analyze a single symbol
python main.py --symbol RELIANCE
```

### Start Dashboard

```bash
uvicorn app.dashboard.app:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000/dashboard
```

## Deployment Options

### Oracle Cloud Always Free (Recommended)

```bash
# SSH into your Oracle Cloud Ubuntu VM
ssh ubuntu@<your-vm-ip>

# Download and run the setup script
wget -O - https://raw.githubusercontent.com/yourusername/intraday-breakout-scanner/main/deployment/oracle_cloud_setup.sh | bash

# Edit your .env file
nano /opt/scanner/.env

# Start the scanner
sudo systemctl start scanner
```

### Docker

```bash
docker compose -f docker/docker-compose.yml up -d

# With dashboard
docker compose -f docker/docker-compose.yml --profile dashboard up -d
```

### systemd (Linux)

```bash
sudo cp deployment/scanner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scanner
sudo systemctl start scanner
```

### AWS EC2 / Google Cloud / Azure

1. Provision an Ubuntu 22.04+ VM (free tier eligible)
2. Follow the Oracle Cloud setup steps above (general Linux setup works on all platforms)

### Raspberry Pi (ARM)

```bash
# Install Python 3.11 for ARM
sudo apt-get install python3.11 python3.11-venv
# Follow local installation steps
```

### Windows

```bash
# Install Python from python.org
# Clone repo and set up venv
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python main.py --mode live
```

## Deployment Comparison

| Platform      | Cost       | Reliability | Performance | Setup     | Best For                    |
|---------------|------------|-------------|-------------|-----------|-----------------------------|
| Oracle Cloud  | Free       | High        | Good        | Medium    | Primary recommendation      |
| AWS Free Tier | Free (1yr) | Very High   | Good        | Medium    | AWS ecosystem users         |
| Google Cloud  | Free       | High        | Good        | Medium    | GCP ecosystem users         |
| Azure Free    | Free (1yr) | High        | Good        | Medium    | Microsoft ecosystem users   |
| Railway       | Free tier  | Medium      | Medium      | Easy      | Quick deploy, no SSH needed |
| Render        | Free tier  | Medium      | Medium      | Easy      | Quick deploy, no SSH needed |
| Raspberry Pi  | One-time   | Medium      | Low         | Medium    | Local, zero cloud cost      |
| Ubuntu Linux  | Free       | High        | Good        | Medium    | Self-managed, full control  |
| Windows       | Free       | Medium      | Good        | Easy      | Local dev/testing           |

**Recommendation: Oracle Cloud Always Free** for 24×7 unattended operation with the best free-tier reliability.

## Scheduling

The scanner supports two scheduling modes:

### 1. APScheduler (Recommended)

```bash
python main.py --mode schedule
```

Automatically:
- Runs every 15 minutes during market hours (9:15 AM - 3:30 PM IST)
- Runs an end-of-day scan at 3:40 PM IST
- Detects weekends and trading holidays
- Prevents overlapping scans
- Handles misfires and coalesces missed runs

### 2. Linux Cron

```bash
# Install crontab
crontab config/crontab
```

### 3. Manual

```bash
python main.py --mode live
```

## Configuration

All configuration is managed via `.env` file. Never hardcode credentials.

```ini
# Dhan API
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_token

# Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# Scheduling
SCAN_INTERVAL_MINUTES=15
MARKET_OPEN=09:15
MARKET_CLOSE=15:30
EOD_SCAN_TIME=15:40
```

## Dashboard

Accessible at `http://<host>:8000/dashboard`

- Real-time scanner status
- Latest signals and rankings
- Scan history and performance metrics
- Error monitoring
- Dark theme with auto-refresh

### API Endpoints

| Endpoint          | Description                    |
|-------------------|--------------------------------|
| `/health`         | Health check                   |
| `/status`         | Full system status             |
| `/metrics`        | Prometheus-compatible metrics  |
| `/dashboard`      | Web dashboard (HTML)           |
| `/api/signals`    | Latest signals                 |
| `/api/scans`      | Scan history                   |
| `/api/stats`      | Performance statistics         |
| `/api/errors`     | Error log                      |
| `/reports`        | List generated reports         |

## Notifications

Automatic notifications via configured channels when:

- Scanner starts/finishes
- High-confidence signals detected
- Scanner crashes or API failure
- End-of-day report ready
- Database errors

## Project Structure

```
scanner/
├── app/
│   ├── database/          # SQLite database layer
│   │   ├── schema.py      # SQL schema
│   │   └── db.py          # Database client
│   ├── dashboard/         # FastAPI web dashboard
│   │   └── app.py         # API + HTML dashboard
│   ├── scheduler/         # Enhanced scheduler
│   │   └── enhanced_scheduler.py
│   ├── health/            # Health monitoring
│   │   └── monitor.py
│   └── notifications/     # Multi-channel notifications
│       └── multi_channel.py
├── config/
│   ├── settings.py        # Application configuration
│   └── logging_setup.py   # Rotating log configuration
├── data/                  # Data collection modules
├── analysis/              # Technical analysis modules
├── scoring/               # AI scoring engine
├── reporting/             # Report generation
├── alerts/                # Alert integrations
├── ml/                    # ML model infrastructure
├── scheduler/             # Legacy scheduler
├── deployment/            # Deployment scripts
│   ├── oracle_cloud_setup.sh
│   ├── setup.sh
│   ├── deploy.sh
│   ├── update.sh
│   ├── start.sh / stop.sh / restart.sh
│   ├── backup.sh
│   └── health_check.sh
├── docker/
│   ├── Dockerfile         # Production Dockerfile
│   └── docker-compose.yml # Multi-service setup
├── systemd/
│   └── scanner.service    # systemd service definition
├── scripts/               # Utility scripts
├── tests/                 # Test suite
├── .github/workflows/     # CI/CD pipelines
├── .env.example           # Environment template
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Database Schema

SQLite database with tables for:
- `scan_history` - Each scan execution record
- `signals` - Generated trading signals
- `trades` - Trade journal
- `performance` - Daily performance metrics
- `notifications` - Notification audit log
- `errors` - Error tracking
- `backtest_results` - Backtest results

## Monitoring

### Prometheus Metrics

Exposed at `/metrics` endpoint:
- `scanner_uptime_seconds`
- `scanner_scans_total`
- `scanner_signals_total`
- `system_cpu_percent`
- `system_memory_percent`

### Health Check Script

```bash
bash deployment/health_check.sh
```

### Logging

Rotating log files (10MB each, 5 backups):
- `scanner.log` - Main scanner activity
- `error.log` - All errors
- `scheduler.log` - Scheduler activity
- `api.log` - API calls
- `notification.log` - Notification delivery
- `trade.log` - Trade execution
- `performance.log` - Performance metrics

## Backup & Restore

### Automatic Daily Backups

```bash
# Manual backup
bash deployment/backup.sh /opt/scanner /opt/scanner-backups

# Automatic (via cron)
0 4 * * * root /opt/scanner/deployment/backup.sh
```

### Restore

```bash
# List backups
ls /opt/scanner-backups/

# Restore a backup
tar -xzf /opt/scanner-backups/backup_20250101_000000.tar.gz -C /opt/scanner-restore/
systemctl stop scanner
cp /opt/scanner-restore/backup_20250101_000000/data/scanner.db /opt/scanner/data/
cp -r /opt/scanner-restore/backup_20250101_000000/reports/* /opt/scanner/reports/
systemctl start scanner
```

## Security

- All secrets stored in `.env`, never in code
- SSH key authentication (password auth disabled)
- Firewall: only ports 22, 80, 443, 8000 open
- fail2ban for SSH brute-force protection
- Non-root user for application
- systemd security hardening (NoNewPrivileges, PrivateTmp, ProtectSystem)
- Nginx reverse proxy with HTTPS (optional)

## ML-Ready Architecture

The scoring engine supports pluggable ML models:

```python
from ml.model import MLPredictor

# Currently rule-based; swap with any framework:
class XGBoostPredictor(MLPredictor):
    def predict(self, features):
        return self.model.predict(features)

# Supported: TensorFlow, PyTorch, XGBoost, LightGBM, CatBoost
```

## CI/CD

GitHub Actions workflow (`.github/workflows/deploy.yml`):
1. On push to `main`: run tests
2. Build Docker image (optional)
3. Deploy to Oracle Cloud via SSH
4. Restart scanner service
5. Verify health endpoint

## Troubleshooting

### Scanner won't start
```bash
# Check logs
journalctl -u scanner -n 50 --no-pager
tail -f /opt/scanner/logs/scanner.log

# Check .env configuration
cat /opt/scanner/.env | grep -v PASSWORD | grep -v TOKEN

# Verify Python environment
/opt/scanner/venv/bin/python -c "import dhanhq; print('OK')"
```

### API errors
```bash
# Check API connectivity
curl -I https://api.dhan.co

# Check rate limiting
tail -f /opt/scanner/logs/api.log
```

### Database issues
```bash
# Check database integrity
sqlite3 /opt/scanner/data/scanner.db "PRAGMA integrity_check;"

# Vacuum database
sqlite3 /opt/scanner/data/scanner.db "VACUUM;"
```

## License

MIT License - See LICENSE file for details.
