import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from config.settings import CONFIG
from config.logging_setup import setup_logging
from app.database.db import Database
from app.health.monitor import monitor

logger = setup_logging("dashboard")
db = Database()

app = FastAPI(
    title="Intraday Breakout Scanner Dashboard",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "app": "Intraday Breakout Scanner", "version": "1.0.0"}


@app.get("/health")
async def health():
    status = monitor.get_status()
    overall = "healthy"
    if not status["database"]["exists"]:
        overall = "degraded"
    return {"status": overall, "checks": status}


@app.get("/status")
async def status():
    return monitor.get_status()


@app.get("/metrics")
async def metrics():
    s = monitor.get_status()
    lines = [
        f"# HELP scanner_uptime_seconds Scanner uptime",
        f"# TYPE scanner_uptime_seconds gauge",
        f"scanner_uptime_seconds {s['uptime_seconds']}",
        f"# HELP scanner_scans_total Total scans today",
        f"# TYPE scanner_scans_total gauge",
        f"scanner_scans_total {s['today']['total_scans']}",
        f"# HELP scanner_signals_total Total signals today",
        f"# TYPE scanner_signals_total gauge",
        f"scanner_signals_total {s['today']['total_signals']}",
    ]
    if "cpu_percent" in s.get("system", {}):
        cpu = s["system"].get("cpu_percent", 0)
        if isinstance(cpu, (int, float)):
            lines.append(f"# HELP system_cpu_percent CPU usage")
            lines.append(f"# TYPE system_cpu_percent gauge")
            lines.append(f"system_cpu_percent {cpu}")
    if "memory_percent" in s.get("system", {}):
        mem = s["system"].get("memory_percent", 0)
        if isinstance(mem, (int, float)):
            lines.append(f"# HELP system_memory_percent Memory usage")
            lines.append(f"# TYPE system_memory_percent gauge")
            lines.append(f"system_memory_percent {mem}")
    return PlainTextResponse("\n".join(lines) + "\n")


@app.get("/api/scans")
async def get_scans(limit: int = Query(50, ge=1, le=200)):
    rows = db.fetchall("SELECT * FROM scan_history ORDER BY id DESC LIMIT ?", (limit,))
    return {"scans": rows}


@app.get("/api/signals")
async def get_signals(limit: int = Query(20, ge=1, le=200)):
    rows = db.get_top_signals_today(limit)
    return {"signals": rows}


@app.get("/api/signals/{symbol}")
async def get_symbol_signals(symbol: str, limit: int = Query(20, ge=1, le=200)):
    rows = db.fetchall(
        "SELECT * FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT ?",
        (symbol.upper(), limit),
    )
    return {"symbol": symbol.upper(), "signals": rows}


@app.get("/api/errors")
async def get_errors(limit: int = Query(50, ge=1, le=200)):
    rows = db.fetchall("SELECT * FROM errors ORDER BY id DESC LIMIT ?", (limit,))
    return {"errors": rows}


@app.get("/api/stats")
async def get_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    today_stats = db.fetchone("""
        SELECT COUNT(*) as scans, COALESCE(SUM(shortlisted),0) as signals
        FROM scan_history WHERE scan_time LIKE ?
    """, (f"{today}%",))
    weekly = db.fetchall("""
        SELECT date(scan_time) as day, COUNT(*) as scans, COALESCE(SUM(shortlisted),0) as signals
        FROM scan_history WHERE scan_time >= ? GROUP BY date(scan_time) ORDER BY day DESC
    """, (week_ago,))
    return {
        "today": today_stats,
        "weekly": weekly,
    }


@app.get("/api/latest")
async def get_latest():
    scan = db.get_latest_scan()
    signals = db.get_top_signals_today(5) if scan else []
    return {"scan": scan, "signals": signals}


