import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN: str = os.getenv("OB_BOT_TOKEN", "")
    PROJECT_TITLE: str = os.getenv("OB_PROJECT_TITLE", "Loyiha")
    PROJECT_ID: str = os.getenv("OB_PROJECT_ID", "")
    PROJECT_REGION: str = os.getenv("OB_PROJECT_REGION", "")
    PROJECT_DESCRIPTION: str = os.getenv("OB_PROJECT_DESCRIPTION", "")
    VOTE_URL: str = os.getenv("OB_VOTE_URL", "https://openbudget.uz")
    ADMIN_IDS: list[int] = [
        int(x) for x in os.getenv("OB_ADMIN_IDS", "").split(",") if x.strip()
    ]
    VOTING_DEADLINE: str = os.getenv("OB_VOTING_DEADLINE", "")
    TIMEZONE: str = os.getenv("OB_TIMEZONE", "Asia/Tashkent")
    DB_PATH: str = os.getenv("OB_DB_PATH", "data/open_budget.db")
    IMAGE_DIR: str = os.getenv("OB_IMAGE_DIR", "")
    BOT_USERNAME: str = os.getenv("OB_BOT_USERNAME", "")
    DEADLINE_DATE: str = os.getenv("OB_DEADLINE_DATE", "")  # YYYY-MM-DD

    def validate(self):
        if not self.BOT_TOKEN:
            raise ValueError("OB_BOT_TOKEN is required")
        if not self.VOTE_URL:
            raise ValueError("OB_VOTE_URL is required")


config = Config()
