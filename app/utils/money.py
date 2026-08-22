import re
from typing import Optional


def parse_price(raw: str | int | float | None) -> Optional[int]:
    """Convert any price string to integer UZS. Returns None if unparseable."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)

    text = str(raw)
    # Remove currency words and common separators
    text = re.sub(r"(so['']?m|сум|uzs|usd|\$)", "", text, flags=re.IGNORECASE)
    # Remove spaces used as thousands separator
    text = re.sub(r"\s+", "", text)
    # Remove non-numeric except dot and comma
    text = re.sub(r"[^\d.,]", "", text)
    # Replace comma decimal separator with dot
    text = text.replace(",", ".")
    # If multiple dots, keep only last (e.g. "3.500.000" → "3500000")
    parts = text.split(".")
    if len(parts) > 2:
        text = "".join(parts)
    elif len(parts) == 2 and len(parts[1]) >= 3:
        # "3500.000" → 3500000 (thousands dot, not decimal)
        text = "".join(parts)

    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None


def format_price(price: Optional[int], currency: str = "UZS") -> str:
    """Format integer price for display."""
    if price is None:
        return "Narx ko'rsatilmagan"
    formatted = f"{price:,}".replace(",", " ")
    if currency.upper() in ("UZS", "SO'M", "SUM"):
        return f"{formatted} so'm"
    return f"{formatted} {currency}"
