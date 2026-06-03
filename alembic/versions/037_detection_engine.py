"""Autonomous detection engine: 15 patterns for entity/flow/anomaly discovery.

Tables:
- detection_pattern: 15 pattern configs (seeded)
- detection_finding: structured findings requiring DAF validation

Revision ID: 037
Revises: 036
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PATTERNS = [
    (1, "GROUP_COMPANIES", "Group companies via NIF cross-match",
     "Same NIF as emitter AND receiver", "NIF_CROSS_MATCH", "CREATE_ENTITY"),
    (2, "ASSOCIATES", "Associates via CCA name variations",
     "Account 455 with spelling variations", "ALIAS_MATCH", "RESOLVE_ALIAS"),
    (3, "PROJECT_ALIASES", "Project aliases via address/parcel",
     "Same address/parcel in different labels", "ALIAS_MATCH", "RESOLVE_ALIAS"),
    (4, "INTER_PROJECT_FLOW", "Inter-project flows via account 580",
     "Matching amount+date on 580 in two journals", "SQL_QUERY", "GENERATE_FORMULAIRE"),
    (5, "RF3_FICTITIOUS", "RF3 between group entities",
     "Both NIFs are group entities", "NIF_CROSS_MATCH", "TRIGGER_CFF"),
    (6, "GACEB_ADVANCE", "GACEB 120M advance on account 409",
     "409100 + GACEB/AMENFORT/materiel label", "LABEL_SCAN", "FLAG_REVIEW"),
    (7, "VEHICLE_TRANSFER", "Vehicle transfers via account 218200",
     "Asset creation then disposal with GACEB", "SQL_QUERY", "FLAG_REVIEW"),
    (8, "ASSOCIATE_WITHDRAWAL", "Associate withdrawals via 455 debits",
     "455 debit with apartment/prelevement labels", "LABEL_SCAN", "FLAG_REVIEW"),
    (9, "KHADIDJA_DEBT", "Khadidja 18M debt on account 455",
     "455 entry with KHADIDJA GFI for 18M", "LABEL_SCAN", "FLAG_REVIEW"),
    (10, "VILLA_COMMISSION", "Villa commission 32M",
     "32M entry with villa/Zit Kaci label", "LABEL_SCAN", "FLAG_REVIEW"),
    (11, "BBZ_CHARGES", "BBZ charges on accounts 613/2181/275",
     "BBZ/Bab Ezzouar in labels", "LABEL_SCAN", "FLAG_REVIEW"),
    (12, "OWNERSHIP_60_20_20", "60/20/20/0 pattern in allocations",
     "Repetitive 60/20/20 across entries", "AMOUNT_PATTERN", "FLAG_REVIEW"),
    (13, "CFF_AMENFORT", "CFF from AMENFORT to ETS-DK",
     "AMENFORT NIF invoicing ETS-DK NIF", "NIF_CROSS_MATCH", "TRIGGER_CFF"),
    (14, "CFF_BAYTI", "CFF from BAYTI aliases",
     "Same NIF under Novus/BAYTI/Allo Maison", "ALIAS_MATCH", "TRIGGER_CFF"),
    (15, "OWNERSHIP_STATUTS", "Ownership from scanned bylaws",
     "PDF with repartition des parts", "LABEL_SCAN", "FLAG_REVIEW"),
]


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
    # 1. detection_pattern (system reference)
    op.create_table(
        "detection_pattern",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pattern_id", sa.Integer, unique=True, nullable=False),
        sa.Column("code", sa.String(30), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("evidence_signature", sa.Text, nullable=False),
        sa.Column("detection_method", sa.Text, nullable=False),
        sa.Column("proposed_action", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 2. detection_finding
    op.create_table(
        "detection_finding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("pattern_id", sa.Integer, nullable=False, index=True),
        sa.Column("pattern_code", sa.String(30), nullable=False, index=True),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_documents", JSONB, nullable=True),
        sa.Column("extracted_values", JSONB, nullable=True),
        sa.Column("proposed_action", sa.String(50), nullable=False),
        sa.Column("proposed_action_detail", JSONB, nullable=True),
        sa.Column("related_entity_ids", JSONB, nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'DETECTED'")),
        sa.Column("validated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_notes", sa.Text, nullable=True),
        sa.Column("integrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("integration_result", JSONB, nullable=True),
        *_system_columns(),
    )

    # Triggers
    op.execute("""CREATE TRIGGER trg_detection_finding_updated_at BEFORE UPDATE ON detection_finding
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
    op.execute("SELECT gfi_apply_no_delete_trigger('detection_finding');")

    # Seed 15 patterns
    for pid, code, name, evidence, method, action in PATTERNS:
        name_esc = name.replace("'", "''")
        evidence_esc = evidence.replace("'", "''")
        op.execute(f"""
            INSERT INTO detection_pattern (pattern_id, code, name, description,
                                           evidence_signature, detection_method, proposed_action)
            VALUES ({pid}, '{code}', '{name_esc}', '{name_esc}',
                    '{evidence_esc}', '{method}', '{action}');
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_detection_finding_updated_at ON detection_finding;")
    op.execute("DROP TRIGGER IF EXISTS trg_detection_finding_no_delete ON detection_finding;")
    op.drop_table("detection_finding")
    op.drop_table("detection_pattern")
