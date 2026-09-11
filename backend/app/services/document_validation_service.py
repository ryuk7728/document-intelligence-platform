from pathlib import Path

import pymupdf
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings, get_settings
from app.schemas.document import FileValidation


SUPPORTED_TYPES = {
    ".pdf": ("application/pdf", b"%PDF"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
}


class DocumentValidationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate(self, file_path: str | Path) -> FileValidation:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_TYPES:
            return self._failure("UNSUPPORTED_FILE_TYPE", "Only PDF, JPG, and PNG documents are supported.")
        mime_type, signature = SUPPORTED_TYPES[suffix]
        if not path.is_file() or path.stat().st_size == 0:
            return self._failure("EMPTY_FILE", "The uploaded file is empty or missing.", mime_type)
        if path.stat().st_size > self.settings.max_upload_size_mb * 1024 * 1024:
            return self._failure("FILE_TOO_LARGE", "The uploaded file exceeds the configured size limit.", mime_type)
        try:
            with path.open("rb") as stream:
                header = stream.read(max(len(signature), 8))
        except OSError:
            return self._failure("UNREADABLE_FILE", "The uploaded file could not be read.", mime_type)
        if not header.startswith(signature):
            return self._failure("FILE_TYPE_MISMATCH", "The file content does not match its extension.", mime_type)

        try:
            page_count = self._page_count(path, suffix)
        except (pymupdf.FileDataError, RuntimeError, OSError, UnidentifiedImageError, ValueError):
            return self._failure("CORRUPTED_FILE", "The uploaded document is corrupted or unreadable.", mime_type)
        if page_count < 1:
            return self._failure("EMPTY_DOCUMENT", "The uploaded document contains no readable pages.", mime_type)
        if page_count > self.settings.max_upload_pages:
            return self._failure(
                "PAGE_LIMIT_EXCEEDED",
                f"Documents may contain at most {self.settings.max_upload_pages} pages.",
                mime_type,
                page_count,
            )
        return FileValidation(
            file_type=mime_type,
            is_supported=True,
            is_readable=True,
            page_count=page_count,
            status="PASS",
        )

    @staticmethod
    def _page_count(path: Path, suffix: str) -> int:
        if suffix == ".pdf":
            with pymupdf.open(path) as document:
                if document.needs_pass:
                    raise ValueError("Encrypted PDF")
                for page in document:
                    _ = page.rect
                return document.page_count
        with Image.open(path) as image:
            image.verify()
            return 1

    @staticmethod
    def _failure(
        code: str,
        message: str,
        file_type: str | None = None,
        page_count: int | None = None,
    ) -> FileValidation:
        return FileValidation(
            file_type=file_type,
            is_supported=code != "UNSUPPORTED_FILE_TYPE",
            is_readable=False,
            page_count=page_count,
            status="FAILED",
            error_code=code,
            error_message=message,
        )

