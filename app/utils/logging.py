import logging
import sys
import os
from logging.handlers import RotatingFileHandler

from app.config import config


def setup_logging() -> None:
    os.makedirs("logs", exist_ok=True)

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File (rotate at 5MB, keep 3 backups)
    file_handler = RotatingFileHandler(
        "logs/cooperation-bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
