from pathlib import Path

import cv2
import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR

from app.services.layout import PageText, TextToken


class OCRService:
    def __init__(self, native_text_threshold: int = 80) -> None:
        self.native_text_threshold = native_text_threshold
        self._ocr_engine: RapidOCR | None = None

    @property
    def ocr_engine(self) -> RapidOCR:
        if self._ocr_engine is None:
            self._ocr_engine = RapidOCR()
        return self._ocr_engine

    def extract(self, file_path: str | Path, file_type: str) -> list[PageText]:
        path = Path(file_path)
        if file_type == "application/pdf":
            return self._extract_pdf(path)
        return [self._ocr_image_path(path, page_number=1)]

    def _extract_pdf(self, path: Path) -> list[PageText]:
        pages: list[PageText] = []
        with pymupdf.open(path) as document:
            for index, page in enumerate(document):
                native_words = page.get_text("words", sort=True)
                native_text = page.get_text("text", sort=True).strip()
                if len(native_text) >= self.native_text_threshold and native_words:
                    pages.append(self._native_page(page, native_words, index + 1))
                else:
                    matrix = pymupdf.Matrix(2.2, 2.2)
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                        pixmap.height,
                        pixmap.width,
                        pixmap.n,
                    )
                    pages.append(self._ocr_array(image, index + 1))
        return pages

    @staticmethod
    def _native_page(page: pymupdf.Page, words: list[tuple], page_number: int) -> PageText:
        width = float(page.rect.width)
        height = float(page.rect.height)
        tokens = [
            TextToken(
                text=str(word[4]),
                page_number=page_number,
                confidence=1.0,
                x0=float(word[0]) / width,
                y0=float(word[1]) / height,
                x1=float(word[2]) / width,
                y1=float(word[3]) / height,
            )
            for word in words
            if str(word[4]).strip()
        ]
        return PageText(page_number=page_number, width=int(width), height=int(height), method="native_pdf", tokens=tokens)

    def _ocr_image_path(self, path: Path, page_number: int) -> PageText:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Image could not be decoded for OCR.")
        return self._ocr_array(image, page_number)

    def _ocr_array(self, image: np.ndarray, page_number: int) -> PageText:
        height, width = image.shape[:2]
        result, _ = self.ocr_engine(image)
        tokens: list[TextToken] = []
        for item in result or []:
            box, text, confidence = item
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            cleaned = str(text).strip()
            if not cleaned:
                continue
            tokens.append(
                TextToken(
                    text=cleaned,
                    page_number=page_number,
                    confidence=float(confidence),
                    x0=min(xs) / width,
                    y0=min(ys) / height,
                    x1=max(xs) / width,
                    y1=max(ys) / height,
                )
            )
        return PageText(page_number=page_number, width=width, height=height, method="ocr", tokens=tokens)

