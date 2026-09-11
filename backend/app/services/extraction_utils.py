import re
from decimal import Decimal, InvalidOperation
from typing import Iterable

from app.schemas.document import Evidence
from app.services.layout import TextRow, TextToken


NUMBER_PATTERN = re.compile(r"^\(?\s*[-+]?\s*[$₹€£]?\s*[\d.,]+\s*%?\s*\)?$")


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def parse_number(value: str) -> Decimal | None:
    original = value.strip()
    if not original or original in {"-", "--", "—", "–"}:
        return None
    negative = original.startswith("(") and original.endswith(")")
    cleaned = re.sub(r"[^0-9,.-]", "", original).strip("-")
    if not cleaned or not re.search(r"\d", cleaned):
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind(".") and len(cleaned.rsplit(",", 1)[1]) == 2:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        if cleaned.count(",") == 1 and len(cleaned.rsplit(",", 1)[1]) in {1, 2}:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(".") > 1:
        parts = cleaned.split(".")
        if len(parts[-1]) == 2:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        else:
            cleaned = "".join(parts)
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return None
    return -number if negative or original.strip().startswith("-") else number


def is_number_token(token: TextToken, allow_percent: bool = False) -> bool:
    text = token.text.strip()
    if not allow_percent and "%" in text:
        return False
    if "/" in text and not text.startswith("("):
        return False
    return bool(NUMBER_PATTERN.fullmatch(text)) and parse_number(text) is not None


def decimal_to_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def row_evidence(row: TextRow) -> Evidence:
    return Evidence(source_text=row.text, page_number=row.page_number, bounding_box=row.bounding_box)


def token_evidence(token: TextToken) -> Evidence:
    return Evidence(source_text=token.text, page_number=token.page_number, bounding_box=token.bounding_box)


def all_rows(pages: Iterable) -> list[TextRow]:
    return [row for page in pages for row in page.rows if row.text.strip()]
