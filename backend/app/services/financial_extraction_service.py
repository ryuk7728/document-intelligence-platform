import re
from collections import defaultdict
from dataclasses import dataclass

from app.schemas.document import ExtractedData, ExtractedValue, FinancialLineItem
from app.services.extraction_utils import (
    all_rows,
    compact_text,
    decimal_to_float,
    is_number_token,
    normalize_text,
    parse_number,
    row_evidence,
)
from app.services.layout import PageText, TextRow, TextToken


@dataclass(slots=True)
class PeriodColumn:
    label: str
    x_center: float
    y_center: float


SECTION_PATTERNS = {
    "capital_and_liabilities": ("capital and liabilities", "capital liabilities"),
    "assets": ("assets",),
    "income": ("income",),
    "expenditure": ("expenditure",),
    "profit": ("profit",),
    "appropriations": ("appropriations",),
    "operating_activities": ("cash flows from operating activities",),
    "investing_activities": ("cash flows from investing activities", "cash flows used in investing activities"),
    "financing_activities": ("cash flows from financing activities",),
}


class FinancialExtractionService:
    def extract(self, pages: list[PageText]) -> ExtractedData:
        fields: dict[str, ExtractedValue] = {}
        line_items: list[FinancialLineItem] = []
        source_blocks = [row_evidence(row) for row in all_rows(pages)]
        title_row = next((row for row in all_rows(pages) if "consolidated" in row.text.lower()), None)
        if title_row:
            fields["statement_title"] = ExtractedValue(value=title_row.text, evidence=row_evidence(title_row))

        periods_seen: list[str] = []
        for page in pages:
            period_columns = self._period_columns(page)
            periods_seen.extend(column.label for column in period_columns if column.label not in periods_seen)
            line_items.extend(self._extract_page_rows(page, period_columns))

        if periods_seen:
            evidence_row = next(
                (row for row in all_rows(pages) if any(period in row.text for period in periods_seen)),
                title_row,
            )
            fields["periods"] = ExtractedValue(
                value=periods_seen,
                evidence=row_evidence(evidence_row) if evidence_row else None,
            )

        currency_row = next(
            (row for row in all_rows(pages) if re.search(r"(?:₹|\brs\.?\b|\binr\b|\bcrore\b|[\"'‘’“”`]000)", row.text, re.I)),
            None,
        )
        if currency_row:
            fields["currency"] = ExtractedValue(value="INR", evidence=row_evidence(currency_row))
            if "crore" in currency_row.text.lower():
                fields["currency_scale"] = ExtractedValue(value="crore", evidence=row_evidence(currency_row))
            elif "000" in currency_row.text:
                fields["currency_scale"] = ExtractedValue(value="thousands", evidence=row_evidence(currency_row))

        for item in line_items:
            canonical = self._canonical_key(item.label, item.section)
            if canonical and canonical not in fields:
                fields[canonical] = ExtractedValue(value=item.values, evidence=item.evidence)

        tables = []
        if line_items:
            columns = ["section", "label", "schedule", *periods_seen]
            table_rows = [
                {
                    "section": item.section,
                    "label": item.label,
                    "schedule": item.schedule,
                    **item.values,
                }
                for item in line_items
            ]
            from app.schemas.document import ExtractedTable

            tables.append(
                ExtractedTable(
                    name="financial_statement_line_items",
                    columns=columns,
                    rows=table_rows,
                    page_number=line_items[0].evidence.page_number,
                )
            )
        return ExtractedData(
            fields=fields,
            financial_line_items=line_items,
            tables=tables,
            source_text_blocks=source_blocks,
        )

    def _extract_page_rows(self, page: PageText, columns: list[PeriodColumn]) -> list[FinancialLineItem]:
        if len(columns) < 1:
            return []
        items: list[FinancialLineItem] = []
        current_section: str | None = None
        unlabeled_counts: defaultdict[str, int] = defaultdict(int)
        first_value_x = min(column.x_center for column in columns)
        header_y = max(column.y_center for column in columns)
        for row in page.rows:
            if row.y_center <= header_y + 0.006:
                continue
            normalized = normalize_text(row.text)
            if any(stop in normalized for stop in ("as per our report", "for and on behalf of the board")):
                break
            section = self._section_name(normalized)
            row_numbers = self._values_for_columns(row.tokens, columns)
            if section and not row_numbers:
                current_section = section
                continue
            if not row_numbers:
                continue
            label_tokens = [
                token
                for token in row.tokens
                if token.x_center < first_value_x - 0.045
                and not self._is_schedule_only(token.text)
            ]
            label = " ".join(token.text for token in sorted(label_tokens, key=lambda token: token.x0)).strip()
            label = re.sub(r"^(?:I|II|III|IV|V|VI)\s+", "", label, flags=re.I)
            schedule = self._schedule_value(row.tokens, first_value_x)
            if not label:
                unlabeled_counts[current_section or "statement"] += 1
                label = f"Subtotal {unlabeled_counts[current_section or 'statement']}"
            item = FinancialLineItem(
                label=label,
                section=current_section,
                schedule=schedule,
                values=row_numbers,
                evidence=row_evidence(row),
            )
            items.append(item)
        return items

    @staticmethod
    def _values_for_columns(tokens: list[TextToken], columns: list[PeriodColumn]) -> dict[str, float | None]:
        values: dict[str, float | None] = {}
        numeric_tokens = [token for token in tokens if is_number_token(token)]
        for column in columns:
            matches = sorted(numeric_tokens, key=lambda token: abs(token.x_center - column.x_center))
            if matches and abs(matches[0].x_center - column.x_center) <= 0.075:
                values[column.label] = decimal_to_float(parse_number(matches[0].text))
        return values

    def _period_columns(self, page: PageText) -> list[PeriodColumn]:
        candidates: list[tuple[float, float, str]] = []
        for token in page.tokens:
            if token.x_center < 0.58 or token.y_center > 0.28:
                continue
            year = self._extract_year(token.text)
            if year:
                candidates.append((token.y_center, token.x_center, year))
        candidates.sort()
        selected: list[PeriodColumn] = []
        for y_center, x_center, label in candidates:
            if any(abs(existing.x_center - x_center) < 0.035 for existing in selected):
                continue
            selected.append(PeriodColumn(label=label, x_center=x_center, y_center=y_center))
        selected.sort(key=lambda item: item.x_center)
        return selected[:3]

    @staticmethod
    def _extract_year(text: str) -> str | None:
        full_year = re.search(r"\b(20\d{2}|19\d{2})\b", text)
        if full_year:
            return full_year.group(1)
        short_date = re.search(r"\d{1,2}[-/]?[A-Za-z]{3}[-/](\d{2})(?!\d)", text)
        if short_date:
            year = int(short_date.group(1))
            return str(2000 + year if year < 70 else 1900 + year)
        return None

    @staticmethod
    def _section_name(normalized: str) -> str | None:
        compact = normalized.replace(" ", "")
        for section, phrases in SECTION_PATTERNS.items():
            if any(phrase in normalized or phrase.replace(" ", "") in compact for phrase in phrases):
                return section
        return None

    @staticmethod
    def _is_schedule_only(text: str) -> bool:
        return bool(re.fullmatch(r"(?:\d+[A-Za-z]?|\d+\s*&\s*\d+)", text.strip()))

    @staticmethod
    def _schedule_value(tokens: list[TextToken], first_value_x: float) -> str | None:
        candidates = [
            token.text
            for token in tokens
            if 0.48 < token.x_center < first_value_x - 0.04
            and re.fullmatch(r"(?:\d+[A-Za-z]?|\d+\s*&\s*\d+)", token.text.strip())
        ]
        return candidates[-1] if candidates else None

    @staticmethod
    def _canonical_key(label: str, section: str | None) -> str | None:
        compact = compact_text(label)
        section = section or ""
        if "netcashflow" in compact and "operatingactivities" in compact:
            return "operating_cash_flow"
        if "netcashflow" in compact and "investingactivities" in compact:
            return "investing_cash_flow"
        if "netcashflow" in compact and "financingactivities" in compact:
            return "financing_cash_flow"
        if "netincreaseincashandcashequivalents" in compact:
            return "net_change_in_cash"
        if "effect" in compact and "translation" in compact and ("exchange" in compact or "foreigncurrency" in compact or "fluctuation" in compact):
            return "fx_translation_adjustment"
        if "cashandcashequivalents" in compact and "acquired" in compact:
            return "cash_acquired_adjustment"
        if "cashandcashequivalents" in compact and ("beginning" in compact or "april1" in compact):
            return "opening_cash"
        if "cashandcashequivalents" in compact and ("endoftheyear" in compact or "march31" in compact):
            return "closing_cash"
        if "profit" in compact and "attributable" in compact and ("group" in compact or "owners" in compact):
            return "net_profit_attributable_to_group"
        if "profit" in compact and "before" in compact and "minorit" in compact:
            return "profit_before_minority_interest"
        if compact.startswith("less") and "minorit" in compact:
            return "minority_interest"
        if compact == "total":
            return {
                "assets": "total_assets",
                "capital_and_liabilities": "total_capital_and_liabilities",
                "income": "total_income",
                "expenditure": "total_expenditure",
                "profit": "total_available_for_appropriation",
                "appropriations": "total_appropriations",
            }.get(section)
        aliases = {
            "interestearned": "interest_earned",
            "otherincome": "other_income",
            "interestexpended": "interest_expended",
            "operatingexpenses": "operating_expenses",
            "provisionsandcontingencies": "provisions_and_contingencies",
            "netprofitfortheyear": "net_profit_for_year",
            "consolidatednetprofitfortheyearbeforeminoritiesinterest": "profit_before_minority_interest",
            "lessminorityinterest": "minority_interest",
            "minorityinterest": "minority_interest",
            "consolidatedprofitfortheyearattributabletothegroup": "net_profit_attributable_to_group",
            "consolidatednetprofitfortheyearattributabletothegroup": "net_profit_attributable_to_group",
            "addshareinprofitsofassociates": "share_of_associates",
            "balanceinprofitandlossaccountbroughtforward": "brought_forward_profit",
            "netcashflowusedinfromoperatingactivities": "operating_cash_flow",
            "netcashflowfromoperatingactivities": "operating_cash_flow",
            "netcashflowusedininvestingactivities": "investing_cash_flow",
            "netcashflowfromusedinfinancingactivities": "financing_cash_flow",
            "netcashflowfromfinancingactivities": "financing_cash_flow",
            "effectofexchangefluctuationontranslationreserve": "fx_translation_adjustment",
            "netincreaseincashandcashequivalents": "net_change_in_cash",
            "cashandcashequivalentsasatapril1st": "opening_cash",
            "cashandcashequivalentsasmarch31st": "closing_cash",
            "cashandcashequivalentsasatmarch31st": "closing_cash",
        }
        if compact in aliases:
            return aliases[compact]
        for candidate in sorted(aliases, key=len, reverse=True):
            canonical = aliases[candidate]
            if candidate in compact:
                return canonical
        return None
