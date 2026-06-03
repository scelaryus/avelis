"""Document generation engine + relance (follow-up) system.

Tables:
- document_template: 14 PDF template definitions (seeded)
- generated_document: instances linked to dossiers
- relance_tracker: per-document follow-up status with escalation

Seeds 14 document templates with RF2 visibility flags.

Revision ID: 018
Revises: 017
Create Date: 2026-03-18
"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_tpl_counter = 0


def _tpl_uuid():
    global _tpl_counter
    _tpl_counter += 1
    return f"f1000000-0000-0000-0000-{_tpl_counter:012x}"


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


TEMPLATES = [
    ("DEVIS", "Devis", "ADV", True, False,
     "RF1 price only. NEVER shows RF2."),
    ("ATTEST_RESERV_NO_RF2", "Attestation de reservation (RF2 non securise)",
     "ADV", True, False,
     "WITHOUT ANY AMOUNTS. Rule RF2-S03."),
    ("ATTEST_RESERV_RF2_OK", "Attestation de reservation (RF2 securise)",
     "ADV", True, False,
     "Can include RF1 amounts only."),
    ("DECISION_AFFECTATION", "Decision d''affectation",
     "ADV", True, False,
     "RF1 price ONLY (ENG-003). Promesse de Vente."),
    ("GUIDE_TECHNIQUE", "Guide technique client",
     "ADV", True, False,
     "Technical lot specifications."),
    ("ECHEANCIER_PDF", "Echeancier de paiement",
     "ADV", True, False,
     "Installment schedule."),
    ("DEMANDE_DEBLOCAGE", "Demande de deblocage",
     "CREDIT", False, False,
     "Expert report + tier amount. Bank only."),
    ("ETAT_DETAILLE_PDF", "Etat detaille cheque notaire",
     "NOTAIRE", False, False,
     "Cheque breakdown. Internal."),
    ("FICHE_DEPOT_NOTAIRE", "Fiche de depot notaire",
     "NOTAIRE", False, False,
     "Document deposit checklist. Internal."),
    ("PV_REMISE_CLES", "PV de remise des cles",
     "ADV", True, False,
     "Key handover signed by client + company."),
    ("RECU_RF1", "Recu de paiement RF1",
     "ADV", True, False,
     "Official receipt."),
    ("RECU_RF2", "Recu interne RF2",
     "INTERNAL", False, True,
     "NEVER shown to client. Internal tracking only."),
    ("RELANCE_IMPAYE", "Relance impaye",
     "ADV", True, False,
     "Escalating severity letters."),
    ("RAPPORT_SITUATION", "Rapport de situation dossier",
     "ADV", True, False,
     "Full summary filtered by role."),
]


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. document_template (system reference)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "document_template",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(30), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("client_visible", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("rf2_content", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("template_path", sa.Text, nullable=True),
        sa.Column("required_fields", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. generated_document
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "generated_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("template_id", UUID(as_uuid=True),
                  sa.ForeignKey("document_template.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("template_code", sa.String(30), nullable=False, index=True),
        sa.Column("dossier_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("document_ref", sa.String(100), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("file_format", sa.String(10), nullable=False,
                  server_default=sa.text("'PDF'")),
        sa.Column("content_data", JSONB, nullable=True),
        sa.Column("client_visible", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("rf2_content", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'GENERE'")),
        sa.Column("sent_to_client", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("sent_to_bank", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. relance_tracker
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "relance_tracker",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dossier_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("document_type", sa.String(60), nullable=False),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("required_since", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'REQUIS'")),
        sa.Column("received_date", sa.Date, nullable=True),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("relance_j3_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relance_j7_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relance_j14_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relance_j30_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relance_count", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        sa.Column("blocks_operation", sa.String(40), nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("generated_document", "relance_tracker"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ═════════════════════════════════════════════════════════════════════
    # 5. SEED — 14 document templates
    # ═════════════════════════════════════════════════════════════════════
    for code, name, category, client_vis, rf2, desc in TEMPLATES:
        uid = _tpl_uuid()
        desc_esc = desc.replace("'", "''")
        name_esc = name.replace("'", "''")
        cv = "true" if client_vis else "false"
        r2 = "true" if rf2 else "false"
        op.execute(f"""
            INSERT INTO document_template (id, code, name, category,
                                           client_visible, rf2_content, description)
            VALUES ('{uid}', '{code}', '{name_esc}', '{category}',
                    {cv}, {r2}, '{desc_esc}');
        """)


def downgrade() -> None:
    for table in ("relance_tracker", "generated_document"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("relance_tracker")
    op.drop_table("generated_document")
    op.drop_table("document_template")
