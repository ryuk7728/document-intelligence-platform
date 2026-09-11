from decimal import Decimal

from app.core.config import Settings, get_settings
from app.schemas.document import (
    DocumentType,
    ExtractedData,
    FinancialValidation,
    ValidationCheck,
)


class FinancialValidationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate(self, document_type: DocumentType, data: ExtractedData) -> FinancialValidation:
        if document_type == DocumentType.INVOICE:
            checks = self._invoice_checks(data)
        elif document_type == DocumentType.BALANCE_SHEET:
            checks = self._balance_sheet_checks(data)
        elif document_type == DocumentType.PROFIT_AND_LOSS:
            checks = self._profit_and_loss_checks(data)
        else:
            checks = self._cash_flow_checks(data)
        if any(check.status == "FAIL" for check in checks):
            overall = "FAIL"
        elif any(check.status == "PASS" for check in checks):
            overall = "PASS"
        else:
            overall = "NOT_APPLICABLE"
        issues = [check.message or check.name for check in checks if check.status == "FAIL"]
        return FinancialValidation(checks=checks, overall_status=overall, issues=issues)

    def _invoice_checks(self, data: ExtractedData) -> list[ValidationCheck]:
        checks: list[ValidationCheck] = []
        for index, item in enumerate(data.line_items, start=1):
            reported = item.net_amount if item.net_amount is not None else item.amount
            operands = {"quantity": item.quantity, "unit_price": item.unit_price}
            if item.quantity is None or item.unit_price is None or reported is None:
                checks.append(
                    self._not_applicable(
                        f"invoice_line_{index}_amount_check",
                        "quantity * unit_price",
                        operands=operands,
                        reported=reported,
                    )
                )
            else:
                calculated = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
                reported_decimal = self._decimal(reported)
                relative_gap = abs(calculated - reported_decimal) / max(abs(reported_decimal), Decimal("1"))
                if item.quantity > 10000 or relative_gap > Decimal("0.03"):
                    check = self._not_applicable(
                        f"invoice_line_{index}_amount_check",
                        "quantity * unit_price",
                        operands=operands,
                        reported=reported,
                    )
                    check.message = "Extracted columns are not reliable enough for an arithmetic decision."
                    checks.append(check)
                else:
                    checks.append(
                        self._compare(
                            f"invoice_line_{index}_amount_check",
                            "quantity * unit_price",
                            operands,
                            calculated,
                            reported_decimal,
                        )
                    )
        subtotal = self._scalar(data, "subtotal")
        tax = self._scalar(data, "tax_amount")
        discount = self._scalar(data, "discount")
        shipping = self._scalar(data, "shipping_amount")
        total = self._scalar(data, "total_amount")
        tax_included_field = data.fields.get("tax_included")
        tax_included = bool(tax_included_field and tax_included_field.value is True)
        total_operands = {
            "subtotal": subtotal,
            "tax_amount": tax,
            "discount": 0.0 if discount is None else discount,
            "shipping_amount": 0.0 if shipping is None else shipping,
        }
        if subtotal is None or total is None or (tax is None and not tax_included):
            checks.append(
                self._not_applicable(
                    "invoice_total_check",
                    "subtotal + tax_amount + shipping_amount - discount",
                    operands=total_operands,
                    reported=total,
                )
            )
        else:
            calculated_total = Decimal(str(subtotal))
            formula = "subtotal"
            if not tax_included:
                calculated_total += Decimal(str(tax))
                formula += " + tax_amount"
            calculated_total += Decimal(str(total_operands["shipping_amount"]))
            calculated_total -= Decimal(str(total_operands["discount"]))
            formula += " + shipping_amount - discount"
            checks.append(
                self._compare(
                    "invoice_total_check",
                    formula,
                    total_operands,
                    calculated_total,
                    self._decimal(total),
                )
            )
        line_checks = [
            check
            for check in checks
            if check.name.startswith("invoice_line_") and check.name.endswith("_amount_check")
        ]
        if data.line_items and line_checks and all(check.status == "PASS" for check in line_checks):
            line_total_values = [
                item.net_amount if item.net_amount is not None else item.amount
                for item in data.line_items
            ]
            if all(value is not None for value in line_total_values):
                calculated = sum(Decimal(str(value)) for value in line_total_values if value is not None)
                subtotal_decimal = self._decimal(subtotal)
                if subtotal_decimal is not None:
                    relative_gap = abs(calculated - subtotal_decimal) / max(abs(subtotal_decimal), Decimal("1"))
                    if relative_gap > Decimal("0.03"):
                        check = self._not_applicable(
                            "invoice_line_items_to_subtotal_check",
                            "sum(line_item_amounts)",
                            operands={"line_item_sum": float(calculated)},
                            reported=subtotal,
                        )
                        check.message = "The extracted line-item set may be incomplete; no reconciliation decision was made."
                        checks.append(check)
                    else:
                        checks.append(
                            self._compare(
                                name="invoice_line_items_to_subtotal_check",
                                formula="sum(line_item_amounts)",
                                operands={"line_item_sum": float(calculated)},
                                calculated=calculated,
                                reported=subtotal_decimal,
                            )
                        )
        cash_paid = self._scalar(data, "cash_paid")
        change = self._scalar(data, "change")
        change_operands = {"cash_paid": cash_paid, "total_amount": total}
        if cash_paid is None or total is None or change is None:
            checks.append(
                self._not_applicable(
                    "invoice_change_check",
                    "cash_paid - total_amount",
                    operands=change_operands,
                    reported=change,
                )
            )
        else:
            calculated_change = Decimal(str(cash_paid)) - Decimal(str(total))
            reported_change = self._decimal(change)
            relative_gap = abs(calculated_change - reported_change) / max(abs(calculated_change), Decimal("1"))
            if relative_gap > Decimal("0.05"):
                check = self._not_applicable(
                    "invoice_change_check",
                    "cash_paid - total_amount",
                    operands=change_operands,
                    reported=change,
                )
                check.message = "The OCR payment or change value is not reliable enough for a decision."
                checks.append(check)
            else:
                checks.append(
                    self._compare(
                        "invoice_change_check",
                        "cash_paid - total_amount",
                        change_operands,
                        calculated_change,
                        reported_change,
                    )
                )
        return checks

    def _balance_sheet_checks(self, data: ExtractedData) -> list[ValidationCheck]:
        assets = self._period_values(data, "total_assets")
        liabilities = self._period_values(data, "total_capital_and_liabilities")
        periods = sorted(set(assets) | set(liabilities), reverse=True)
        return [
            self._check(
                name="balance_sheet_equation",
                period=period,
                formula="total_capital_and_liabilities - total_assets",
                operands={"total_capital_and_liabilities": liabilities.get(period)},
                reported=assets.get(period),
            )
            for period in periods
        ] or [self._not_applicable("balance_sheet_equation", "total_capital_and_liabilities = total_assets")]

    def _profit_and_loss_checks(self, data: ExtractedData) -> list[ValidationCheck]:
        fields = {
            name: self._period_values(data, name)
            for name in (
                "interest_earned",
                "other_income",
                "total_income",
                "interest_expended",
                "operating_expenses",
                "provisions_and_contingencies",
                "total_expenditure",
                "profit_before_minority_interest",
                "net_profit_for_year",
                "minority_interest",
                "share_of_associates",
                "net_profit_attributable_to_group",
                "brought_forward_profit",
                "total_available_for_appropriation",
            )
        }
        periods = sorted({period for values in fields.values() for period in values}, reverse=True)
        checks: list[ValidationCheck] = []
        for period in periods:
            checks.extend(
                [
                    self._check(
                        "profit_loss_total_income",
                        "interest_earned + other_income",
                        {
                            "interest_earned": fields["interest_earned"].get(period),
                            "other_income": fields["other_income"].get(period),
                        },
                        fields["total_income"].get(period),
                        period=period,
                    ),
                    self._check(
                        "profit_loss_total_expenditure",
                        "interest_expended + operating_expenses + provisions_and_contingencies",
                        {
                            "interest_expended": fields["interest_expended"].get(period),
                            "operating_expenses": fields["operating_expenses"].get(period),
                            "provisions_and_contingencies": fields["provisions_and_contingencies"].get(period),
                        },
                        fields["total_expenditure"].get(period),
                        period=period,
                    ),
                    self._check(
                        "profit_loss_profit_before_minority",
                        "total_income - total_expenditure",
                        {
                            "total_income": fields["total_income"].get(period),
                            "total_expenditure": self._negate(fields["total_expenditure"].get(period)),
                        },
                        fields["profit_before_minority_interest"].get(period),
                        period=period,
                    ),
                ]
            )
            profit_before = fields["profit_before_minority_interest"].get(period)
            net_profit_for_year = fields["net_profit_for_year"].get(period)
            associates = fields["share_of_associates"].get(period)
            if profit_before is not None:
                attributable_operands = {
                    "profit_before_minority_interest": profit_before,
                    "minority_interest": self._negate(fields["minority_interest"].get(period)),
                }
                attributable_formula = "profit_before_minority_interest - minority_interest"
            else:
                attributable_operands = {
                    "net_profit_for_year": net_profit_for_year,
                    "minority_interest": self._negate(fields["minority_interest"].get(period)),
                    "share_of_associates": associates,
                }
                attributable_formula = "net_profit_for_year - minority_interest + share_of_associates"
            checks.append(
                self._check(
                    "profit_loss_attributable_profit",
                    attributable_formula,
                    attributable_operands,
                    fields["net_profit_attributable_to_group"].get(period),
                    period=period,
                )
            )
        return checks or [self._not_applicable("profit_loss_validation", "Required profit and loss fields are unavailable.")]

    def _cash_flow_checks(self, data: ExtractedData) -> list[ValidationCheck]:
        names = (
            "operating_cash_flow",
            "investing_cash_flow",
            "financing_cash_flow",
            "fx_translation_adjustment",
            "net_change_in_cash",
            "opening_cash",
            "closing_cash",
            "cash_acquired_adjustment",
        )
        fields = {name: self._period_values(data, name) for name in names}
        periods = sorted({period for values in fields.values() for period in values}, reverse=True)
        checks: list[ValidationCheck] = []
        for period in periods:
            checks.append(
                self._check(
                    "cash_flow_net_change",
                    "operating_cash_flow + investing_cash_flow + financing_cash_flow + fx_translation_adjustment",
                    {
                        "operating_cash_flow": fields["operating_cash_flow"].get(period),
                        "investing_cash_flow": fields["investing_cash_flow"].get(period),
                        "financing_cash_flow": fields["financing_cash_flow"].get(period),
                        "fx_translation_adjustment": fields["fx_translation_adjustment"].get(period),
                    },
                    fields["net_change_in_cash"].get(period),
                    period=period,
                )
            )
            acquired = fields["cash_acquired_adjustment"].get(period)
            checks.append(
                self._check(
                    "cash_flow_closing_cash",
                    "opening_cash + net_change_in_cash + cash_acquired_adjustment",
                    {
                        "opening_cash": fields["opening_cash"].get(period),
                        "net_change_in_cash": fields["net_change_in_cash"].get(period),
                        "cash_acquired_adjustment": 0.0 if acquired is None else acquired,
                    },
                    fields["closing_cash"].get(period),
                    period=period,
                )
            )
        return checks or [self._not_applicable("cash_flow_validation", "Required cash flow fields are unavailable.")]

    def _check(
        self,
        name: str,
        formula: str,
        operands: dict[str, float | None],
        reported: float | None,
        period: str | None = None,
        required: tuple[str, ...] | None = None,
    ) -> ValidationCheck:
        required_names = required or tuple(operands)
        if reported is None or any(operands.get(key) is None for key in required_names):
            return self._not_applicable(name, formula, period, operands, reported)
        calculated = sum(Decimal(str(value)) for value in operands.values() if value is not None)
        return self._compare(name, formula, operands, calculated, self._decimal(reported), period)

    def _compare(
        self,
        name: str,
        formula: str,
        operands: dict[str, float | None],
        calculated: Decimal,
        reported: Decimal | None,
        period: str | None = None,
    ) -> ValidationCheck:
        if reported is None:
            return self._not_applicable(name, formula, period, operands, None)
        variance = calculated - reported
        tolerance = max(
            Decimal(str(self.settings.financial_absolute_tolerance)),
            abs(reported) * Decimal(str(self.settings.financial_relative_tolerance)),
        )
        status = "PASS" if abs(variance) <= tolerance else "FAIL"
        return ValidationCheck(
            name=name,
            period=period,
            formula=formula,
            operands=operands,
            calculated_value=float(calculated),
            reported_value=float(reported),
            variance=float(variance),
            status=status,
            message=None if status == "PASS" else f"{name} variance {float(variance):.4f} exceeds tolerance {float(tolerance):.4f}.",
        )

    @staticmethod
    def _not_applicable(
        name: str,
        formula: str,
        period: str | None = None,
        operands: dict[str, float | None] | None = None,
        reported: float | None = None,
    ) -> ValidationCheck:
        return ValidationCheck(
            name=name,
            period=period,
            formula=formula,
            operands=operands or {},
            reported_value=reported,
            status="NOT_APPLICABLE",
            message="Required source fields are not available; no value was inferred.",
        )

    @staticmethod
    def _scalar(data: ExtractedData, name: str) -> float | None:
        field = data.fields.get(name)
        return field.value if field and isinstance(field.value, (int, float)) else None

    @staticmethod
    def _period_values(data: ExtractedData, name: str) -> dict[str, float | None]:
        field = data.fields.get(name)
        if not field or not isinstance(field.value, dict):
            return {}
        return {str(period): value for period, value in field.value.items() if isinstance(value, (int, float)) or value is None}

    @staticmethod
    def _decimal(value: float | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    @staticmethod
    def _negate(value: float | None) -> float | None:
        return None if value is None else -value
