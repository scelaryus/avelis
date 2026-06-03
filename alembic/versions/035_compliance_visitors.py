"""Data protection compliance + visitor management.

Tables:
- data_processing_registry: ANPDP register
- consent_record: employee data processing consent
- data_access_request: right-of-access (72h SLA)
- data_purge_log: anonymization events
- visitor: QR-coded temporary access
- hr_document_template: 6 HR doc templates seeded

Revision ID: 035
Revises: 034
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_tpl_counter = 0


def _tpl_uuid():
    global _tpl_counter
    _tpl_counter += 1
    return f"f6000000-0000-0000-0000-{_tpl_counter:012x}"


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


HR_TEMPLATES = [
    ("CERTIFICAT_TRAVAIL", "Certificat de Travail", "OFFBOARDING"),
    ("ATTESTATION_TRAVAIL", "Attestation de Travail", "ATTESTATION"),
    ("PV_PASSATION", "PV de Passation de Consignes", "PASSATION"),
    ("QUITUS_DECHARGE", "Modele Quitus / Decharge", "QUITUS"),
    ("RECU_PAIEMENT", "Recu de Paiement", "PAIEMENT"),
    ("BON_SORTIE", "Bon de Sortie Equipement", "BON_SORTIE"),
]


def upgrade() -> None:
    # 1. data_processing_registry (system reference)
    op.create_table(
        "data_processing_registry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("activity_name", sa.String(255), nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("data_categories", JSONB, nullable=False),
        sa.Column("recipients", JSONB, nullable=True),
        sa.Column("retention_period_years", sa.Integer, nullable=False),
        sa.Column("security_measures", JSONB, nullable=True),
        sa.Column("legal_basis", sa.String(100), nullable=True),
        sa.Column("module", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_reviewed", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 2. consent_record
    op.create_table(
        "consent_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("consent_type", sa.String(50), nullable=False),
        sa.Column("consent_given", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("consent_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_document_url", sa.Text, nullable=True),
        sa.Column("withdrawn", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("withdrawn_date", sa.DateTime(timezone=True), nullable=True),
        *_system_columns(),
    )

    # 3. data_access_request
    op.create_table(
        "data_access_request",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("request_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("export_json_url", sa.Text, nullable=True),
        sa.Column("export_pdf_url", sa.Text, nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_by", UUID(as_uuid=True), nullable=True),
        *_system_columns(),
    )

    # 4. data_purge_log
    op.create_table(
        "data_purge_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("purge_date", sa.Date, nullable=False, index=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("records_anonymized", sa.Integer, nullable=False),
        sa.Column("retention_rule", sa.String(100), nullable=False),
        sa.Column("reviewed_by_dpo", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("dpo_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detail", JSONB, nullable=True),
        *_system_columns(),
    )

    # 5. visitor
    op.create_table(
        "visitor",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("visitor_name", sa.String(255), nullable=False),
        sa.Column("visitor_company", sa.String(255), nullable=True),
        sa.Column("visitor_phone", sa.String(30), nullable=True),
        sa.Column("visitor_email", sa.String(255), nullable=True),
        sa.Column("host_employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("purpose", sa.Text, nullable=True),
        sa.Column("authorized_zones", JSONB, nullable=True),
        sa.Column("visit_date", sa.Date, nullable=False, index=True),
        sa.Column("time_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("qr_code_data", sa.Text, nullable=True, unique=True),
        sa.Column("qr_sent_via", sa.String(10), nullable=True),
        sa.Column("qr_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'REGISTERED'")),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
        *_system_columns(),
    )

    # 6. hr_document_template (system reference)
    op.create_table(
        "hr_document_template",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(30), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("template_path", sa.Text, nullable=True),
        sa.Column("fields_schema", JSONB, nullable=True),
        sa.Column("qr_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Triggers
    for t in ("consent_record", "data_access_request", "data_purge_log", "visitor"):
        op.execute(f"""CREATE TRIGGER trg_{t}_updated_at BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{t}');")

    # Seed HR doc templates
    for code, name, cat in HR_TEMPLATES:
        uid = _tpl_uuid()
        op.execute(f"""
            INSERT INTO hr_document_template (id, code, name, category)
            VALUES ('{uid}', '{code}', '{name}', '{cat}');
        """)


def downgrade() -> None:
    for t in ("visitor", "data_purge_log", "data_access_request", "consent_record"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_updated_at ON {t};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_no_delete ON {t};")
    op.drop_table("visitor")
    op.drop_table("data_purge_log")
    op.drop_table("data_access_request")
    op.drop_table("consent_record")
    op.drop_table("hr_document_template")
    op.drop_table("data_processing_registry")
