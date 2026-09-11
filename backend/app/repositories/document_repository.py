import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import DocumentRecord
from app.schemas.document import (
    DocumentListResponse,
    DocumentSummary,
    ProcessingResult,
    StoredDocument,
)


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, result: ProcessingResult) -> StoredDocument:
        record = DocumentRecord(
            document_name=result.document_name,
            document_type=result.document_type.value,
            processing_status=result.processing_status,
            result_json=result.model_dump_json(),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._stored(record)

    def get(self, record_id: int) -> StoredDocument | None:
        record = self.session.get(DocumentRecord, record_id)
        return self._stored(record) if record else None

    def get_latest_by_name(self, document_name: str) -> StoredDocument | None:
        record = self.session.scalar(
            select(DocumentRecord)
            .where(DocumentRecord.document_name == document_name)
            .order_by(DocumentRecord.created_at.desc(), DocumentRecord.id.desc())
            .limit(1)
        )
        return self._stored(record) if record else None

    def list(self, limit: int, offset: int) -> DocumentListResponse:
        records = self.session.scalars(
            select(DocumentRecord)
            .order_by(DocumentRecord.created_at.desc(), DocumentRecord.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        total = self.session.scalar(select(func.count()).select_from(DocumentRecord)) or 0
        return DocumentListResponse(
            items=[self._summary(record) for record in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _stored(record: DocumentRecord) -> StoredDocument:
        return StoredDocument(
            id=record.id,
            created_at=record.created_at,
            result=ProcessingResult.model_validate_json(record.result_json),
        )

    @staticmethod
    def _summary(record: DocumentRecord) -> DocumentSummary:
        payload = json.loads(record.result_json)
        return DocumentSummary(
            id=record.id,
            document_name=record.document_name,
            document_type=record.document_type,
            processing_status=record.processing_status,
            validation_status=payload.get("validation", {}).get("overall_status", "NOT_APPLICABLE"),
            created_at=record.created_at,
        )
