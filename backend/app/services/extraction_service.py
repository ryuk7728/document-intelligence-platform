from app.schemas.document import DocumentType, ExtractedData
from app.services.financial_extraction_service import FinancialExtractionService
from app.services.invoice_extraction_service import InvoiceExtractionService
from app.services.layout import PageText


class DocumentExtractionService:
    def __init__(self) -> None:
        self.invoice_extractor = InvoiceExtractionService()
        self.financial_extractor = FinancialExtractionService()

    def extract(self, pages: list[PageText], document_type: DocumentType) -> ExtractedData:
        if document_type == DocumentType.INVOICE:
            return self.invoice_extractor.extract(pages)
        return self.financial_extractor.extract(pages)

