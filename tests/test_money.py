import pytest
from app.utils.money import parse_price, format_price


@pytest.mark.parametrize("raw,expected", [
    ("3 500 000 so'm", 3500000),
    ("3500000", 3500000),
    ("3,500,000", 3500000),
    ("3.500.000", 3500000),
    ("1 200 000 сум", 1200000),
    ("1200000 UZS", 1200000),
    (3500000, 3500000),
    (3500000.0, 3500000),
    (None, None),
    ("", None),
    ("narx yo'q", None),
])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_format_price_uzs():
    assert "3 500 000" in format_price(3500000)
    assert "so'm" in format_price(3500000)


def test_format_price_none():
    assert format_price(None) == "Narx ko'rsatilmagan"
