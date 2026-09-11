from decimal import Decimal

from app.services.extraction_utils import parse_number


def test_parse_number_handles_financial_formats() -> None:
    assert parse_number("8,923,441,607") == Decimal("8923441607")
    assert parse_number("(11,959.57)") == Decimal("-11959.57")
    assert parse_number("126,27") == Decimal("126.27")
    assert parse_number("$138.90") == Decimal("138.90")
    assert parse_number("-") is None

