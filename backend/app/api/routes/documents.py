from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_session_dependency
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import (
    DocumentListResponse,
    DocumentType,
    ErrorResponse,
    StoredDocument,
)
from app.services.document_service import DocumentProcessingService


router = APIRouter(prefix="/documents", tags=["documents"])


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@router.post(
    "/process",
    response_model=StoredDocument,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def process_document(
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session_dependency),
) -> StoredDocument | JSONResponse:
    settings = get_settings()
    original_name = Path(file.filename or "").name
    if not original_name:
        return _error(status.HTTP_400_BAD_REQUEST, "MISSING_FILENAME", "An uploaded filename is required.")
    suffix = Path(original_name).suffix.lower()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    payload = await file.read(max_bytes + 1)
    await file.close()
    if len(payload) > max_bytes:
        return _error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "FILE_TOO_LARGE",
            "The uploaded file exceeds the configured size limit.",
        )

    with TemporaryDirectory(prefix="document-intelligence-") as directory:
        temporary_path = Path(directory) / f"upload{suffix}"
        temporary_path.write_bytes(payload)
        result = await run_in_threadpool(DocumentProcessingService().process, temporary_path, document_type)
    result.document_name = original_name
    if result.file_validation.status == "FAILED":
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            result.file_validation.error_code or "PROCESSING_FAILED",
            result.file_validation.error_message or "The document could not be processed.",
        )
    return DocumentRepository(session).create(result)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session_dependency),
) -> DocumentListResponse:
    return DocumentRepository(session).list(limit=limit, offset=offset)


@router.get("/latest/{document_name}", response_model=StoredDocument, responses={404: {"model": ErrorResponse}})
def get_latest_document(
    document_name: str,
    session: Session = Depends(get_session_dependency),
) -> StoredDocument | JSONResponse:
    record = DocumentRepository(session).get_latest_by_name(document_name)
    return record or _error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "No matching document was found.")


@router.get("/{record_id}", response_model=StoredDocument, responses={404: {"model": ErrorResponse}})
def get_document(
    record_id: int,
    session: Session = Depends(get_session_dependency),
) -> StoredDocument | JSONResponse:
    record = DocumentRepository(session).get(record_id)
    return record or _error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "No matching document was found.")
