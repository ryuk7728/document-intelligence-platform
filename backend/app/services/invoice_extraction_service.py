import re
from decimal import Decimal

from app.schemas.document import ExtractedData, ExtractedTable, ExtractedValue, InvoiceLineItem
from app.services.extraction_utils import (
    all_rows,
    compact_text,
    decimal_to_float,
    is_number_token,
    normalize_text,
    parse_number,
    row_evidence,
    token_evidence,
)
from app.services.layout import PageText, TextRow, TextToken


class InvoiceExtractionService:
    def extract(self, pages: list[PageText]) -> ExtractedData:
        rows = all_rows(pages)
        fields: dict[str, ExtractedValue] = {}
        self._extract_identifiers(rows, fields)
        self._extract_parties(pages, fields)
        self._extract_currency(rows, fields)
        self._extract_totals(rows, fields)
        line_items = self._extract_line_items(pages)

        if "subtotal" not in fields and line_items:
            subtotal = sum(
                (Decimal(str(item.net_amount)) for item in line_items if item.net_amount is not None),
                Decimal("0"),
            )
            if subtotal:
                fields["calculated_line_item_subtotal"] = ExtractedValue(value=float(subtotal))

        tables = []
        if line_items:
            table_rows = [item.model_dump(exclude={"evidence"}) for item in line_items]
            tables.append(
                ExtractedTable(
                    name="invoice_line_items",
                    columns=list(table_rows[0].keys()),
                    rows=table_rows,
                    page_number=line_items[0].evidence.page_number,
                )
            )
        return ExtractedData(
            fields=fields,
            line_items=line_items,
            tables=tables,
            source_text_blocks=[row_evidence(row) for row in rows],
        )

    @staticmethod
    def _extract_identifiers(rows: list[TextRow], fields: dict[str, ExtractedValue]) -> None:
        invoice_patterns = (
            re.compile(r"invoice\s*(?:no|number|#)\s*[:#.-]?\s*([A-Z0-9][A-Z0-9/.-]{1,})", re.I),
            re.compile(r"invoice\s*[:#]\s*([A-Z0-9][A-Z0-9/.-]{1,})(?![^\s]*@)", re.I),
            re.compile(r"\bTRN\s*[:#.-]?\s*([A-Z0-9][A-Z0-9/.-]{2,})", re.I),
        )
        date_patterns = (
            re.compile(r"(?:date(?:\s+of\s+issue)?|dated)\s*[:.-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I),
            re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"),
            re.compile(r"\b(\d{1,2}-(?:[A-Za-z]{3}|\d{1,2})-\d{2,4})\b"),
            re.compile(
                r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
                r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
                r"\s+\d{1,2},\s+\d{4})\b",
                re.I,
            ),
        )
        for row in rows:
            if "invoice_number" not in fields:
                for pattern in invoice_patterns:
                    match = pattern.search(row.text)
                    if match and match.group(1).lower() not in {"printed", "date", "dated", "for", "tax", "no"}:
                        fields["invoice_number"] = ExtractedValue(value=match.group(1), evidence=row_evidence(row))
                        break
            if "invoice_date" not in fields:
                for pattern in date_patterns:
                    match = pattern.search(row.text)
                    if match:
                        fields["invoice_date"] = ExtractedValue(value=match.group(1), evidence=row_evidence(row))
                        break

    def _extract_parties(self, pages: list[PageText], fields: dict[str, ExtractedValue]) -> None:
        tokens = [token for page in pages for token in page.tokens]
        if "invoice_number" not in fields:
            number_token = self._value_below(
                tokens,
                ("invoice no", "invoice number"),
                side="any",
                allow_identifier=True,
            )
            if number_token:
                fields["invoice_number"] = ExtractedValue(value=number_token.text, evidence=token_evidence(number_token))
        vendor = self._value_below(tokens, ("seller", "vendor", "supplier", "bill from"), side="left")
        customer = self._value_below(tokens, ("client", "buyer", "bill to", "consignee"), side="any")
        if vendor:
            fields["vendor_name"] = ExtractedValue(value=vendor.text, evidence=token_evidence(vendor))
        if customer:
            fields["customer_name"] = ExtractedValue(value=customer.text, evidence=token_evidence(customer))
        if "vendor_name" not in fields:
            exclusions = (
                "invoice", "date", "tax", "gst", "items", "summary", "receipt", "printed", "delivery",
                "sales man", "reference", "consignee", "buyer", "contact", "state name", "email", "terms",
            )
            broad_candidates = [
                token
                for token in sorted(tokens, key=lambda item: (item.page_number, item.y0, item.x0))
                if token.page_number == 1
                and token.y0 < 0.4
                and len(re.sub(r"[^A-Za-z]", "", token.text)) >= 4
                and not any(word in token.text.lower() for word in exclusions)
            ]
            business_candidate = next(
                (
                    token
                    for token in broad_candidates
                    if re.search(r"\b(?:plc|inc|ltd|limited|market|enterprise|electronics|company|sdn|bhd|store|shop)\b", token.text, re.I)
                ),
                None,
            )
            early_candidate = next(
                (
                    token
                    for token in broad_candidates
                    if token.y0 < 0.12 and token.x_center < 0.6 and not re.match(r"^\s*\d", token.text)
                ),
                None,
            )
            candidate = business_candidate or early_candidate
            if candidate:
                fields["vendor_name"] = ExtractedValue(value=candidate.text, evidence=token_evidence(candidate))

    @staticmethod
    def _value_below(
        tokens: list[TextToken],
        labels: tuple[str, ...],
        side: str,
        allow_identifier: bool = False,
    ) -> TextToken | None:
        label_token = next(
            (token for token in tokens if any(label in normalize_text(token.text) for label in labels)),
            None,
        )
        if not label_token:
            return None
        candidates = []
        for token in tokens:
            if token.page_number != label_token.page_number or token.y0 <= label_token.y0:
                continue
            if token.y0 - label_token.y1 > 0.12:
                continue
            if side == "left" and token.x_center > 0.55:
                continue
            if abs(token.x_center - label_token.x_center) > 0.28:
                continue
            normalized = normalize_text(token.text)
            if any(label in normalized for label in labels):
                continue
            if allow_identifier:
                if not re.search(r"\d", token.text) or len(token.text.strip()) < 3:
                    continue
            else:
                if len(re.sub(r"[^A-Za-z]", "", token.text)) < 3:
                    continue
                if re.search(r"(?:GSTIN|UIN|Tax\s*Id|@|\bcode\b|\bcontact\b|\bstate\b)", token.text, re.I):
                    continue
            candidates.append(token)
        return min(candidates, key=lambda token: (token.y0 - label_token.y1, abs(token.x0 - label_token.x0))) if candidates else None

    @staticmethod
    def _extract_currency(rows: list[TextRow], fields: dict[str, ExtractedValue]) -> None:
        joined = "\n".join(row.text for row in rows)
        currency = None
        evidence = None
        rules = (
            (r"(?:₹|\bINR\b|\bGSTIN\b|\bCGST\b|\bSGST\b)", "INR"),
            (r"(?:\bRM\b|\bMYR\b|Malaysia)", "MYR"),
            (r"(?:\$|\bUSD\b)", "USD"),
            (r"(?:€|\bEUR\b)", "EUR"),
            (r"(?:£|\bGBP\b)", "GBP"),
        )
        for pattern, code in rules:
            if re.search(pattern, joined, re.I):
                currency = code
                evidence = next((row_evidence(row) for row in rows if re.search(pattern, row.text, re.I)), None)
                break
        if currency:
            fields["currency"] = ExtractedValue(value=currency, evidence=evidence)

    @staticmethod
    def _extract_totals(rows: list[TextRow], fields: dict[str, ExtractedValue]) -> None:
        total_candidates: list[tuple[Decimal, TextRow]] = []
        for row in rows:
            normalized = normalize_text(row.text)
            numeric_tokens = [token for token in row.tokens if is_number_token(token)]
            numbers = [parse_number(token.text) for token in numeric_tokens]
            numbers = [number for number in numbers if number is not None]
            if not numbers:
                continue
            if "subtotal" in normalized:
                fields["subtotal"] = ExtractedValue(value=decimal_to_float(numbers[-1]), evidence=row_evidence(row))
            if "discount" in normalized or "disc " in f"{normalized} ":
                fields["discount"] = ExtractedValue(value=decimal_to_float(numbers[-1]), evidence=row_evidence(row))
            if "shipping" in normalized or "handling" in normalized or normalized.startswith("s h"):
                fields["shipping_amount"] = ExtractedValue(value=decimal_to_float(numbers[-1]), evidence=row_evidence(row))
            if (
                re.search(r"\b(?:tax|vat|gst|cgst|sgst)\b", normalized)
                and not any(word in normalized for word in ("total", "subtotal", "summary", "taxable", "includes"))
            ):
                fields["tax_amount"] = ExtractedValue(value=decimal_to_float(numbers[-1]), evidence=row_evidence(row))
            if normalized.startswith("cash") or "cash paid" in normalized:
                fields["cash_paid"] = ExtractedValue(value=decimal_to_float(numbers[-1]), evidence=row_evidence(row))
            if normalized.startswith("change"):
                fields["change"] = ExtractedValue(value=decimal_to_float(numbers[-1]), evidence=row_evidence(row))
            if (
                "total includes" in normalized
                or "total inclusive" in normalized
                or "tax included" in normalized
                or "inclusive gst" in normalized
            ):
                fields["tax_included"] = ExtractedValue(value=True, evidence=row_evidence(row))
            if "total" in normalized and "total qty" not in normalized:
                if normalized.startswith("total") and len(numbers) >= 3:
                    fields.setdefault("subtotal", ExtractedValue(value=decimal_to_float(numbers[-3]), evidence=row_evidence(row)))
                    fields.setdefault("tax_amount", ExtractedValue(value=decimal_to_float(numbers[-2]), evidence=row_evidence(row)))
                total_candidates.append((max(numbers), row))
        if total_candidates:
            value, evidence_row = max(total_candidates, key=lambda item: item[0])
            fields["total_amount"] = ExtractedValue(value=float(value), evidence=row_evidence(evidence_row))
        # Receipt printers frequently render a tax-inclusive total poorly while the
        # card-tender line remains legible. Use that corroborating source only when
        # it agrees with the printed subtotal, so a larger cash tender is not
        # mistaken for the sale total.
        subtotal_field = fields.get("subtotal")
        total_field = fields.get("total_amount")
        if "tax_included" in fields and subtotal_field and total_field:
            subtotal = Decimal(str(subtotal_field.value))
            total = Decimal(str(total_field.value))
            if abs(total - subtotal) > Decimal("0.01"):
                for row in rows:
                    normalized = normalize_text(row.text)
                    if not re.match(r"^(?:master(?:card)?|visa|amex|card|debit|credit)\b", normalized):
                        continue
                    amounts = [parse_number(token.text) for token in row.tokens if is_number_token(token)]
                    amounts = [amount for amount in amounts if amount is not None]
                    if amounts and abs(amounts[-1] - subtotal) <= Decimal("0.01"):
                        fields["total_amount"] = ExtractedValue(
                            value=decimal_to_float(amounts[-1]),
                            evidence=row_evidence(row),
                        )
                        break

    def _extract_line_items(self, pages: list[PageText]) -> list[InvoiceLineItem]:
        items: list[InvoiceLineItem] = []
        for page in pages:
            rows = page.rows
            header_index = next(
                (
                    index
                    for index, row in enumerate(rows)
                    if ("qty" in compact_text(row.text) or "quantity" in normalize_text(row.text))
                    and any(term in normalize_text(row.text) for term in ("description", "item", "amount", "price", "worth"))
                ),
                None,
            )
            if header_index is not None:
                items.extend(self._tabular_items(rows, header_index))
            if not items:
                items.extend(self._receipt_items(rows))
        return items

    def _tabular_items(self, rows: list[TextRow], header_index: int) -> list[InvoiceLineItem]:
        header = rows[header_index]
        anchors = self._column_anchors(header.tokens)
        if "quantity" not in anchors or "description" not in anchors:
            return []
        results: list[InvoiceLineItem] = []
        for row in rows[header_index + 1 :]:
            normalized = normalize_text(row.text)
            if any(stop in normalized for stop in ("summary", "subtotal", "net total", "amount chargeable")):
                break
            serial = next(
                (token for token in row.tokens if token.x_center < anchors["description"] and re.fullmatch(r"\d+[.]?", token.text.strip())),
                None,
            )
            if not serial:
                if results:
                    continuation = " ".join(
                        token.text
                        for token in row.tokens
                        if token.x_center < anchors["quantity"] - 0.04 and not is_number_token(token)
                    ).strip()
                    if continuation:
                        results[-1].description = f"{results[-1].description or ''} {continuation}".strip()
                continue
            assigned = self._assign_to_columns(row.tokens, anchors)
            description = " ".join(token.text for token in assigned.get("description", [])).strip() or None
            quantity = self._first_number(assigned.get("quantity", []))
            unit_price = self._first_number(assigned.get("unit_price", []))
            net_amount = self._first_number(assigned.get("net_amount", []))
            amount = self._first_number(assigned.get("amount", []))
            tax_rate = self._first_number(assigned.get("tax_rate", []), allow_percent=True)
            unit = " ".join(token.text for token in assigned.get("unit", [])).strip() or None
            results.append(
                InvoiceLineItem(
                    description=description,
                    quantity=quantity,
                    unit=unit,
                    unit_price=unit_price,
                    net_amount=net_amount,
                    tax_rate=tax_rate,
                    amount=amount or net_amount,
                    evidence=row_evidence(row),
                )
            )
        return results

    @staticmethod
    def _column_anchors(tokens: list[TextToken]) -> dict[str, float]:
        anchors: dict[str, float] = {}
        for token in tokens:
            compact = compact_text(token.text)
            normalized = normalize_text(token.text)
            if "description" in normalized or compact == "item":
                anchors["description"] = token.x_center
            elif compact in {"qty", "quantity"}:
                anchors["quantity"] = token.x_center
            elif compact in {"um", "uom", "unit"}:
                anchors["unit"] = token.x_center
            elif "netprice" in compact or "uprice" in compact or compact == "rate":
                anchors["unit_price"] = token.x_center
            elif "networth" in compact:
                anchors["net_amount"] = token.x_center
            elif "vat" in compact or "gst" in compact:
                anchors["tax_rate"] = token.x_center
            elif "gross" in compact or compact in {"amount", "amt"}:
                anchors["amount"] = token.x_center
        return anchors

    @staticmethod
    def _assign_to_columns(tokens: list[TextToken], anchors: dict[str, float]) -> dict[str, list[TextToken]]:
        assigned: dict[str, list[TextToken]] = {column: [] for column in anchors}
        ordered = sorted(anchors.items(), key=lambda item: item[1])
        for token in tokens:
            if re.fullmatch(r"\d+[.]?", token.text.strip()) and token.x_center < anchors.get("description", 0):
                continue
            column = min(ordered, key=lambda item: abs(token.x_center - item[1]))[0]
            assigned[column].append(token)
        return assigned

    @staticmethod
    def _first_number(tokens: list[TextToken], allow_percent: bool = False) -> float | None:
        for token in tokens:
            if is_number_token(token, allow_percent=allow_percent):
                value = parse_number(token.text)
                return decimal_to_float(value)
        return None

    @staticmethod
    def _receipt_items(rows: list[TextRow]) -> list[InvoiceLineItem]:
        pattern = re.compile(
            r"^\s*(?P<qty>\d+(?:[.,]\d+)?)\s+(?P<description>.+?)\s+@?\s*(?P<unit>\d+[.,]\d{2})\s+(?P<amount>\d+[.,]\d{2})(?:\s|$)",
            re.I,
        )
        items = []
        for row in rows:
            match = pattern.search(row.text)
            if not match:
                continue
            items.append(
                InvoiceLineItem(
                    description=match.group("description").strip(),
                    quantity=decimal_to_float(parse_number(match.group("qty"))),
                    unit_price=decimal_to_float(parse_number(match.group("unit"))),
                    net_amount=decimal_to_float(parse_number(match.group("amount"))),
                    amount=decimal_to_float(parse_number(match.group("amount"))),
                    evidence=row_evidence(row),
                )
            )
        return items
