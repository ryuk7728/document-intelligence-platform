import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.schemas.document import DocumentType
from app.services.document_service import DocumentProcessingService


CATEGORY_TYPES = {
    "Invoices": DocumentType.INVOICE,
    "Balance Sheet": DocumentType.BALANCE_SHEET,
    "Profit & Loss": DocumentType.PROFIT_AND_LOSS,
    "Cash Flows": DocumentType.CASH_FLOW_STATEMENT,
}

MINIMUM_FIELDS = {
    DocumentType.INVOICE: {
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "currency",
        "subtotal",
        "tax_amount",
        "total_amount",
    },
    DocumentType.BALANCE_SHEET: {"periods", "currency", "total_assets", "total_capital_and_liabilities"},
    DocumentType.PROFIT_AND_LOSS: {"periods", "total_income", "total_expenditure", "net_profit_attributable_to_group"},
    DocumentType.CASH_FLOW_STATEMENT: {
        "periods",
        "operating_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
        "net_change_in_cash",
        "opening_cash",
        "closing_cash",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile extraction results across the supplied sample dataset.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    service = DocumentProcessingService()
    records = []
    for category, document_type in CATEGORY_TYPES.items():
        category_path = args.dataset / category
        for path in sorted(category_path.iterdir()):
            if not path.is_file():
                continue
            result = service.process(path, document_type)
            field_names = set(result.extracted_data.fields)
            record = {
                "file": path.name,
                "category": category,
                "document_type": document_type.value,
                "processing_status": result.processing_status,
                "file_validation": result.file_validation.status,
                "financial_validation": result.validation.overall_status,
                "ocr_used": result.processing_metadata.ocr_used,
                "processing_time_ms": result.processing_metadata.processing_time_ms,
                "field_count": len(field_names),
                "line_item_count": len(result.extracted_data.line_items),
                "financial_line_item_count": len(result.extracted_data.financial_line_items),
                "missing_minimum_fields": sorted(MINIMUM_FIELDS[document_type] - field_names),
                "error_code": result.file_validation.error_code,
            }
            records.append(record)
            print(
                f"{category}: {path.name} | {record['processing_status']} | "
                f"fields={record['field_count']} missing={len(record['missing_minimum_fields'])} | "
                f"validation={record['financial_validation']} | {record['processing_time_ms']}ms",
                flush=True,
            )

    by_category = defaultdict(lambda: Counter())
    for record in records:
        counter = by_category[record["category"]]
        counter["files"] += 1
        counter[f"processing_{record['processing_status'].lower()}"] += 1
        counter[f"validation_{record['financial_validation'].lower()}"] += 1
        counter["complete_minimum_field_set"] += not record["missing_minimum_fields"]
        counter["ocr_used"] += record["ocr_used"]

    report = {
        "summary": {category: dict(counter) for category, counter in by_category.items()},
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

