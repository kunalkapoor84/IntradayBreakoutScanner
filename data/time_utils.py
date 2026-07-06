from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def now_ist() -> datetime:
    return datetime.now(IST)

def date_ist() -> str:
    return now_ist().strftime("%Y-%m-%d")

def time_ist() -> str:
    return now_ist().strftime("%H:%M:%S")
