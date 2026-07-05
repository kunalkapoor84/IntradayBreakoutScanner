import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import CONFIG
from config.logging_setup import setup_logging
from models import ScannerOutput

logger = setup_logging("email_alert")


class EmailAlert:
    def __init__(self):
        self.sender = CONFIG.alert.email_sender
        self.password = CONFIG.alert.email_password
        self.recipients = CONFIG.alert.email_recipients
        self.enabled = bool(self.sender and self.password and self.recipients)

    def send_report(self, output: ScannerOutput):
        if not self.enabled: return
        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender; msg["To"] = ", ".join(self.recipients)
            msg["Subject"] = f"Intraday Scanner - {output.generated_at}"
            body = f"Intraday Breakout Scanner Report\nGenerated: {output.generated_at}\nAnalyzed: {output.total_stocks_analyzed}\nShortlisted: {output.stocks_shortlisted}\n\n"
            for i, s in enumerate(output.top_stocks[:10], 1):
                body += f"{i}. {s.symbol} | Score: {s.total_score:.1f} | {s.direction.value if hasattr(s.direction,'value') else s.direction} | Entry: {s.entry_price} | SL: {s.stop_loss} | T1: {s.target_1} | T2: {s.target_2}\n"
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(CONFIG.alert.email_smtp_host, CONFIG.alert.email_smtp_port) as s:
                s.starttls(); s.login(self.sender, self.password); s.send_message(msg)
            logger.info("Email sent")
        except Exception as e: logger.error(f"Email failed: {e}")