@app.get("/reports")
async def list_reports():
    report_dir = Path(CONFIG.report_dir)
    if not report_dir.exists():
        return {"reports": []}
    files = []
    for f in sorted(report_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:50]:
        if f.is_file():
            files.append({
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return {"reports": files}


@app.get("/reports/{filename}")
async def download_report(filename: str):
    report_dir = Path(CONFIG.report_dir)
    filepath = report_dir / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(str(filepath), filename=filename)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_html():
    return HTMLResponse(DASHBOARD_HTML)


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Intraday Breakout Scanner Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1923; color: #e0e0e0; padding: 20px; }
.container { max-width: 1400px; margin: 0 auto; }
.header { background: linear-gradient(135deg, #1a237e, #0d47a1); padding: 20px 24px; border-radius: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
.header h1 { font-size: 22px; color: #fff; }
.header .meta { font-size: 13px; color: rgba(255,255,255,0.7); }
.status-bar { background: #1a2332; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px; display: flex; gap: 24px; flex-wrap: wrap; }
.status-item { font-size: 13px; }
.status-item .label { color: #78909c; }
.status-item .value { color: #e0e0e0; font-weight: 600; margin-left: 6px; }
.status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.dot-green { background: #4caf50; }
.dot-red { background: #f44336; }
.dot-yellow { background: #ff9800; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.card { background: #1a2332; border-radius: 10px; padding: 20px; }
.card h3 { font-size: 14px; color: #78909c; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px 6px; color: #78909c; border-bottom: 1px solid #263238; font-weight: 600; }
td { padding: 8px 6px; border-bottom: 1px solid #1e2c3a; }
tr:hover td { background: #1e2c3a; }
.score-high { color: #4caf50; font-weight: 600; }
.score-mid { color: #ff9800; font-weight: 600; }
.score-low { color: #f44336; font-weight: 600; }
.bullish { color: #4caf50; }
.bearish { color: #f44336; }
.neutral { color: #ff9800; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.tag-bull { background: rgba(76,175,80,0.2); color: #4caf50; }
.tag-bear { background: rgba(244,67,54,0.2); color: #f44336; }
.metrics-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; margin-bottom: 16px; }
.metric-box { background: #0f1923; border-radius: 8px; padding: 12px; text-align: center; }
.metric-box .val { font-size: 20px; font-weight: 700; }
.metric-box .lbl { font-size: 11px; color: #78909c; margin-top: 4px; }
.full-width { grid-column: 1 / -1; }
.refresh { background: #1565c0; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.refresh:hover { background: #1976d2; }
@media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>Intraday Breakout Scanner</h1>
      <div class="meta" id="headerMeta">Loading...</div>
    </div>
    <button class="refresh" onclick="fetchAll()">Refresh</button>
  </div>
  <div class="status-bar" id="statusBar"></div>
  <div class="metrics-row" id="metricsRow"></div>
  <div class="grid">
    <div class="card">
      <h3>Latest Signals</h3>
      <table><thead><tr><th>#</th><th>Symbol</th><th>Score</th><th>Direction</th><th>Conf</th><th>Entry</th><th>SL</th><th>T1</th><th>R:R</th><th>Strategy</th></tr></thead>
      <tbody id="signalsBody"></tbody></table>
    </div>
    <div class="card">
      <h3>Recent Scans</h3>
      <table><thead><tr><th>Time</th><th>Type</th><th>Stocks</th><th>Shortlisted</th><th>Duration</th><th>Status</th></tr></thead>
      <tbody id="scansBody"></tbody></table>
    </div>
  </div>
  <div class="card full-width">
    <h3>Scanner Errors</h3>
    <table><thead><tr><th>Time</th><th>Source</th><th>Type</th><th>Message</th></tr></thead>
    <tbody id="errorsBody"></tbody></table>
  </div>
</div>
<script>
async function fetchJSON(url) { const r = await fetch(url); return r.json(); }
async function fetchAll() {
  const [status, signals, scans, errors] = await Promise.all([
    fetchJSON('/status'), fetchJSON('/api/signals?limit=20'),
    fetchJSON('/api/scans?limit=20'), fetchJSON('/api/errors?limit=10'),
  ]);
  const now = new Date();
  document.getElementById('headerMeta').textContent =
    `Last Updated: ${now.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST | ` +
    `Scanner Uptime: ${Math.floor(status.uptime_seconds / 3600)}h ${Math.floor((status.uptime_seconds % 3600) / 60)}m`;
  const mkt = status.market || {};
  document.getElementById('statusBar').innerHTML = `
    <div class="status-item"><span class="status-dot ${mkt.is_market_open ? 'dot-green' : 'dot-yellow'}"></span><span class="label">Market:</span><span class="value">${mkt.is_market_open ? 'OPEN' : 'CLOSED'}</span></div>
    <div class="status-item"><span class="status-dot ${mkt.is_trading_day ? 'dot-green' : 'dot-red'}"></span><span class="label">Trading Day:</span><span class="value">${mkt.is_trading_day ? 'Yes' : 'No'}</span></div>
    <div class="status-item"><span class="label">Time:</span><span class="value">${mkt.current_time || ''}</span></div>
    <div class="status-item"><span class="label">Timezone:</span><span class="value">${mkt.timezone || ''}</span></div>
    <div class="status-item"><span class="label">DB:</span><span class="value">${status.database?.status || 'unknown'}</span></div>
  `;
  const today = status.today || {};
  document.getElementById('metricsRow').innerHTML = `
    <div class="metric-box"><div class="val">${today.total_scans || 0}</div><div class="lbl">Scans Today</div></div>
    <div class="metric-box"><div class="val">${today.total_signals || 0}</div><div class="lbl">Signals Today</div></div>
    <div class="metric-box"><div class="val">${Math.floor(status.uptime_seconds / 3600)}h</div><div class="lbl">Uptime</div></div>
  `;
  const sigs = signals.signals || [];
  document.getElementById('signalsBody').innerHTML = sigs.slice(0, 20).map((s, i) => {
    const dirClass = (s.direction || '').toLowerCase();
    const scoreClass = s.score >= 75 ? 'score-high' : s.score >= 60 ? 'score-mid' : 'score-low';
    return `<tr><td>${i+1}</td><td><strong>${s.symbol}</strong></td><td class="${scoreClass}">${s.score?.toFixed(1)}</td><td class="${dirClass}"><span class="tag tag-${dirClass}">${s.direction || '-'}</span></td><td>${s.confidence?.toFixed(0)}%</td><td>${s.entry_price || '-'}</td><td>${s.stop_loss || '-'}</td><td>${s.target_1 || '-'}</td><td>${s.risk_reward || '-'}</td><td>${s.strategy || '-'}</td></tr>`;
  }).join('');
  const scs = scans.scans || [];
  document.getElementById('scansBody').innerHTML = scs.slice(0, 15).map(s => {
    const statusClass = s.status === 'success' ? 'dot-green' : 'dot-red';
    return `<tr><td>${s.scan_time || ''}</td><td>${s.scan_type || ''}</td><td>${s.total_stocks || 0}</td><td>${s.shortlisted || 0}</td><td>${s.duration_seconds?.toFixed(1) || 0}s</td><td><span class="status-dot ${statusClass}"></span>${s.status || ''}</td></tr>`;
  }).join('');
  const errs = errors.errors || [];
  document.getElementById('errorsBody').innerHTML = errs.slice(0, 8).map(e =>
    `<tr><td>${e.created_at || ''}</td><td>${e.source || ''}</td><td>${e.error_type || ''}</td><td>${(e.message || '').substring(0, 60)}...</td></tr>`
  ).join('') || '<tr><td colspan="4" style="text-align:center;color:#78909c">No errors</td></tr>';
}
fetchAll();
setInterval(fetchAll, 30000);
</script>
</body>
</html>
"""


from fastapi.responses import PlainTextResponse
