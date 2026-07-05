import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LogManager:
    _loggers: dict = {}

    @classmethod
    def get_logger(cls, name: str = "scanner") -> logging.Logger:
        if name in cls._loggers:
            return cls._loggers[name]
        from config.settings import CONFIG
        log_level = getattr(logging, CONFIG.log_level.upper(), logging.INFO)
        log_dir = Path(CONFIG.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        logger.handlers.clear()
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)
        log_files = {
            "scanner": "scanner.log",
            "error": "error.log",
            "api": "api.log",
            "scheduler": "scheduler.log",
            "trade": "trade.log",
            "notification": "notification.log",
            "performance": "performance.log",
        }
        fname = log_files.get(name, "scanner.log")
        fh = RotatingFileHandler(
            log_dir / fname, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        ef = RotatingFileHandler(
            log_dir / "error.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        ef.setLevel(logging.ERROR)
        ef.setFormatter(fmt)
        logger.addHandler(ef)
        cls._loggers[name] = logger
        return logger


def setup_logging(name: str = "scanner", level: str = "INFO") -> logging.Logger:
    return LogManager.get_logger(name)
