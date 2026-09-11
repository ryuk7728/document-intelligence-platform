from pathlib import Path

import pymupdf
from PIL import Image

from app.services.document_validation_service import DocumentValidationService


def test_valid_png_passes(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (100, 100), "white").save(image_path)

    result = DocumentValidationService().validate(image_path)

    assert result.status == "PASS"
    assert result.file_type == "image/png"
    assert result.page_count == 1


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("not a supported document", encoding="utf-8")

    result = DocumentValidationService().validate(path)

    assert result.status == "FAILED"
    assert result.error_code == "UNSUPPORTED_FILE_TYPE"


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    path.touch()

    result = DocumentValidationService().validate(path)

    assert result.status == "FAILED"
    assert result.error_code == "EMPTY_FILE"


def test_extension_content_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"this is not a pdf")

    result = DocumentValidationService().validate(path)

    assert result.status == "FAILED"
    assert result.error_code == "FILE_TYPE_MISMATCH"


def test_pdf_over_three_pages_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "four-pages.pdf"
    document = pymupdf.open()
    for _ in range(4):
        document.new_page()
    document.save(path)
    document.close()

    result = DocumentValidationService().validate(path)

    assert result.status == "FAILED"
    assert result.error_code == "PAGE_LIMIT_EXCEEDED"
    assert result.page_count == 4

