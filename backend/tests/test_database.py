from sqlalchemy import create_engine, inspect, text

from app.core.database import Base, normalize_database_url
from app.models.document import DocumentRecord


def test_document_table_can_be_created() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    assert "document_records" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_document_record_has_required_foundation_fields() -> None:
    column_names = {column.name for column in DocumentRecord.__table__.columns}
    assert {
        "id",
        "document_name",
        "document_type",
        "processing_status",
        "result_json",
        "created_at",
    }.issubset(column_names)


def test_render_postgres_url_uses_psycopg_driver() -> None:
    assert normalize_database_url("postgresql://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )
    assert normalize_database_url("sqlite:///local.db") == "sqlite:///local.db"
