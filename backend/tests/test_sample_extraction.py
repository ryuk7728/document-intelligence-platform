from pathlib import Path

import pytest

from app.schemas.document import DocumentType
from app.services.document_service import DocumentProcessingService


DATASET = Path(__file__).parents[2] / "samples" / "dataset" / "New Dataset"


@pytest.fixture(scope="module")
def processing_service() -> DocumentProcessingService:
    return DocumentProcessingService()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("relative_path", "document_type", "required_fields", "ocr_expected"),
    [
        (
            Path("Invoices") / "batch1-1109.jpg",
            DocumentType.INVOICE,
            {"invoice_number", "invoice_date", "vendor_name", "customer_name", "subtotal", "tax_amount", "total_amount"},
            True,
        ),
        (
            Path("Balance Sheet") / "Consolidated Balance Sheet 2017.pdf",
            DocumentType.BALANCE_SHEET,
            {"total_assets", "total_capital_and_liabilities"},
            True,
        ),
        (
            Path("Profit & Loss") / "Consolidated Profit & Loss 2017.pdf",
            DocumentType.PROFIT_AND_LOSS,
            {"total_income", "total_expenditure", "net_profit_attributable_to_group"},
            True,
        ),
        (
            Path("Cash Flows") / "Consolidated Cash Flow Statement 2022.pdf",
            DocumentType.CASH_FLOW_STATEMENT,
            {"operating_cash_flow", "investing_cash_flow", "financing_cash_flow", "net_change_in_cash", "opening_cash", "closing_cash"},
            False,
        ),
    ],
)
def test_representative_case_study_sample(
    processing_service: DocumentProcessingService,
    relative_path: Path,
    document_type: DocumentType,
    required_fields: set[str],
    ocr_expected: bool,
) -> None:
    if not DATASET.exists():
        pytest.skip("Case-study sample dataset is not available.")

    result = processing_service.process(DATASET / relative_path, document_type)

    assert result.file_validation.status == "PASS"
    assert result.processing_status == "PASS"
    assert required_fields.issubset(result.extracted_data.fields)
    assert result.validation.overall_status == "PASS"
    assert result.processing_metadata.ocr_used is ocr_expected
    assert result.extracted_data.source_text_blocks


@pytest.mark.integration
def test_invoice_extracts_structured_line_items(processing_service: DocumentProcessingService) -> None:
    if not DATASET.exists():
        pytest.skip("Case-study sample dataset is not available.")

    result = processing_service.process(DATASET / "Invoices" / "batch1-1109.jpg", DocumentType.INVOICE)

    assert len(result.extracted_data.line_items) == 7
    assert result.extracted_data.line_items[0].quantity == 5
    assert result.extracted_data.line_items[0].unit_price == 3.49
    assert result.extracted_data.line_items[0].net_amount == 17.45


@pytest.mark.integration
def test_tax_inclusive_receipt_uses_corroborating_card_total(
    processing_service: DocumentProcessingService,
) -> None:
    if not DATASET.exists():
        pytest.skip("Case-study sample dataset is not available.")

    result = processing_service.process(DATASET / "Invoices" / "X51006328913.jpg", DocumentType.INVOICE)

    assert result.processing_status == "PASS"
    assert result.extracted_data.fields["subtotal"].value == 105.0
    assert result.extracted_data.fields["total_amount"].value == 105.0
    assert result.extracted_data.fields["total_amount"].evidence.source_text == "MASTER 105.00"
    assert result.validation.overall_status == "PASS"
