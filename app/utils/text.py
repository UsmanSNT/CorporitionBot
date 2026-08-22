import re
import hashlib
from typing import Any


def normalize_keyword(text: str) -> str:
    return text.strip().lower()


def keyword_matches(text: str, keyword: str) -> bool:
    """Case-insensitive substring match across Uzbek, Russian, Korean, English."""
    if not text or not keyword:
        return False
    return keyword.lower() in text.lower()


def make_hash(data: Any) -> str:
    return hashlib.sha256(str(data).encode()).hexdigest()


def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special)}])", r"\\\1", text)
