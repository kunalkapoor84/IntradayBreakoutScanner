import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass
class DhanConfig:
    client_id: str = field(default_factory=lambda: _get("DHAN_CLIENT_ID", ""))
    access_token: str = field(default_factory=lambda: _get("DHAN_ACCESS_TOKEN", ""))
    base_url: str = "https://api.dhan.co"
    timeout: int = 30
    retry_count: int = 3


@dataclass
class ScannerConfig:
    min_price: float = 50.0
    min_avg_turnover_crore: float = 10.0
    min_avg_volume_lakhs: float = 3.0
    min_delivery_pct: float = 20.0
    score_threshold: float = 55.0
    top_n: int = 20
    lookback_daily_days: int = 365
    lookback_intraday_days: int = 20
    intraday_interval_minutes: int = 5
    max_risk_per_trade: float = 500.0
    live_intraday_interval_minutes: int = 15
    live_intraday_lookback_days: int = 5


@dataclass
class ScoringWeights:
    trend: float = 20.0
    price_action: float = 15.0
    volume: float = 15.0
    momentum: float = 15.0
    volatility: float = 10.0
    relative_strength: float = 10.0
    liquidity: float = 10.0
    market_context: float = 5.0


@dataclass
class AlertConfig:
    telegram_bot_token: str = field(default_factory=lambda: _get("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: _get("TELEGRAM_CHAT_ID", ""))
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_sender: str = field(default_factory=lambda: _get("EMAIL_SENDER", ""))
    email_password: str = field(default_factory=lambda: _get("EMAIL_PASSWORD", ""))
    email_recipients: List[str] = field(default_factory=lambda: [r.strip() for r in _get("EMAIL_RECIPIENTS", "").split(",") if r.strip()])
    discord_webhook_url: str = field(default_factory=lambda: _get("DISCORD_WEBHOOK_URL", ""))
    slack_webhook_url: str = field(default_factory=lambda: _get("SLACK_WEBHOOK_URL", ""))


@dataclass
class AppConfig:
    dhan: DhanConfig = field(default_factory=DhanConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    alert: AlertConfig = field(default_factory=AlertConfig)
    log_level: str = "INFO"
    db_path: str = field(default_factory=lambda: _get("DATABASE_PATH", str(PROJECT_ROOT / "data" / "scanner.db")))
    log_dir: str = field(default_factory=lambda: _get("LOG_DIR", str(PROJECT_ROOT / "logs")))
    report_dir: str = field(default_factory=lambda: _get("REPORT_DIR", str(PROJECT_ROOT / "reports")))
    chart_dir: str = field(default_factory=lambda: _get("CHART_DIR", str(PROJECT_ROOT / "charts")))
    output_dir: str = field(default_factory=lambda: _get("OUTPUT_DIR", str(PROJECT_ROOT / "output")))
    scan_interval_minutes: int = int(_get("SCAN_INTERVAL_MINUTES", "15"))
    market_open: str = _get("MARKET_OPEN", "09:15")
    market_close: str = _get("MARKET_CLOSE", "15:30")
    eod_scan_time: str = _get("EOD_SCAN_TIME", "15:40")
    timezone: str = _get("TIMEZONE", "Asia/Kolkata")


CONFIG = AppConfig()
