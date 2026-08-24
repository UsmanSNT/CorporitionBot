import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_USER_ID: int = int(os.getenv("TELEGRAM_ADMIN_USER_ID", "0"))
    TELEGRAM_EXTRA_USER_IDS: list[int] = [
        int(x) for x in os.getenv("TELEGRAM_EXTRA_USER_IDS", "").split(",") if x.strip()
    ]
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/cooperation.db")
    CHECK_INTERVAL_MINUTES: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    COOPERATION_BASE_URL: str = os.getenv("COOPERATION_BASE_URL", "https://cooperation.uz")
    NEW_COOPERATION_BASE_URL: str = os.getenv("NEW_COOPERATION_BASE_URL", "https://new.cooperation.uz")
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Tashkent")

    def validate(self) -> None:
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required in .env")
        if not self.TELEGRAM_ADMIN_USER_ID:
            raise ValueError("TELEGRAM_ADMIN_USER_ID is required in .env")


config = Config()
