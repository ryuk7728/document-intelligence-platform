from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.schemas.document import (
    DocumentType,
    ExtractedData,
    FinancialValidation,
    ProcessingMetadata,
    ProcessingResult,
)
from app.services.document_validation_service import DocumentValidationService
from app.services.extraction_service import DocumentExtractionService
from app.services.financial_validation_service import FinancialValidationService
from app.services.llm_extraction_service import LLMExtractionService
from app.services.ocr_service import OCRService


class DocumentProcessingService:
    def __init__(self) -> None:
        self.file_validator = DocumentValidationService()
        self.ocr_service = OCRService()
        self.extractor = DocumentExtractionService()
        self.llm_extractor = LLMExtractionService()
        self.financial_validator = FinancialValidationService()

    def process(self, file_path: str | Path, document_type: DocumentType) -> ProcessingResult:
        path = Path(file_path)
        started = perf_counter()
        processed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        file_validation = self.file_validator.validate(path)
        if file_validation.status == "FAILED":
            return ProcessingResult(
                document_name=path.name,
                document_type=document_type,
                processing_status="FAILED",
                file_validation=file_validation,
                extracted_data=ExtractedData(),
                validation=FinancialValidation(checks=[], overall_status="NOT_APPLICABLE", issues=[]),
                processing_metadata=ProcessingMetadata(
                    ocr_used=False,
                    processed_at=processed_at,
                    processing_time_ms=int((perf_counter() - started) * 1000),
                    extraction_provider="none",
                ),
            )
        try:
            pages = self.ocr_service.extract(path, file_validation.file_type or "")
            local_result = self.extractor.extract(pages, document_type)
            outcome = self.llm_extractor.enrich(local_result, pages, document_type)
            financial_validation = self.financial_validator.validate(document_type, outcome.data)
            return ProcessingResult(
                document_name=path.name,
                document_type=document_type,
                # Processing and financial reconciliation are separate outcomes. A
                # genuine accounting mismatch is a successful processing result
                # whose validation status is FAIL.
                processing_status="PASS",
                file_validation=file_validation,
                extracted_data=outcome.data,
                validation=financial_validation,
                processing_metadata=ProcessingMetadata(
                    ocr_used=any(page.method == "ocr" for page in pages),
                    processed_at=processed_at,
                    processing_time_ms=int((perf_counter() - started) * 1000),
                    extraction_provider=outcome.provider,
                ),
            )
        except Exception as exc:
            file_validation.status = "FAILED"
            file_validation.is_readable = False
            file_validation.error_code = "PROCESSING_ERROR"
            file_validation.error_message = "The document could not be processed safely."
            return ProcessingResult(
                document_name=path.name,
                document_type=document_type,
                processing_status="FAILED",
                file_validation=file_validation,
                extracted_data=ExtractedData(),
                validation=FinancialValidation(
                    checks=[],
                    overall_status="NOT_APPLICABLE",
                    issues=[type(exc).__name__],
                ),
                processing_metadata=ProcessingMetadata(
                    ocr_used=False,
                    processed_at=processed_at,
                    processing_time_ms=int((perf_counter() - started) * 1000),
                    extraction_provider="none",
                ),
            )
