# Deploying to PythonAnywhere

Step-by-step guide to deploy the Intraday Breakout Scanner on PythonAnywhere's free tier using scheduled tasks and a web-based dashboard.

## Overview

PythonAnywhere is a good option if you want zero infrastructure management. Since the free tier does not support persistent background processes, we use **scheduled tasks** that run cron-style every hour (or set up a loop within a single long-running scheduled task via a console).

## Prerequisites

- A PythonAnywhere account (free tier works)
- Dhan API credentials
- Telegram bot token (optional)

---

## Step 1: Create a PythonAnywhere Account

1. Go to [https://www.pythonanywhere.com/](https://www.pythonanywhere.com/)
2. Sign up for a **Beginner** (free) account
3. Verify your email

---

## Step 2: Clone the Repository

1. Open the PythonAnywhere **Bash console** (from the Dashboard, go to Consoles → Bash)
2. Clone the repository:

```bash
cd ~
git clone https://github.com/yourusername/intraday-breakout-scanner.git
cd intraday-breakout-scanner
```

3. Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

> **Note**: On PythonAnywhere, some packages may require specific versions. If `ta` fails, try `pip install ta-lib` or skip it. The scanner uses its own RSI/ADX calculation internally so TA-Lib is optional.

4. Create required directories:

```bash
mkdir -p logs reports charts output/reports output/charts data
```

5. Configure environment:

```bash
cp .env.example .env
nano .env
```

Fill in your Dhan API credentials and notification tokens.

---

## Step 3: Setup the Database

```bash
cd ~/intraday-breakout-scanner
source venv/bin/activate
python -c "
from app.database.db import Database
db = Database()
print('Database initialized at:', db.db_path)
"
```

Expected output:
```
Database initialized
```

---

## Step 4: Test the Scanner

Run a single manual scan to verify everything works:

```bash
cd ~/intraday-breakout-scanner
source venv/bin/activate
python main.py
```

If successful, you'll see output with scanned stocks and generated reports.

---

## Step 5: Create a Long-Running Scheduler Task

PythonAnywhere free tier allows **one always-on task** via a console or scheduled tasks. The best approach for 24x7 operation is to run the scheduler in a **persistent console** that stays alive.

### Option A: Persistent Console (Recommended)

1. Open a Bash console from PythonAnywhere Dashboard → Consoles → Bash
2. Start the scheduler:

```bash
cd ~/intraday-breakout-scanner
source venv/bin/activate
python main.py --mode schedule
```

3. **Keep the console tab open** in your browser. The scanner will run continuously, scanning every 15 minutes during market hours.

> **Tip**: PythonAnywhere consoles time out after a few hours of inactivity. To keep it alive, install a keep-alive browser extension or check the console periodically.

### Option B: Scheduled Tasks (Free Tier)

PythonAnywhere free accounts can have **3 scheduled tasks** that run at specified times. This is more reliable but cannot run continuously.

1. Go to Dashboard → **Tasks** → **Scheduled**
2. Create three tasks:

| Time | Command |
|------|---------|
| `08:30` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/pre_market.py >> logs/cron.log 2>&1` |
| `09:30` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/cron_scan.py >> logs/cron.log 2>&1` |
| `10:30` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/cron_scan.py >> logs/cron.log 2>&1` |
| `11:30` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/cron_scan.py >> logs/cron.log 2>&1` |
| `12:30` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/cron_scan.py >> logs/cron.log 2>&1` |
| `13:30` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/cron_scan.py >> logs/cron.log 2>&1` |
| `14:30` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/cron_scan.py >> logs/cron.log 2>&1` |
| `15:30` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/cron_scan.py >> logs/cron.log 2>&1` |
| `15:40` weekdays | `cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/eod_scan.py >> logs/cron.log 2>&1` |

> **Free tier limit**: Only 3 scheduled tasks on free plan. For hourly scanning, you'll need to write a single wrapper script that checks the time internally:
>
> Create `scripts/pythonanywhere_task.py`:
> ```python
> #!/usr/bin/env python3
> """Single PythonAnywhere scheduled task that runs every hour."""
> import sys, os, subprocess
> from datetime import datetime, time as dt_time
>
> sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
> from config.settings import CONFIG
>
> MARKET_OPEN = dt_time(9, 15)
> MARKET_CLOSE = dt_time(15, 30)
>
> def should_scan():
>     now = datetime.now()
>     if now.weekday() >= 5:
>         return False, None
>     current = now.time()
>     if MARKET_OPEN <= current <= MARKET_CLOSE:
>         return True, "live"
>     if current >= dt_time(15, 40) and current <= dt_time(15, 45):
>         return True, "eod"
>     return False, None
>
> def main():
>     scan, stype = should_scan()
>     if not scan:
>         return
>     cmd = f"cd {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))} && source venv/bin/activate && python main.py"
>     os.system(cmd)
>
> if __name__ == "__main__":
>     main()
> ```
>
> Then set **one** scheduled task every hour from 9 AM to 4 PM:
> - `0 9-16 * * 1-5 cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/pythonanywhere_task.py >> logs/cron.log 2>&1`
>
> On PythonAnywhere, this cron syntax is set via a single task at minute 0, every hour 9-16, Mon-Fri.

### Option C: Always-On Task (Paid Tier)

On a **Hacker** or higher paid plan ($5+/month), you can use **Always-on tasks**:

1. Go to Dashboard → **Tasks** → **Always-on**
2. Add a new task:

```
cd ~/intraday-breakout-scanner && source venv/bin/activate && python main.py --mode schedule
```

3. This runs continuously and auto-restarts if it crashes.

---

## Step 6: Set Up the Web Dashboard

PythonAnywhere can host the FastAPI web dashboard.

### 6.1 Create a Web App

1. Go to Dashboard → **Web** → **Add a new web app**
2. Click **Next**, choose **Manual configuration**
3. Choose **Python 3.10** (or the version your venv uses)
4. Note the URL: `yourusername.pythonanywhere.com`

### 6.2 Configure WSGI File

1. Go to **Web** → **Code** → click the WSGI configuration file link
2. Replace the content with:

```python
import sys
import os

# Add project to path
PROJECT_DIR = os.path.expanduser('~/intraday-breakout-scanner')
sys.path.insert(0, PROJECT_DIR)

# Activate virtual environment
VENV_DIR = os.path.join(PROJECT_DIR, 'venv')
if VENV_DIR not in sys.path:
    sys.path.insert(0, os.path.join(VENV_DIR, 'lib/python3.10/site-packages'))

# Set environment
os.environ['PYTHONPATH'] = PROJECT_DIR

# Import the FastAPI app via ASGI
from app.dashboard.app import app

# FastAPI needs an ASGI server, but PythonAnywhere uses WSGI.
# We'll mount the FastAPI app as a WSGI callable:
from fastapi.middleware.wsgi import WSGIMiddleware
application = WSGIMiddleware(app)
```

> **Note**: If you get import errors, ensure the Python version in the WSGI file matches your venv's Python version (check with `python --version` in your console).

### 6.3 Alternative: Use a Static HTML Dashboard

If the WSGI setup is complex, you can upload the `reports/*.html` files and serve them as static files:

1. Go to **Web** → **Static Files**
2. Add: URL `/static` → Directory `/home/yourusername/intraday-breakout-scanner/reports`
3. Access reports at: `https://yourusername.pythonanywhere.com/static/scanner_report_20250101_151530.html`

### 6.4 Configure Static Files for Charts

1. Go to **Web** → **Static Files**
2. Add: URL `/charts` → Directory `/home/yourusername/intraday-breakout-scanner/charts`
3. Add: URL `/reports` → Directory `/home/yourusername/intraday-breakout-scanner/reports`

### 6.5 Reload Web App

Click the green **Reload** button at the top of the Web page.

---

## Step 7: Configure Environment Variables

PythonAnywhere does not automatically load `.env` files in the web app context. Set them via the Web UI:

1. Go to **Web** → **Environment variables** (under Code section)
2. Add each variable from your `.env` file:

| Variable | Value |
|----------|-------|
| `DHAN_CLIENT_ID` | `your_client_id` |
| `DHAN_ACCESS_TOKEN` | `your_access_token` |
| `TELEGRAM_BOT_TOKEN` | `your_bot_token` |
| `TELEGRAM_CHAT_ID` | `your_chat_id` |
| `EMAIL_SENDER` | `your_email` |
| `EMAIL_PASSWORD` | `your_app_password` |
| `EMAIL_RECIPIENTS` | `recipient@email.com` |

3. Reload the web app

---

## Step 8: Verify Deployment

### Check the Scanner

```bash
# In a Bash console
cd ~/intraday-breakout-scanner
source venv/bin/activate
python main.py --symbol RELIANCE
```

### Check the Dashboard

Visit `https://yourusername.pythonanywhere.com/dashboard`

If the WSGI setup works, you should see the dark-themed dashboard.

### Check Logs

```bash
tail -f ~/intraday-breakout-scanner/logs/scanner.log
```

### Check the Web App Logs

Go to **Web** → **Logs** → **Error log** — check here for any WSGI errors.

---

## Step 9: Set Up Backup

Add a scheduled task for daily backup:

```
0 4 * * * cd ~/intraday-breakout-scanner && source venv/bin/activate && python scripts/cleanup.py >> logs/backup.log 2>&1
```

---

## Step 10: Configuration Summary

### Storage Limits

| Resource | Free Tier | Paid Tier |
|----------|-----------|-----------|
| Disk space | 512 MB | 5+ GB |
| Always-on tasks | 0 | 1+ |
| Scheduled tasks | 3 | 10+ |
| CPU time | 100 sec/day | 1000+ sec/day |
| Web apps | 1 | 2+ |
| Concurrent connections | 2 | Unlimited |

### Best Practices for Free Tier

1. **Use a single scheduled task** with the wrapper script above that checks time internally
2. **Set the task to run every hour** during market hours (9 AM to 4 PM, Mon-Fri)
3. **Monitor your CPU quota** at the Dashboard → **Account** → **CPU usage**
4. **Keep log rotation aggressive** — logs eat into your 512MB limit
5. **Store charts/reports only when needed** or they'll fill up storage quickly

### Upgrade to Paid

If you exceed free limits, upgrade to a **Hacker** plan ($5/month) for:
- An always-on task (runs the scanner 24x7)
- 1000+ seconds CPU per day
- 5+ GB storage
- Full cron support with 10+ tasks
- SSH access

---

## Troubleshooting

### Scanner runs but produces no output

```bash
# Test Dhan API connectivity
cd ~/intraday-breakout-scanner
source venv/bin/activate
python -c "
from data.dhan_client import DhanClient
c = DhanClient()
print(c.get_market_status())
"
```

### Web app shows 500 error

Check the error log at **Web** → **Logs** → **Error log**. Common issues:
- Python version mismatch between WSGI config and venv
- Missing environment variables
- Package import errors

### Console keeps timing out

- Use a browser with a keep-alive extension
- Or rely on scheduled tasks instead
- Or upgrade to a paid plan for always-on tasks

### CPU quota exceeded

- Increase scan interval from 15 to 30 or 60 minutes
- Use the wrapper script to only scan during critical market times
- Upgrade to a paid plan

### Out of storage

```bash
# Clean old charts
rm -f ~/intraday-breakout-scanner/charts/*.png
# Clean old reports
rm -f ~/intraday-breakout-scanner/reports/*.xlsx
rm -f ~/intraday-breakout-scanner/output/reports/*.xlsx
# Check usage
du -sh ~/intraday-breakout-scanner/
```

---

## Quick Reference

### Console Commands

```bash
# Start scanner (persistent console)
cd ~/intraday-breakout-scanner && source venv/bin/activate && python main.py --mode schedule

# Run single scan
cd ~/intraday-breakout-scanner && source venv/bin/activate && python main.py

# View logs
tail -f ~/intraday-breakout-scanner/logs/scanner.log

# Update code
cd ~/intraday-breakout-scanner && git pull && source venv/bin/activate && pip install -r requirements.txt
```

### URLs

- Dashboard: `https://yourusername.pythonanywhere.com/dashboard`
- Health check: `https://yourusername.pythonanywhere.com/health`
- Reports: `https://yourusername.pythonanywhere.com/reports/scanner_report_20250101_151530.html`
- Charts: `https://yourusername.pythonanywhere.com/charts/RELIANCE_20250101_151530.png`
- PythonAnywhere console: `https://www.pythonanywhere.com/user/yourusername/consoles/`
