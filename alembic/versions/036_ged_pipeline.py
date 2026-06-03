"""GED: 7-layer document processing pipeline for 400+ GB heritage.

Tables:
- document: core record with SHA-256 dedup, classification, full-text search
- document_version: version history (modifications create new versions)
- document_processing_run: per-layer execution log

KT-01: SHA-256 unique constraint blocks duplicate documents.
Full-text search via PostgreSQL tsvector + GIN index.

Revision ID: 036
Revises: 035
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _system_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("version", sa.Integer, nullable=False,
                  server_default=sa.text("1")),
    ]


def upgrade() -> None:
    # 1. document
    op.create_table(
        "document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("document_ref", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("file_hash_sha256", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("document_type", sa.String(30), nullable=True, index=True),
        sa.Column("classification_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("extracted_metadata", JSONB, nullable=True),
        sa.Column("extraction_complete", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("aliases_resolved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("unresolved_aliases", JSONB, nullable=True),
        sa.Column("storage_path", sa.Text, nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("linked_entity_type", sa.String(50), nullable=True),
        sa.Column("linked_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("pipeline_status", sa.String(30), nullable=False, server_default=sa.text("'RECEIVED'")),
        sa.Column("pipeline_blocked_reason", sa.Text, nullable=True),
        sa.Column("upload_source", sa.String(20), nullable=True),
        sa.Column("uploaded_by_name", sa.String(255), nullable=True),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("ocr_language", sa.String(10), nullable=True),
        sa.Column("search_vector", TSVECTOR, nullable=True),
        sa.Column("current_version", sa.Integer, nullable=False, server_default=sa.text("1")),
        *_system_columns(),
    )

    # Full-text search GIN index
    op.execute("""
        CREATE INDEX ix_document_search_vector
        ON document USING GIN (search_vector);
    """)

    # Auto-update search vector on text change
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_document_search_update()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.ocr_text IS NOT NULL THEN
                NEW.search_vector := to_tsvector('french', NEW.ocr_text);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_document_search_update
        BEFORE INSERT OR UPDATE ON document
        FOR EACH ROW EXECUTE FUNCTION gfi_document_search_update();
    """)

    # 2. document_version
    op.create_table(
        "document_version",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("document.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("file_hash_sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("change_description", sa.Text, nullable=True),
        *_system_columns(),
    )

    # 3. document_processing_run
    op.create_table(
        "document_processing_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("document.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("layer", sa.Integer, nullable=False),
        sa.Column("layer_name", sa.String(30), nullable=False),
        sa.Column("result", sa.String(10), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        *_system_columns(),
    )

    for t in ("document", "document_version", "document_processing_run"):
        op.execute(f"""CREATE TRIGGER trg_{t}_updated_at BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{t}');")


def downgrade() -> None:
    for t in ("document_processing_run", "document_version", "document"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_updated_at ON {t};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_no_delete ON {t};")
    op.execute("DROP TRIGGER IF EXISTS trg_document_search_update ON document;")
    op.execute("DROP FUNCTION IF EXISTS gfi_document_search_update();")
    op.drop_table("document_processing_run")
    op.drop_table("document_version")
    op.drop_table("document")
