import json
from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings
from app.schemas.document import DocumentType, ExtractedData
from app.services.layout import PageText


@dataclass(slots=True)
class ExtractionOutcome:
    data: ExtractedData
    provider: str


class LLMExtractionService:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client

    def enrich(
        self,
        local_result: ExtractedData,
        pages: list[PageText],
        document_type: DocumentType,
    ) -> ExtractionOutcome:
        if self.settings.llm_provider != "openai_compatible":
            return ExtractionOutcome(local_result, "local_ocr_and_rules")
        if not self.settings.llm_api_key or not self.settings.llm_model:
            return ExtractionOutcome(local_result, "local_ocr_and_rules")

        payload = {
            "model": self.settings.llm_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract every meaningful visible field and table from the supplied financial document text. "
                        "Return only JSON matching the requested structure. Use null for missing or unreadable values. "
                        "Do not infer facts that are not grounded in the source. Preserve comparative periods and negative parentheses. "
                        "Every important value must include source_text and page_number evidence. Do not invent confidence scores."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "document_type": document_type.value,
                            "required_shape": {
                                "fields": {"snake_case_name": {"value": "any or null", "evidence": {"source_text": "text", "page_number": 1}}},
                                "line_items": [],
                                "financial_line_items": [],
                                "tables": [],
                            },
                            "ocr_pages": [{"page_number": page.page_number, "text": page.text} for page in pages],
                            "local_draft": local_result.model_dump(mode="json", exclude={"source_text_blocks"}),
                        }
                    ),
                },
            ],
        }
        client = self.client or httpx.Client(timeout=60.0)
        try:
            response = client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.strip("`")
                if content.startswith("json"):
                    content = content[4:].lstrip()
            enriched = ExtractedData.model_validate(json.loads(content))
            enriched.source_text_blocks = local_result.source_text_blocks
            for key, value in local_result.fields.items():
                enriched.fields.setdefault(key, value)
            if not enriched.line_items:
                enriched.line_items = local_result.line_items
            if not enriched.financial_line_items:
                enriched.financial_line_items = local_result.financial_line_items
            if not enriched.tables:
                enriched.tables = local_result.tables
            return ExtractionOutcome(enriched, f"openai_compatible:{self.settings.llm_model}")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            return ExtractionOutcome(local_result, "local_ocr_and_rules_llm_fallback")
        finally:
            if self.client is None:
                client.close()

