from app.schemas.document import (
    DocumentType,
    ExtractedData,
    ExtractedValue,
    InvoiceLineItem,
    Evidence,
)
from app.services.financial_validation_service import FinancialValidationService


EVIDENCE = Evidence(source_text="test", page_number=1)


def field(value):
    return ExtractedValue(value=value, evidence=EVIDENCE)


def test_invoice_reconciliation_passes() -> None:
    data = ExtractedData(
        fields={
            "subtotal": field(100.0),
            "tax_amount": field(10.0),
            "discount": field(5.0),
            "total_amount": field(105.0),
        },
        line_items=[
            InvoiceLineItem(
                description="Service",
                quantity=2,
                unit_price=50,
                net_amount=100,
                amount=110,
                evidence=EVIDENCE,
            )
        ],
    )

    result = FinancialValidationService().validate(DocumentType.INVOICE, data)

    assert result.overall_status == "PASS"
    assert next(check for check in result.checks if check.name == "invoice_total_check").variance == 0
    assert next(check for check in result.checks if check.name == "invoice_line_1_amount_check").status == "PASS"


def test_invoice_failure_is_detected() -> None:
    data = ExtractedData(
        fields={
            "subtotal": field(100.0),
            "tax_amount": field(10.0),
            "total_amount": field(150.0),
        }
    )

    result = FinancialValidationService().validate(DocumentType.INVOICE, data)

    assert result.overall_status == "FAIL"
    check = next(check for check in result.checks if check.name == "invoice_total_check")
    assert check.status == "FAIL"
    assert check.variance == -40.0


def test_invoice_total_includes_shipping() -> None:
    data = ExtractedData(
        fields={
            "subtotal": field(135.0),
            "tax_amount": field(12.48),
            "shipping_amount": field(10.0),
            "total_amount": field(157.48),
        }
    )

    result = FinancialValidationService().validate(DocumentType.INVOICE, data)

    check = next(check for check in result.checks if check.name == "invoice_total_check")
    assert check.status == "PASS"
    assert check.calculated_value == 157.48


def test_tax_inclusive_invoice_does_not_add_tax_twice() -> None:
    data = ExtractedData(
        fields={
            "subtotal": field(29.0),
            "tax_amount": field(1.64),
            "tax_included": field(True),
            "total_amount": field(29.0),
        }
    )

    result = FinancialValidationService().validate(DocumentType.INVOICE, data)

    check = next(check for check in result.checks if check.name == "invoice_total_check")
    assert check.status == "PASS"
    assert check.formula == "subtotal + shipping_amount - discount"


def test_missing_invoice_values_are_not_applicable() -> None:
    result = FinancialValidationService().validate(DocumentType.INVOICE, ExtractedData())

    assert result.overall_status == "NOT_APPLICABLE"
    assert all(check.status == "NOT_APPLICABLE" for check in result.checks)


def test_balance_sheet_validates_each_period() -> None:
    data = ExtractedData(
        fields={
            "total_assets": field({"2024": 1000.0, "2023": 900.0}),
            "total_capital_and_liabilities": field({"2024": 1000.0, "2023": 900.0}),
        }
    )

    result = FinancialValidationService().validate(DocumentType.BALANCE_SHEET, data)

    assert result.overall_status == "PASS"
    assert {check.period for check in result.checks} == {"2024", "2023"}


def test_cash_flow_parentheses_and_closing_cash_equations() -> None:
    data = ExtractedData(
        fields={
            "operating_cash_flow": field({"2024": 100.0}),
            "investing_cash_flow": field({"2024": -25.0}),
            "financing_cash_flow": field({"2024": 10.0}),
            "fx_translation_adjustment": field({"2024": -5.0}),
            "net_change_in_cash": field({"2024": 80.0}),
            "opening_cash": field({"2024": 20.0}),
            "closing_cash": field({"2024": 100.0}),
        }
    )

    result = FinancialValidationService().validate(DocumentType.CASH_FLOW_STATEMENT, data)

    assert result.overall_status == "PASS"
    assert all(check.status == "PASS" for check in result.checks)


def test_cash_flow_closing_cash_includes_acquired_cash_adjustment() -> None:
    data = ExtractedData(
        fields={
            "operating_cash_flow": field({"2024": 100.0}),
            "investing_cash_flow": field({"2024": -25.0}),
            "financing_cash_flow": field({"2024": 10.0}),
            "fx_translation_adjustment": field({"2024": -5.0}),
            "net_change_in_cash": field({"2024": 80.0}),
            "opening_cash": field({"2024": 20.0}),
            "cash_acquired_adjustment": field({"2024": 7.0}),
            "closing_cash": field({"2024": 107.0}),
        }
    )

    result = FinancialValidationService().validate(DocumentType.CASH_FLOW_STATEMENT, data)

    closing = next(check for check in result.checks if check.name == "cash_flow_closing_cash")
    assert closing.status == "PASS"
    assert closing.calculated_value == 107.0
