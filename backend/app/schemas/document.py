from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    INVOICE = "invoice"
    BALANCE_SHEET = "balance_sheet"
    PROFIT_AND_LOSS = "profit_and_loss"
    CASH_FLOW_STATEMENT = "cash_flow_statement"


class Evidence(BaseModel):
    source_text: str
    page_number: int = Field(ge=1)
    bounding_box: list[float] | None = None


class ExtractedValue(BaseModel):
    value: Any = None
    evidence: Evidence | None = None


class InvoiceLineItem(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    net_amount: float | None = None
    tax_rate: float | None = None
    tax_amount: float | None = None
    amount: float | None = None
    evidence: Evidence


class FinancialLineItem(BaseModel):
    label: str
    section: str | None = None
    schedule: str | None = None
    values: dict[str, float | None]
    evidence: Evidence


class ExtractedTable(BaseModel):
    name: str
    columns: list[str]
    rows: list[dict[str, Any]]
    page_number: int = Field(ge=1)


class ExtractedData(BaseModel):
    fields: dict[str, ExtractedValue] = Field(default_factory=dict)
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    financial_line_items: list[FinancialLineItem] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)
    source_text_blocks: list[Evidence] = Field(default_factory=list)


class FileValidation(BaseModel):
    file_type: str | None = None
    is_supported: bool = False
    is_readable: bool = False
    page_count: int | None = None
    status: Literal["PASS", "FAILED"]
    error_code: str | None = None
    error_message: str | None = None


class ValidationCheck(BaseModel):
    name: str
    period: str | None = None
    formula: str
    operands: dict[str, float | None]
    calculated_value: float | None = None
    reported_value: float | None = None
    variance: float | None = None
    status: Literal["PASS", "FAIL", "NOT_APPLICABLE"]
    message: str | None = None


class FinancialValidation(BaseModel):
    checks: list[ValidationCheck] = Field(default_factory=list)
    overall_status: Literal["PASS", "FAIL", "NOT_APPLICABLE"]
    issues: list[str] = Field(default_factory=list)


class ProcessingMetadata(BaseModel):
    ocr_used: bool
    processed_at: str
    processing_time_ms: int = Field(ge=0)
    extraction_provider: str


class ProcessingResult(BaseModel):
    document_name: str
    document_type: DocumentType
    processing_status: Literal["PASS", "FAILED"]
    file_validation: FileValidation
    extracted_data: ExtractedData
    validation: FinancialValidation
    processing_metadata: ProcessingMetadata


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class DocumentSummary(BaseModel):
    id: int
    document_name: str
    document_type: DocumentType
    processing_status: Literal["PASS", "FAILED"]
    validation_status: Literal["PASS", "FAIL", "NOT_APPLICABLE"]
    created_at: datetime


class StoredDocument(BaseModel):
    id: int
    created_at: datetime
    result: ProcessingResult


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
