import requests
from config.settings import CONFIG
from config.logging_setup import setup_logging
from models import ScannerOutput

logger = setup_logging("telegram_alert")


class TelegramAlert:
    def __init__(self):
        self.bot_token = CONFIG.alert.telegram_bot_token
        self.chat_id = CONFIG.alert.telegram_chat_id
        self.enabled = bool(self.bot_token and self.chat_id)

    def send_report(self, output: ScannerOutput):
        if not self.enabled or not output.top_stocks: return
        lines = ["🚀 *Intraday Breakout Scanner*", f"📅 {output.generated_at}", f"📊 Analyzed: {output.total_stocks_analyzed}", f"✅ Shortlisted: {output.stocks_shortlisted}", "", "*Top 5:*"]
        for i, s in enumerate(output.top_stocks[:5], 1):
            em = "🟢" if "Bullish" in str(s.direction) else "🔴"
            lines.append(f"{i}. {em} *{s.symbol}* | Score: {s.total_score:.1f} | Conf: {s.confidence:.0f}%")
            lines.append(f"   Entry: {s.entry_price} | SL: {s.stop_loss} | T1: {s.target_1} | T2: {s.target_2}")
        lines.append("\n#IntradayScanner")
        try:
            requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                         json={"chat_id": self.chat_id, "text": "\n".join(lines), "parse_mode": "Markdown",
                               "disable_web_page_preview": True}, timeout=10)
        except Exception as e: logger.error(f"Telegram failed: {e}")

    def send_file(self, filepath: str):
        if not self.enabled or not filepath: return
        try:
            with open(filepath, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendDocument",
                             data={"chat_id": self.chat_id},
                             files={"document": f}, timeout=30)
            logger.info(f"Sent file to Telegram: {filepath}")
        except Exception as e: logger.error(f"Telegram send_file failed: {e}")
