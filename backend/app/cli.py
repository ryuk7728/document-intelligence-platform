import argparse
from pathlib import Path

from app.schemas.document import DocumentType
from app.services.document_service import DocumentProcessingService


def main() -> None:
    parser = argparse.ArgumentParser(description="Process one financial document and emit structured JSON.")
    parser.add_argument("file", type=Path)
    parser.add_argument("document_type", choices=[item.value for item in DocumentType])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = DocumentProcessingService().process(args.file, DocumentType(args.document_type))
    json_text = result.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_text + "\n", encoding="utf-8")
    else:
        print(json_text)


if __name__ == "__main__":
    main()

