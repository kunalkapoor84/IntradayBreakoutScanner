import json
import requests
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

from config.settings import CONFIG
from config.logging_setup import setup_logging
from app.database.db import Database

logger = setup_logging("notification")


class MultiChannelNotifier:
    def __init__(self):
        self.db = Database()
        self._init_channels()

    def _init_channels(self):
        self.telegram_enabled = bool(CONFIG.alert.telegram_bot_token and CONFIG.alert.telegram_chat_id)
        self.email_enabled = bool(CONFIG.alert.email_sender and CONFIG.alert.email_password and CONFIG.alert.email_recipients)
        self.discord_enabled = bool(CONFIG.alert.discord_webhook_url)
        self.slack_enabled = bool(CONFIG.alert.slack_webhook_url)

    def send_scan_report(self, output) -> None:
        if not output or not output.top_stocks:
            return
        message = self._format_scan_message(output)
        if self.telegram_enabled:
            self._send_telegram(message)
        if self.email_enabled:
            self._send_email(message)
        if self.discord_enabled:
            self._send_discord(message)
        if self.slack_enabled:
            self._send_slack(message)

    def send_alert(self, alert_type: str, message: str) -> None:
        full_msg = f"[{alert_type.upper()}] {message}"
        if self.telegram_enabled:
            self._send_telegram(full_msg)
        if self.discord_enabled:
            self._send_discord(full_msg)
        if self.slack_enabled:
            self._send_slack(full_msg)

    def _format_scan_message(self, output) -> str:
        lines = [
            "Intraday Breakout Scanner Report",
            f"Generated: {output.generated_at}",
            f"Analyzed: {output.total_stocks_analyzed} stocks",
            f"Shortlisted: {output.stocks_shortlisted}",
            "",
            "Top Picks:",
        ]
        for i, s in enumerate(output.top_stocks[:5], 1):
            emoji = "BULLISH" if "Bullish" in str(s.direction) else "BEARISH"
            lines.append(
                f"{i}. {s.symbol} | Score: {s.total_score:.1f} | {emoji} | "
                f"Conf: {s.confidence:.0f}% | Entry: {s.entry_price} | "
                f"SL: {s.stop_loss} | T1: {s.target_1} | R:R: {s.risk_reward}"
            )
        return "\n".join(lines)

    def _send_telegram(self, message: str) -> None:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{CONFIG.alert.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": CONFIG.alert.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            resp.raise_for_status()
            self.db.record_notification("telegram", "message", message[:200])
            logger.info("Telegram notification sent")
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            self.db.record_notification("telegram", "message", message[:200], status="failed", error=str(e))

    def _send_telegram_file(self, filepath: str) -> None:
        try:
            with open(filepath, "rb") as f:
                resp = requests.post(
                    f"https://api.telegram.org/bot{CONFIG.alert.telegram_bot_token}/sendDocument",
                    data={"chat_id": CONFIG.alert.telegram_chat_id},
                    files={"document": f},
                    timeout=30,
                )
                resp.raise_for_status()
            logger.info("Telegram file sent: %s", filepath)
        except Exception as e:
            logger.error("Telegram file send failed: %s", e)

    def _send_email(self, message: str) -> None:
        try:
            msg = MIMEMultipart()
            msg["From"] = CONFIG.alert.email_sender
            msg["To"] = ", ".join(CONFIG.alert.email_recipients)
            msg["Subject"] = f"Intraday Scanner Report - {datetime.now().strftime('%Y-%m-%d')}"
            msg.attach(MIMEText(message, "plain"))
            with smtplib.SMTP(CONFIG.alert.email_smtp_host, CONFIG.alert.email_smtp_port) as s:
                s.starttls()
                s.login(CONFIG.alert.email_sender, CONFIG.alert.email_password)
                s.send_message(msg)
            self.db.record_notification("email", "report", message[:200])
            logger.info("Email notification sent")
        except Exception as e:
            logger.error("Email send failed: %s", e)
            self.db.record_notification("email", "report", message[:200], status="failed", error=str(e))

    def _send_discord(self, message: str) -> None:
        try:
            resp = requests.post(
                CONFIG.alert.discord_webhook_url,
                json={"content": message[:2000]},
                timeout=10,
            )
            resp.raise_for_status()
            self.db.record_notification("discord", "message", message[:200])
            logger.info("Discord notification sent")
        except Exception as e:
            logger.error("Discord send failed: %s", e)
            self.db.record_notification("discord", "message", message[:200], status="failed", error=str(e))

    def _send_slack(self, message: str) -> None:
        try:
            resp = requests.post(
                CONFIG.alert.slack_webhook_url,
                json={"text": message},
                timeout=10,
            )
            resp.raise_for_status()
            self.db.record_notification("slack", "message", message[:200])
            logger.info("Slack notification sent")
        except Exception as e:
            logger.error("Slack send failed: %s", e)
            self.db.record_notification("slack", "message", message[:200], status="failed", error=str(e))
